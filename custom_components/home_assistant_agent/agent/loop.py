"""Agent orchestration loop."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    CONF_MAX_ACTIONS,
    CONF_MISSION_STATEMENT,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    EVENT_CHECKPOINT_SAVED,
    EVENT_RESUME,
    MAX_RETRIES,
)
from ..memory.checkpoint import CheckpointStore
from ..memory.summarizer import MemorySummarizer
from ..memory.store import MemoryStore
from ..notify import Notifier
from .executor import Executor
from .planner import AgentPlan, Planner
from .verifier import Verifier
from ..coordinator import StateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Outcome of an agent run."""

    plan: AgentPlan
    steps_executed: list[str]
    success: bool
    response_text: str


class AgentLoop:
    """Plan → execute → verify → retry orchestration."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        coordinator: StateCoordinator,
        planner: Planner,
        executor: Executor,
        verifier: Verifier,
        memory: MemoryStore,
        summarizer: MemorySummarizer,
        notifier: Notifier,
        checkpoint: CheckpointStore,
    ) -> None:
        self._hass = hass
        self._config = config
        self._coordinator = coordinator
        self._planner = planner
        self._executor = executor
        self._verifier = verifier
        self._memory = memory
        self._summarizer = summarizer
        self._notifier = notifier
        self._checkpoint = checkpoint
        self._lock = asyncio.Lock()
        self._running = False
        self._last_activity_ended_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def _now(self) -> datetime:
        try:
            from homeassistant.util import dt as dt_util

            return dt_util.now()
        except ImportError:
            from datetime import timezone

            return datetime.now(timezone.utc)

    def _poll_interval_seconds(self) -> int:
        return int(self._config.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

    def _idle_for_poll_period(self) -> bool:
        """Return True when no agent work has run for a full poll interval."""
        if self._last_activity_ended_at is None:
            return True
        elapsed = (self._now() - self._last_activity_ended_at).total_seconds()
        return elapsed >= self._poll_interval_seconds()

    def _mark_activity_ended(self) -> None:
        self._last_activity_ended_at = self._now()

    def _current_time_for_prompt(self) -> str:
        try:
            from homeassistant.util import dt as dt_util

            return dt_util.now().strftime("%Y-%m-%d %H:%M %Z")
        except ImportError:
            from datetime import datetime, timezone

            return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    async def run_background(self) -> RunResult | None:
        """Run agent cycle from coordinator update."""
        if self._lock.locked():
            _LOGGER.debug("Agent already running, skipping background cycle")
            return None

        if self._checkpoint.has_pending():
            _LOGGER.info("Pending checkpoint found; resuming instead of new background run")
            return await self.run_resume(reason="checkpoint")

        if not self._idle_for_poll_period():
            elapsed = (self._now() - self._last_activity_ended_at).total_seconds()
            _LOGGER.debug(
                "Agent active %.0fs ago; waiting for full poll interval (%ss) "
                "before next background LLM run",
                elapsed,
                self._poll_interval_seconds(),
            )
            return None

        async with self._lock:
            self._running = True
            try:
                mission = self._config.get(CONF_MISSION_STATEMENT, "")
                plan = await self._planner.plan_background(
                    mission=mission,
                    preferences=self._memory.get_preferences_text(),
                    memory=self._memory.get_summaries_text(),
                    current_time=self._current_time_for_prompt(),
                    diff=self._coordinator.format_diff_for_prompt(),
                    snapshot=self._coordinator.format_snapshot_for_prompt(),
                    automations=self._coordinator.format_list_for_prompt("automations"),
                    scenes=self._coordinator.format_list_for_prompt("scenes"),
                    scripts=self._coordinator.format_list_for_prompt("scripts"),
                )
                return await self._execute_plan(
                    plan,
                    user_request=None,
                    run_type="background",
                )
            finally:
                self._running = False
                self._mark_activity_ended()

    async def run_resume(self, *, reason: str = "startup") -> RunResult | None:
        """Resume an interrupted run from the persisted checkpoint."""
        if self._lock.locked():
            _LOGGER.debug("Agent already running, skipping resume")
            return None

        if not self._checkpoint.has_pending():
            _LOGGER.debug("No checkpoint to resume")
            return None

        snapshot = self._checkpoint.get_snapshot() or {}
        pending_count = len(snapshot.get("pending_steps", []))
        completed_count = len(snapshot.get("completed_steps", []))

        async with self._lock:
            self._running = True
            try:
                self._fire_resume_event(
                    reason=reason,
                    pending_steps=pending_count,
                    completed_steps=completed_count,
                )
                plan = self._checkpoint.to_plan()
                if not plan or not plan.steps:
                    _LOGGER.warning("Checkpoint had no executable steps; clearing")
                    await self._checkpoint.clear()
                    return None

                _LOGGER.info(
                    "Resuming interrupted run (%d steps remaining, reason=%s)",
                    len(plan.steps),
                    reason,
                )
                return await self._execute_plan(
                    plan,
                    user_request=snapshot.get("user_request"),
                    run_type=snapshot.get("run_type", "background"),
                    resuming=True,
                )
            finally:
                self._running = False
                self._mark_activity_ended()

    def _fire_resume_event(
        self,
        *,
        reason: str,
        pending_steps: int,
        completed_steps: int,
    ) -> None:
        self._hass.bus.async_fire(
            EVENT_RESUME,
            {
                "reason": reason,
                "pending_steps": pending_steps,
                "completed_steps": completed_steps,
            },
        )

    async def run_conversation(self, user_message: str) -> RunResult:
        """Run agent cycle from user input."""
        async with self._lock:
            self._running = True
            try:
                mission = self._config.get(CONF_MISSION_STATEMENT, "")
                plan = await self._planner.plan_conversation(
                    mission=mission,
                    preferences=self._memory.get_preferences_text(),
                    memory=self._memory.get_summaries_text(),
                    user_message=user_message,
                    snapshot=self._coordinator.format_snapshot_for_prompt(),
                )
                return await self._execute_plan(
                    plan,
                    user_request=user_message,
                    run_type="conversation",
                )
            finally:
                self._running = False
                self._mark_activity_ended()

    async def _execute_plan(
        self,
        plan: AgentPlan,
        *,
        user_request: str | None,
        run_type: str = "background",
        resuming: bool = False,
    ) -> RunResult:
        max_actions = self._config.get(CONF_MAX_ACTIONS, 10)
        steps_executed: list[str] = []
        overall_success = True
        last_error = ""

        if not plan.steps:
            _LOGGER.debug("No action steps in plan: %s", plan.reasoning)
            if resuming:
                await self._checkpoint.clear()
            if plan.summary_for_memory:
                await self._memory.add_entry(plan.summary_for_memory)
            return RunResult(
                plan=plan,
                steps_executed=[],
                success=True,
                response_text=plan.response_text or plan.reasoning,
            )

        steps_to_run = plan.steps[:max_actions]
        if len(plan.steps) > max_actions:
            _LOGGER.warning(
                "Truncating plan from %d to %d steps",
                len(plan.steps),
                max_actions,
            )

        if not resuming:
            await self._checkpoint.begin_run(
                plan,
                run_type=run_type,
                user_request=user_request,
            )
            self._hass.bus.async_fire(
                EVENT_CHECKPOINT_SAVED,
                {
                    "run_type": run_type,
                    "pending_steps": len(steps_to_run),
                    "completed_steps": 0,
                },
            )

        for idx, step in enumerate(steps_to_run):
            step_success = False
            last_error = ""
            current_states: dict[str, str] = {}

            for attempt in range(MAX_RETRIES):
                try:
                    await self._executor.execute_step(step)
                    result = await self._verifier.verify_step(step)
                    if result.success:
                        step_success = True
                        description = self._executor.describe_step(step)
                        steps_executed.append(description)
                        remaining = steps_to_run[idx + 1 :]
                        await self._checkpoint.record_step_done(description, remaining)
                        break
                    last_error = result.message
                    current_states = result.current_states
                    _LOGGER.warning(
                        "Verification failed (attempt %d): %s",
                        attempt + 1,
                        last_error,
                    )
                    if attempt < MAX_RETRIES - 1:
                        plan = await self._planner.plan_retry(
                            mission=self._config.get(CONF_MISSION_STATEMENT, ""),
                            failed_step={
                                "service": step.service,
                                "target": step.target,
                                "data": step.data,
                                "expected": step.expected,
                            },
                            error=last_error,
                            current_state=self._verifier.format_states(current_states),
                        )
                        if plan.steps:
                            step = plan.steps[0]
                except Exception as err:
                    last_error = str(err)
                    _LOGGER.error("Step execution failed: %s", err)
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                    else:
                        break

            if not step_success:
                overall_success = False
                if plan.notify_user or steps_executed:
                    await self._notifier.notify_significant(
                        title="Home Assistant Agent",
                        message=f"Action failed after retries: {last_error}",
                    )
                break

        if overall_success:
            await self._checkpoint.clear()

        outcome = "success" if overall_success else f"partial/failed: {last_error or 'ok'}"
        summary = plan.summary_for_memory
        if not summary:
            summary = await self._summarizer.summarize_run(
                reasoning=plan.reasoning,
                steps_taken=steps_executed,
                outcome=outcome,
                user_request=user_request,
            )
        await self._memory.add_entry(summary)

        should_notify = plan.notify_user or bool(steps_executed)
        if should_notify:
            notify_msg = plan.response_text or plan.reasoning
            if steps_executed:
                notify_msg = f"{notify_msg}\n\nActions: {'; '.join(steps_executed)}"
            await self._notifier.notify_significant(
                title="Home Assistant Agent",
                message=notify_msg,
            )

        response = plan.response_text or plan.reasoning
        if steps_executed and not plan.response_text:
            response = f"{response}\nExecuted: {'; '.join(steps_executed)}"

        return RunResult(
            plan=plan,
            steps_executed=steps_executed,
            success=overall_success,
            response_text=response,
        )
