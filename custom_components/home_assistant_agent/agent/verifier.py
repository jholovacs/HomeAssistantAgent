"""Verify that plan steps achieved expected outcomes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import VERIFY_DELAY_SECONDS
from .planner import PlanStep

_LOGGER = logging.getLogger(__name__)


class VerificationResult:
    """Result of verifying a plan step."""

    def __init__(
        self,
        success: bool,
        message: str,
        current_states: dict[str, str] | None = None,
    ) -> None:
        self.success = success
        self.message = message
        self.current_states = current_states or {}


class Verifier:
    """Re-reads entity state after actions to confirm success."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def verify_step(self, step: PlanStep) -> VerificationResult:
        """Wait briefly then check expected state."""
        expected = step.expected or {}
        if not expected:
            return VerificationResult(True, "No verification criteria specified.")

        await asyncio.sleep(VERIFY_DELAY_SECONDS)

        entity_id = expected.get("entity_id")
        expected_state = expected.get("state")

        if not entity_id:
            return VerificationResult(True, "No entity_id in expected block.")

        state = self._hass.states.get(entity_id)
        current_states = {entity_id: state.state if state else "unavailable"}

        if state is None:
            return VerificationResult(
                False,
                f"Entity {entity_id} not found.",
                current_states,
            )

        if expected_state is not None and state.state != expected_state:
            return VerificationResult(
                False,
                f"Expected {entity_id}={expected_state}, got {state.state}.",
                current_states,
            )

        for attr_key, attr_val in expected.items():
            if attr_key in ("entity_id", "state"):
                continue
            actual = state.attributes.get(attr_key)
            if actual != attr_val:
                return VerificationResult(
                    False,
                    f"Expected {entity_id}.{attr_key}={attr_val}, got {actual}.",
                    current_states,
                )

        return VerificationResult(True, f"Verified {entity_id}={state.state}.", current_states)

    def format_states(self, states: dict[str, str]) -> str:
        """Format states for retry prompt."""
        return ", ".join(f"{eid}={val}" for eid, val in states.items())
