"""Tests for memory store formatting."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.memory.store import MemoryStore


@pytest.fixture
def memory_store():
    hass = MagicMock()
    store = MemoryStore(hass, "test-entry")
    store._data = {
        "mission_statement": "Keep home efficient",
        "entries": [
            {"ts": "2026-01-01T00:00:00+00:00", "summary": "Turned off kitchen light"},
        ],
        "user_preferences": {"bedtime": "22:30"},
    }
    return store


def test_get_summaries_text(memory_store):
    text = memory_store.get_summaries_text()
    assert "kitchen light" in text


def test_get_preferences_text(memory_store):
    text = memory_store.get_preferences_text()
    assert "bedtime" in text
    assert "22:30" in text


@pytest.mark.asyncio
async def test_add_entry_trims_old_entries(memory_store):
    memory_store._store.async_save = AsyncMock()
    memory_store._data["entries"] = [
        {"ts": f"t{i}", "summary": f"entry {i}", "tags": []} for i in range(55)
    ]
    await memory_store.add_entry("new entry")
    assert len(memory_store._data["entries"]) == 50
    assert memory_store._data["entries"][-1]["summary"] == "new entry"
