"""Tests for vLLM JSON parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.const import MAX_OUTPUT_TOKEN_CAP
from home_assistant_agent.llm.vllm import VllmClient


def test_parse_json_strips_markdown_fences():
    client = VllmClient("http://localhost:8000", "test")
    content = '```json\n{"reasoning": "ok", "steps": []}\n```'
    data = client.parse_json_response(content)
    assert data["reasoning"] == "ok"


def test_parse_plain_json():
    client = VllmClient("http://localhost:8000", "test")
    data = client.parse_json_response('{"reasoning": "ok", "steps": []}')
    assert data["steps"] == []


def test_max_output_tokens_are_capped():
    client = VllmClient("http://localhost:8000", "test", num_ctx=16384)
    assert client._max_tokens == MAX_OUTPUT_TOKEN_CAP
