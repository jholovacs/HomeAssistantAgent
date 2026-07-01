"""Tests for checkpoint persistence."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.planner import AgentPlan, PlanStep
from home_assistant_agent.memory.checkpoint import CheckpointStore


@pytest.fixture
def checkpoint_store():
    hass = MagicMock()
    store = CheckpointStore(hass, "test-entry")
    store._store.async_save = AsyncMock()
    return store


@pytest.mark.asyncio
async def test_begin_run_and_has_pending(checkpoint_store):
    plan = AgentPlan(
        reasoning="Test plan",
        steps=[PlanStep(service="light.turn_on", target={"entity_id": "light.kitchen"})],
        notify_user=False,
        response_text="",
        summary_for_memory="",
    )
    await checkpoint_store.begin_run(plan, run_type="background", user_request=None)
    assert checkpoint_store.has_pending()
    snapshot = checkpoint_store.get_snapshot()
    assert snapshot is not None
    assert len(snapshot["pending_steps"]) == 1
    assert snapshot["completed_steps"] == []


@pytest.mark.asyncio
async def test_record_step_done_updates_pending(checkpoint_store):
    plan = AgentPlan(
        reasoning="Test plan",
        steps=[
            PlanStep(service="light.turn_on", target={"entity_id": "light.kitchen"}),
            PlanStep(service="switch.turn_on", target={"entity_id": "switch.pump"}),
        ],
        notify_user=False,
        response_text="",
        summary_for_memory="",
    )
    await checkpoint_store.begin_run(plan, run_type="background", user_request=None)
    await checkpoint_store.record_step_done(
        "light.turn_on on light.kitchen",
        [plan.steps[1]],
    )
    snapshot = checkpoint_store.get_snapshot()
    assert snapshot["completed_steps"] == ["light.turn_on on light.kitchen"]
    assert len(snapshot["pending_steps"]) == 1
    assert snapshot["pending_steps"][0]["service"] == "switch.turn_on"


@pytest.mark.asyncio
async def test_to_plan_rebuilds_remaining_steps(checkpoint_store):
    plan = AgentPlan(
        reasoning="Resume me",
        steps=[PlanStep(service="scene.turn_on", target={"entity_id": "scene.movie"})],
        notify_user=True,
        response_text="Continuing",
        summary_for_memory="Interrupted",
    )
    await checkpoint_store.begin_run(plan, run_type="conversation", user_request="start movie")
    rebuilt = checkpoint_store.to_plan()
    assert rebuilt is not None
    assert rebuilt.reasoning == "Resume me"
    assert rebuilt.steps[0].service == "scene.turn_on"


@pytest.mark.asyncio
async def test_clear_removes_pending(checkpoint_store):
    plan = AgentPlan(
        reasoning="Done",
        steps=[PlanStep(service="light.turn_off", target={"entity_id": "light.kitchen"})],
        notify_user=False,
        response_text="",
        summary_for_memory="",
    )
    await checkpoint_store.begin_run(plan, run_type="background", user_request=None)
    await checkpoint_store.clear()
    assert not checkpoint_store.has_pending()
