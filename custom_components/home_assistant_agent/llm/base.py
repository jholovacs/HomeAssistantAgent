"""LLM client protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the LLM server is reachable."""

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Return available model names."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion and return the assistant message content."""

    @abstractmethod
    async def summarize(self, text: str) -> str:
        """Compress text into a short summary."""
