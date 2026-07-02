"""Tests for config entry migration in __init__.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent import async_migrate_entry
from home_assistant_agent.const import CONF_MODEL, CONF_VLLM_URL, DEFAULT_MODEL


@pytest.mark.asyncio
async def test_async_migrate_entry_upgrades_ollama_config():
    entry = MagicMock()
    entry.version = 1
    entry.data = {
        "ollama_url": "http://192.168.1.10:11434",
        "model": "qwen2.5:7b-instruct",
    }

    hass = MagicMock()
    assert await async_migrate_entry(hass, entry) is True

    updated = hass.config_entries.async_update_entry.call_args
    data = updated.kwargs["data"]
    assert data[CONF_VLLM_URL] == "http://192.168.1.10:8000"
    assert data[CONF_MODEL] == DEFAULT_MODEL
    assert updated.kwargs["version"] == 2


@pytest.mark.asyncio
async def test_async_migrate_entry_rejects_future_version():
    entry = MagicMock()
    entry.version = 3
    entry.data = {}

    hass = MagicMock()
    assert await async_migrate_entry(hass, entry) is False
    hass.config_entries.async_update_entry.assert_not_called()
