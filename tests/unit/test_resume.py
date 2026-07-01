"""Tests for agent resume behavior."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.loop import AgentLoop
from home_assistant_agent.agent.planner import AgentPlan, PlanStep
from home_assistant_agent.memory.checkpoint import CheckpointStore


def _make_loop(checkpoint: CheckpointStore) -> AgentLoop:
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    coordinator = MagicMock()
    coordinator.format_snapshot_for_prompt.return_value = "snapshot"
    coordinator.format_diff_for_prompt.return_value = "diff"
    coordinator.format_list_for_prompt.return_value = "list"
    planner = MagicMock()
    executor = MagicMock()
    executor.describe_step.return_value = "light.turn_on on light.kitchen"
    verifier = MagicMock()
    memory = MagicMock()
    memory.get_preferences_text.return_value = ""
    memory.get_summaries_text.return_value = ""
    memory.add_entry = AsyncMock()
    summarizer = MagicMock()
    summarizer.summarize_run = AsyncMock(return_value="resumed run")
    notifier = MagicMock()
    notifier.notify_significant = AsyncMock()
    return AgentLoop(
        hass,
        {"mission_statement": "test", "max_actions_per_cycle": 5},
        coordinator,
        planner,
        executor,
        verifier,
        memory,
        summarizer,
        notifier,
        checkpoint,
    )


@pytest.mark.asyncio
async def test_run_background_runs_without_state_changes():
    hass = MagicMock()
    checkpoint = CheckpointStore(hass, "entry")
    checkpoint._store.async_load = AsyncMock(return_value=None)
    loop = _make_loop(checkpoint)
    loop._planner.plan_background = AsyncMock(
        return_value=AgentPlan(
            reasoning="All good",
            steps=[],
            notify_user=False,
            response_text="",
            summary_for_memory="",
        )
    )
    loop._execute_plan = AsyncMock(
        return_value=MagicMock(success=True, steps_executed=[], response_text="")
    )

    await loop.run_background()

    loop._planner.plan_background.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_resume_executes_pending_steps():
    hass = MagicMock()
    checkpoint = CheckpointStore(hass, "entry")
    checkpoint._store.async_save = AsyncMock()
    plan = AgentPlan(
        reasoning="Interrupted",
        steps=[PlanStep(service="light.turn_on", target={"entity_id": "light.kitchen"})],
        notify_user=False,
        response_text="",
        summary_for_memory="",
    )
    await checkpoint.begin_run(plan, run_type="background", user_request=None)

    loop = _make_loop(checkpoint)
    loop._executor.execute_step = AsyncMock()
    loop._verifier.verify_step = AsyncMock(
        return_value=MagicMock(success=True, message="ok", current_states={})
    )

    result = await loop.run_resume(reason="startup")
    assert result is not None
    assert result.success is True
    assert result.steps_executed == ["light.turn_on on light.kitchen"]
    assert not checkpoint.has_pending()
    loop._hass.bus.async_fire.assert_any_call(
        "home_assistant_agent_resume",
        {
            "reason": "startup",
            "pending_steps": 1,
            "completed_steps": 0,
        },
    )


@pytest.mark.asyncio
async def test_run_background_defers_to_resume_when_checkpoint_exists():
    hass = MagicMock()
    checkpoint = CheckpointStore(hass, "entry")
    checkpoint._store.async_save = AsyncMock()
    plan = AgentPlan(
        reasoning="Interrupted",
        steps=[PlanStep(service="switch.turn_on", target={"entity_id": "switch.pump"})],
        notify_user=False,
        response_text="",
        summary_for_memory="",
    )
    await checkpoint.begin_run(plan, run_type="background", user_request=None)

    loop = _make_loop(checkpoint)
    loop.run_resume = AsyncMock(return_value=MagicMock(success=True))
    loop._planner.plan_background = AsyncMock()

    await loop.run_background()
    loop.run_resume.assert_awaited_once_with(reason="checkpoint")
    loop._planner.plan_background.assert_not_awaited()
