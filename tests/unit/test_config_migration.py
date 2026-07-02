"""Tests for legacy Ollama config migration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.const import (
    CONF_MODEL,
    CONF_VLLM_REQUEST_TIMEOUT,
    CONF_VLLM_URL,
    DEFAULT_MODEL,
    DEFAULT_VLLM_URL,
    migrate_legacy_config,
)


def test_migrate_legacy_ollama_keys():
    data = {
        "ollama_url": "http://192.168.1.10:11434",
        "ollama_request_timeout": 900,
        "ollama_keep_alive": "30m",
        "model": "qwen2.5:7b-instruct",
    }
    migrated = migrate_legacy_config(data)
    assert migrated[CONF_VLLM_URL] == "http://192.168.1.10:8000"
    assert migrated[CONF_VLLM_REQUEST_TIMEOUT] == 900
    assert migrated[CONF_MODEL] == DEFAULT_MODEL
    assert "ollama_url" not in migrated
    assert "ollama_keep_alive" not in migrated


def test_migrate_adds_defaults_for_missing_keys():
    migrated = migrate_legacy_config({})
    assert migrated[CONF_VLLM_URL] == DEFAULT_VLLM_URL
    assert migrated[CONF_MODEL] == DEFAULT_MODEL
