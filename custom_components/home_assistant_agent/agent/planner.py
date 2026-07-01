"""LLM plan generation and parsing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ..const import CONF_ADMIN_MODE
from ..llm.base import LLMClient
from ..llm.errors import LLMRequestError
from .prompts import (
    BACKGROUND_USER_PROMPT,
    CONVERSATION_USER_PROMPT,
    RESUME_USER_PROMPT,
    RETRY_USER_PROMPT,
    build_system_prompt,
)
from .tools import entity_ids_from_step, is_allowed_service

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


def step_to_dict(step: PlanStep) -> dict[str, Any]:
    """Serialize a plan step for checkpoint storage."""
    return {
        "service": step.service,
        "target": step.target,
        "data": step.data,
        "expected": step.expected,
    }


def step_from_dict(data: dict[str, Any]) -> PlanStep:
    """Deserialize a plan step from checkpoint storage."""
    return PlanStep(
        service=data.get("service", ""),
        target=data.get("target") or {},
        data=data.get("data") or {},
        expected=data.get("expected") or {},
    )


def plan_from_checkpoint(data: dict[str, Any]) -> AgentPlan:
    """Rebuild an agent plan from checkpoint data."""
    pending = [step_from_dict(item) for item in data.get("pending_steps", [])]
    return AgentPlan(
        reasoning=data.get("reasoning", ""),
        steps=pending,
        notify_user=bool(data.get("notify_user", False)),
        response_text=data.get("response_text", ""),
        summary_for_memory=data.get("summary_for_memory", ""),
    )


class Planner:
    """Assembles prompts and parses LLM plans."""

    def __init__(self, llm: LLMClient, config: dict[str, Any]) -> None:
        self._llm = llm
        self._config = config

    def _admin_mode(self) -> bool:
        return bool(self._config.get(CONF_ADMIN_MODE, False))

    async def plan_background(
        self,
        *,
        mission: str,
        preferences: str,
        memory: str,
        current_time: str,
        diff: str,
        snapshot: str,
        automations: str,
        scenes: str,
        scripts: str,
        known_entity_ids: frozenset[str] | None = None,
    ) -> AgentPlan:
        """Generate a plan from periodic background evaluation."""
        system = build_system_prompt(admin_mode=self._admin_mode(), mission=mission)
        user = BACKGROUND_USER_PROMPT.format(
            preferences=preferences or "None recorded.",
            memory=memory,
            current_time=current_time,
            diff=diff,
            snapshot=snapshot,
            automations=automations,
            scenes=scenes,
            scripts=scripts,
        )
        return await self._request_plan(system, user, known_entity_ids=known_entity_ids)

    async def plan_conversation(
        self,
        *,
        mission: str,
        preferences: str,
        memory: str,
        user_message: str,
        snapshot: str,
        known_entity_ids: frozenset[str] | None = None,
    ) -> AgentPlan:
        """Generate a plan from a user conversation."""
        system = build_system_prompt(admin_mode=self._admin_mode(), mission=mission)
        user = CONVERSATION_USER_PROMPT.format(
            preferences=preferences or "None recorded.",
            memory=memory,
            user_message=user_message,
            snapshot=snapshot,
        )
        return await self._request_plan(system, user, known_entity_ids=known_entity_ids)

    async def plan_retry(
        self,
        *,
        mission: str,
        failed_step: dict[str, Any],
        error: str,
        current_state: str,
        known_entity_ids: frozenset[str] | None = None,
    ) -> AgentPlan:
        """Generate a revised plan after verification failure."""
        system = build_system_prompt(admin_mode=self._admin_mode(), mission=mission)
        user = RETRY_USER_PROMPT.format(
            failed_step=json.dumps(failed_step),
            error=error,
            current_state=current_state,
        )
        return await self._request_plan(system, user, known_entity_ids=known_entity_ids)

    async def plan_resume(
        self,
        *,
        mission: str,
        memory: str,
        snapshot: str,
        completed_steps: list[str],
        pending_steps: list[PlanStep],
    ) -> AgentPlan:
        """Generate a plan to resume work after an interruption."""
        import json as json_module

        system = build_system_prompt(admin_mode=self._admin_mode(), mission=mission)
        pending_text = json_module.dumps([step_to_dict(step) for step in pending_steps], indent=2)
        completed_text = "\n".join(f"- {step}" for step in completed_steps) or "None"
        user = RESUME_USER_PROMPT.format(
            completed_steps=completed_text,
            pending_steps=pending_text,
            memory=memory,
            snapshot=snapshot,
        )
        return await self._request_plan(system, user)

    async def _request_plan(
        self,
        system: str,
        user: str,
        *,
        known_entity_ids: frozenset[str] | None = None,
    ) -> AgentPlan:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            content = await self._llm.chat(messages, json_mode=True)
        except LLMRequestError as err:
            _LOGGER.warning("LLM plan request failed: %s", err)
            return AgentPlan(
                reasoning="The vLLM request failed or timed out before a plan could be created.",
                steps=[],
                notify_user=False,
                response_text=(
                    "Sorry, the AI model took too long to respond. "
                    "Try again or increase the vLLM request timeout in settings."
                ),
                summary_for_memory="vLLM request failed or timed out.",
            )
        return self._parse_plan(content, known_entity_ids)

    def _step_references_known_entities(
        self,
        raw_step: dict[str, Any],
        known_entity_ids: frozenset[str],
    ) -> bool:
        referenced = entity_ids_from_step(
            target=raw_step.get("target"),
            data=raw_step.get("data"),
            expected=raw_step.get("expected"),
        )
        for entity_id in referenced:
            if entity_id not in known_entity_ids:
                _LOGGER.warning(
                    "Dropping plan step for unknown entity %s (%s)",
                    entity_id,
                    raw_step.get("service"),
                )
                return False
        return True

    def _parse_plan(
        self,
        content: str,
        known_entity_ids: frozenset[str] | None = None,
    ) -> AgentPlan:
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
            if not is_allowed_service(service, admin_mode=self._admin_mode()):
                _LOGGER.warning("Blocked disallowed service: %s", service)
                continue
            if known_entity_ids and not self._step_references_known_entities(
                raw_step, known_entity_ids
            ):
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
