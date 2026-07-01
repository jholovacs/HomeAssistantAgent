"""Summarize agent activity via LLM."""

from __future__ import annotations

import logging

from ..llm.base import LLMClient

_LOGGER = logging.getLogger(__name__)


class MemorySummarizer:
    """Compresses raw agent runs into short memory entries."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def summarize_run(
        self,
        *,
        reasoning: str,
        steps_taken: list[str],
        outcome: str,
        user_request: str | None = None,
    ) -> str:
        """Produce a 1-2 sentence summary of an agent run."""
        parts = []
        if user_request:
            parts.append(f"User request: {user_request}")
        parts.append(f"Reasoning: {reasoning}")
        if steps_taken:
            parts.append("Actions: " + "; ".join(steps_taken))
        parts.append(f"Outcome: {outcome}")
        raw = "\n".join(parts)

        try:
            return await self._llm.summarize(raw)
        except Exception as err:
            _LOGGER.warning("Failed to summarize via LLM: %s", err)
            if steps_taken:
                return f"Executed: {'; '.join(steps_taken[:3])}. {outcome}"
            return outcome or reasoning[:200]
