"""Tests for Ollama JSON parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.llm.ollama import OllamaClient


def test_parse_json_strips_markdown_fences():
    client = OllamaClient("http://localhost:11434", "test")
    content = """```json
{"reasoning": "ok", "steps": []}
```"""
    data = client.parse_json_response(content)
    assert data["reasoning"] == "ok"


def test_parse_plain_json():
    client = OllamaClient("http://localhost:11434", "test")
    data = client.parse_json_response('{"steps": []}')
    assert data["steps"] == []
