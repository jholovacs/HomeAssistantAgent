"""Persistent checkpoint for resuming interrupted agent runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..agent.planner import AgentPlan, PlanStep, plan_from_checkpoint, step_from_dict, step_to_dict
from ..const import CHECKPOINT_STORAGE_KEY, CHECKPOINT_STORAGE_VERSION


class CheckpointStore:
    """Stores in-progress agent runs for resume after reboot or interruption."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(
            hass,
            CHECKPOINT_STORAGE_VERSION,
            f"{CHECKPOINT_STORAGE_KEY}_{entry_id}",
        )
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any] | None:
        """Load checkpoint data from disk."""
        self._data = await self._store.async_load()
        return self._data

    async def async_save(self) -> None:
        """Persist checkpoint data."""
        if self._data is not None:
            await self._store.async_save(self._data)

    def has_pending(self) -> bool:
        """Return True when a resumable checkpoint exists."""
        if not self._data:
            return False
        return bool(self._data.get("pending_steps"))

    def get_snapshot(self) -> dict[str, Any] | None:
        """Return a copy of the current checkpoint."""
        if not self._data:
            return None
        return dict(self._data)

    async def begin_run(
        self,
        plan: AgentPlan,
        *,
        run_type: str,
        user_request: str | None,
    ) -> None:
        """Persist a new in-progress run before executing steps."""
        now = datetime.now(timezone.utc).isoformat()
        self._data = {
            "run_type": run_type,
            "user_request": user_request,
            "reasoning": plan.reasoning,
            "notify_user": plan.notify_user,
            "response_text": plan.response_text,
            "summary_for_memory": plan.summary_for_memory,
            "pending_steps": [step_to_dict(step) for step in plan.steps],
            "completed_steps": [],
            "started_at": now,
            "updated_at": now,
        }
        await self.async_save()

    async def record_step_done(self, description: str, remaining_steps: list[PlanStep]) -> None:
        """Update checkpoint after a successful step."""
        if self._data is None:
            return
        self._data.setdefault("completed_steps", []).append(description)
        self._data["pending_steps"] = [step_to_dict(step) for step in remaining_steps]
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self.async_save()

    def to_plan(self) -> AgentPlan | None:
        """Rebuild an AgentPlan from the stored checkpoint."""
        if not self.has_pending() or self._data is None:
            return None
        return plan_from_checkpoint(self._data)

    async def clear(self) -> None:
        """Remove any stored checkpoint."""
        self._data = None
        await self._store.async_save({})
