"""Agent orchestration loop."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import CONF_MAX_ACTIONS, CONF_MISSION_STATEMENT, MAX_RETRIES
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
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def run_background(self) -> RunResult | None:
        """Run agent cycle from coordinator update."""
        if self._lock.locked():
            _LOGGER.debug("Agent already running, skipping background cycle")
            return None

        async with self._lock:
            self._running = True
            try:
                mission = self._config.get(CONF_MISSION_STATEMENT, "")
                plan = await self._planner.plan_background(
                    mission=mission,
                    preferences=self._memory.get_preferences_text(),
                    memory=self._memory.get_summaries_text(),
                    diff=self._coordinator.format_diff_for_prompt(),
                    snapshot=self._coordinator.format_snapshot_for_prompt(),
                    automations=self._coordinator.format_list_for_prompt("automations"),
                    scenes=self._coordinator.format_list_for_prompt("scenes"),
                    scripts=self._coordinator.format_list_for_prompt("scripts"),
                )
                return await self._execute_plan(plan, user_request=None)
            finally:
                self._running = False

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
                return await self._execute_plan(plan, user_request=user_message)
            finally:
                self._running = False

    async def _execute_plan(
        self,
        plan: AgentPlan,
        *,
        user_request: str | None,
    ) -> RunResult:
        max_actions = self._config.get(CONF_MAX_ACTIONS, 10)
        steps_executed: list[str] = []
        overall_success = True

        if not plan.steps:
            _LOGGER.debug("No action steps in plan: %s", plan.reasoning)
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

        for step in steps_to_run:
            step_success = False
            last_error = ""
            current_states: dict[str, str] = {}

            for attempt in range(MAX_RETRIES):
                try:
                    await self._executor.execute_step(step)
                    result = await self._verifier.verify_step(step)
                    if result.success:
                        step_success = True
                        steps_executed.append(self._executor.describe_step(step))
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

        outcome = "success" if overall_success else f"partial/failed: {last_error if not overall_success else 'ok'}"
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
