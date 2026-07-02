"""Tests for notification policy in the agent loop."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.loop import AgentLoop
from home_assistant_agent.agent.planner import AgentPlan, PlanStep


def _make_loop() -> AgentLoop:
    return AgentLoop(
        MagicMock(),
        {},
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )


def test_summary_notification_only_for_background_actions():
    loop = _make_loop()
    assert loop._should_send_summary_notification(
        run_type="background",
        steps_executed=["turned on light.kitchen"],
    )
    assert not loop._should_send_summary_notification(
        run_type="background",
        steps_executed=[],
    )
    assert not loop._should_send_summary_notification(
        run_type="conversation",
        steps_executed=["turned on light.kitchen"],
    )


@pytest.mark.asyncio
async def test_execute_plan_skips_notification_for_conversation():
    loop = _make_loop()
    loop._checkpoint.begin_run = AsyncMock()
    loop._checkpoint.clear = AsyncMock()
    loop._checkpoint.record_step_done = AsyncMock()
    loop._memory.add_entry = AsyncMock()
    loop._summarizer.summarize_run = AsyncMock()
    loop._notifier.notify_significant = AsyncMock()
    loop._executor.execute_step = AsyncMock()
    loop._executor.describe_step = MagicMock(return_value="turned on switch.test")
    loop._verifier.verify_step = AsyncMock(return_value=MagicMock(success=True))

    plan = AgentPlan(
        reasoning="ok",
        steps=[PlanStep(service="switch.turn_on", target={"entity_id": "switch.test"})],
        notify_user=True,
        response_text="Done.",
        summary_for_memory="turned on switch",
    )

    await loop._execute_plan(plan, user_request="turn on test", run_type="conversation")

    loop._notifier.notify_significant.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_notifies_after_background_actions():
    loop = _make_loop()
    loop._checkpoint.begin_run = AsyncMock()
    loop._checkpoint.clear = AsyncMock()
    loop._checkpoint.record_step_done = AsyncMock()
    loop._memory.add_entry = AsyncMock()
    loop._summarizer.summarize_run = AsyncMock()
    loop._notifier.notify_significant = AsyncMock()
    loop._executor.execute_step = AsyncMock()
    loop._executor.describe_step = MagicMock(return_value="turned on switch.test")
    loop._verifier.verify_step = AsyncMock(return_value=MagicMock(success=True))

    plan = AgentPlan(
        reasoning="ok",
        steps=[PlanStep(service="switch.turn_on", target={"entity_id": "switch.test"})],
        notify_user=False,
        response_text="",
        summary_for_memory="turned on switch",
    )

    await loop._execute_plan(plan, user_request=None, run_type="background")

    loop._notifier.notify_significant.assert_called_once()
