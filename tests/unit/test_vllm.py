"""Tests for vLLM JSON parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

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
