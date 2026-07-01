"""Tests for vLLM timeout handling."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.planner import Planner
from home_assistant_agent.llm.errors import LLMTimeoutError
from home_assistant_agent.llm.vllm import VllmClient


@pytest.mark.asyncio
async def test_chat_raises_timeout_error():
    client = VllmClient(
        "http://localhost:8000",
        "test-model",
        request_timeout=120,
        session=MagicMock(),
    )

    mock_session = AsyncMock()
    mock_session.post = MagicMock(side_effect=TimeoutError())
    client._session = mock_session

    with pytest.raises(LLMTimeoutError):
        await client.chat([{"role": "user", "content": "hello"}])


@pytest.mark.asyncio
async def test_planner_returns_safe_plan_on_timeout():
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=LLMTimeoutError("timed out"))
    planner = Planner(llm, {})

    plan = await planner._request_plan("system", "user")

    assert plan.steps == []
    assert "timed out" in plan.reasoning.lower() or "failed" in plan.reasoning.lower()
    assert plan.response_text
