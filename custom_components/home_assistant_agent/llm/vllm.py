"""vLLM OpenAI-compatible HTTP client."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from .base import LLMClient
from .errors import LLMRequestError, LLMTimeoutError
from .prompt_log import log_llm_request, log_llm_response

_LOGGER = logging.getLogger(__name__)


class VllmClient(LLMClient):
    """Client for vLLM's OpenAI-compatible REST API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        temperature: float = 0.3,
        num_ctx: int = 8192,
        api_key: str | None = None,
        request_timeout: int = 600,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = num_ctx
        self._api_key = (api_key or "").strip() or None
        self._request_timeout = request_timeout
        self._session = session
        self._owns_session = session is None

    def _api_base(self) -> str:
        if self._base_url.endswith("/v1"):
            return self._base_url
        return f"{self._base_url}/v1"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _chat_timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(
            total=self._request_timeout,
            connect=min(30, self._request_timeout),
            sock_connect=min(30, self._request_timeout),
            sock_read=self._request_timeout,
        )

    def _short_timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(total=10)

    async def health_check(self) -> bool:
        """Return True if the vLLM server is reachable."""
        session = await self._get_session()
        for url in (f"{self._api_base()}/models", f"{self._base_url}/health"):
            try:
                async with session.get(
                    url,
                    headers=self._headers(),
                    timeout=self._short_timeout(),
                ) as resp:
                    if resp.status == 200:
                        return True
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("vLLM health check failed for %s: %s", url, err)
        return False

    async def list_models(self) -> list[str]:
        """Return model IDs served by vLLM."""
        session = await self._get_session()
        async with session.get(
            f"{self._api_base()}/models",
            headers=self._headers(),
            timeout=self._short_timeout(),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return [model["id"] for model in data.get("data", []) if model.get("id")]

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request to vLLM."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        log_llm_request(
            _LOGGER,
            model=self._model,
            messages=messages,
            json_mode=json_mode,
        )

        session = await self._get_session()
        try:
            async with session.post(
                f"{self._api_base()}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self._chat_timeout(),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.warning(
                "vLLM chat timed out after %ss (model=%s, url=%s). "
                "Increase 'vLLM request timeout' in integration settings "
                "or reduce max output tokens.",
                self._request_timeout,
                self._model,
                self._base_url,
            )
            raise LLMTimeoutError(
                f"vLLM chat timed out after {self._request_timeout}s"
            ) from err
        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "vLLM chat request failed (model=%s, url=%s): %s",
                self._model,
                self._base_url,
                err,
            )
            raise LLMRequestError(str(err)) from err

        choices = data.get("choices") or []
        if not choices:
            raise LLMRequestError("vLLM returned no completion choices")

        content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage") or {}
        log_llm_response(
            _LOGGER,
            model=self._model,
            content=content,
            metadata={
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            },
        )
        return content

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
