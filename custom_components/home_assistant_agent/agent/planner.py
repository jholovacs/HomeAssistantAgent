"""LLM plan generation and parsing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ..llm.base import LLMClient
from .prompts import (
    BACKGROUND_USER_PROMPT,
    CONVERSATION_USER_PROMPT,
    PLAN_JSON_SCHEMA,
    RETRY_USER_PROMPT,
    SYSTEM_PROMPT,
)
from .tools import is_allowed_service

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single action step in an agent plan."""

    service: str
    target: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentPlan:
    """Structured plan from the LLM."""

    reasoning: str
    steps: list[PlanStep]
    notify_user: bool
    response_text: str
    summary_for_memory: str


class Planner:
    """Assembles prompts and parses LLM plans."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def plan_background(
        self,
        *,
        mission: str,
        preferences: str,
        memory: str,
        diff: str,
        snapshot: str,
        automations: str,
        scenes: str,
        scripts: str,
    ) -> AgentPlan:
        """Generate a plan from periodic background evaluation."""
        system = SYSTEM_PROMPT.format(schema=PLAN_JSON_SCHEMA)
        user = BACKGROUND_USER_PROMPT.format(
            mission=mission,
            preferences=preferences or "None recorded.",
            memory=memory,
            diff=diff,
            snapshot=snapshot,
            automations=automations,
            scenes=scenes,
            scripts=scripts,
        )
        return await self._request_plan(system, user)

    async def plan_conversation(
        self,
        *,
        mission: str,
        preferences: str,
        memory: str,
        user_message: str,
        snapshot: str,
    ) -> AgentPlan:
        """Generate a plan from a user conversation."""
        system = SYSTEM_PROMPT.format(schema=PLAN_JSON_SCHEMA)
        user = CONVERSATION_USER_PROMPT.format(
            mission=mission,
            preferences=preferences or "None recorded.",
            memory=memory,
            user_message=user_message,
            snapshot=snapshot,
        )
        return await self._request_plan(system, user)

    async def plan_retry(
        self,
        *,
        mission: str,
        failed_step: dict[str, Any],
        error: str,
        current_state: str,
    ) -> AgentPlan:
        """Generate a revised plan after verification failure."""
        system = SYSTEM_PROMPT.format(schema=PLAN_JSON_SCHEMA)
        user = RETRY_USER_PROMPT.format(
            failed_step=json.dumps(failed_step),
            error=error,
            current_state=current_state,
        )
        user = f"Mission: {mission}\n\n{user}"
        return await self._request_plan(system, user)

    async def _request_plan(self, system: str, user: str) -> AgentPlan:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        content = await self._llm.chat(messages, json_mode=True)
        return self._parse_plan(content)

    def _parse_plan(self, content: str) -> AgentPlan:
        """Parse and validate LLM JSON output."""
        try:
            if hasattr(self._llm, "parse_json_response"):
                data = self._llm.parse_json_response(content)  # type: ignore[attr-defined]
            else:
                data = json.loads(content.strip())
        except (json.JSONDecodeError, AttributeError) as err:
            _LOGGER.warning("Invalid plan JSON: %s — content: %s", err, content[:500])
            return AgentPlan(
                reasoning="Failed to parse LLM response.",
                steps=[],
                notify_user=False,
                response_text="I had trouble processing that request.",
                summary_for_memory="Plan parse failure.",
            )

        steps: list[PlanStep] = []
        for raw_step in data.get("steps", []):
            service = raw_step.get("service", "")
            if not is_allowed_service(service):
                _LOGGER.warning("Blocked disallowed service: %s", service)
                continue
            steps.append(
                PlanStep(
                    service=service,
                    target=raw_step.get("target") or {},
                    data=raw_step.get("data") or {},
                    expected=raw_step.get("expected") or {},
                )
            )

        return AgentPlan(
            reasoning=data.get("reasoning", ""),
            steps=steps,
            notify_user=bool(data.get("notify_user", False)),
            response_text=data.get("response_text", ""),
            summary_for_memory=data.get("summary_for_memory", ""),
        )
