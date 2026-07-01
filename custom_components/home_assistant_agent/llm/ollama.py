"""Ollama HTTP client."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .base import LLMClient

_LOGGER = logging.getLogger(__name__)


class OllamaClient(LLMClient):
    """Client for Ollama's REST API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        temperature: float = 0.3,
        num_ctx: int = 8192,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._num_ctx = num_ctx
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def health_check(self) -> bool:
        """Return True if Ollama is reachable."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Ollama health check failed: %s", err)
            return False

    async def list_models(self) -> list[str]:
        """Return model names from Ollama."""
        session = await self._get_session()
        async with session.get(
            f"{self._base_url}/api/tags",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return [m["name"] for m in data.get("models", [])]

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        """Send chat completion to Ollama."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "num_ctx": self._num_ctx,
            },
        }
        if json_mode:
            payload["format"] = "json"

        session = await self._get_session()
        async with session.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        message = data.get("message", {})
        return message.get("content", "")

    async def summarize(self, text: str) -> str:
        """Compress text into 1-2 sentences."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Summarize the following home automation agent activity in "
                    "1-2 concise sentences. Focus on actions taken and outcomes."
                ),
            },
            {"role": "user", "content": text},
        ]
        return await self.chat(messages, json_mode=False)

    def parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, stripping markdown fences if present."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
