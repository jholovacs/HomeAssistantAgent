"""Tests for plan step execution."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.executor import Executor
from home_assistant_agent.agent.planner import PlanStep


@pytest.mark.asyncio
async def test_execute_step_rejects_missing_entity():
    hass = MagicMock()
    hass.services.has_service.return_value = True
    hass.services.async_call = AsyncMock()
    hass.states.get.return_value = None
    executor = Executor(hass, {})

    step = PlanStep(
        service="climate.set_fan_mode",
        target={"entity_id": "climate.office_fan"},
        data={"fan_mode": "on"},
        expected={"entity_id": "climate.office_fan", "state": "cool"},
    )

    with pytest.raises(ValueError, match="Entity not found"):
        await executor.execute_step(step)

    hass.services.async_call.assert_not_called()
