"""Execute Home Assistant service calls from plan steps."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .planner import PlanStep
from .tools import is_allowed_service

_LOGGER = logging.getLogger(__name__)


class Executor:
    """Maps plan steps to hass.services.async_call."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def execute_step(self, step: PlanStep) -> dict[str, Any]:
        """Execute a single plan step. Returns result metadata."""
        if not is_allowed_service(step.service):
            raise ValueError(f"Service not allowed: {step.service}")

        domain, service = step.service.split(".", 1)
        if not self._hass.services.has_service(domain, service):
            raise ValueError(f"Service does not exist: {step.service}")

        service_data = dict(step.data)
        target = step.target or {}

        _LOGGER.info(
            "Executing %s target=%s data=%s",
            step.service,
            target,
            service_data,
        )

        await self._hass.services.async_call(
            domain,
            service,
            service_data,
            target=target,
            blocking=True,
        )

        entity_ids = self._extract_entity_ids(step)
        return {
            "service": step.service,
            "target": target,
            "data": service_data,
            "entity_ids": entity_ids,
        }

    def _extract_entity_ids(self, step: PlanStep) -> list[str]:
        ids: list[str] = []
        target = step.target or {}
        if "entity_id" in target:
            eid = target["entity_id"]
            if isinstance(eid, str):
                ids.append(eid)
            elif isinstance(eid, list):
                ids.extend(eid)
        expected = step.expected or {}
        eid = expected.get("entity_id")
        if isinstance(eid, str) and eid not in ids:
            ids.append(eid)
        return ids

    def describe_step(self, step: PlanStep) -> str:
        """Human-readable step description."""
        target = step.target.get("entity_id", "") if step.target else ""
        return f"{step.service} on {target}".strip()
