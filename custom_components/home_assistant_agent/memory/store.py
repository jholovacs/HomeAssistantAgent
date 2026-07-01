"""Persistent memory store for agent context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import MEMORY_MAX_ENTRIES, STORAGE_KEY, STORAGE_VERSION


class MemoryStore:
    """Stores summarized agent history and user preferences."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{entry_id}",
        )
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any]:
        """Load memory from disk."""
        stored = await self._store.async_load()
        if stored is None:
            self._data = {
                "mission_statement": "",
                "entries": [],
                "user_preferences": {},
            }
        else:
            self._data = stored
        return self._data

    async def async_save(self) -> None:
        """Persist memory to disk."""
        if self._data is not None:
            await self._store.async_save(self._data)

    def set_mission_statement(self, statement: str) -> None:
        """Update the mission statement in memory."""
        if self._data is None:
            self._data = {"mission_statement": "", "entries": [], "user_preferences": {}}
        self._data["mission_statement"] = statement

    def get_mission_statement(self) -> str:
        """Return stored mission statement."""
        if self._data is None:
            return ""
        return self._data.get("mission_statement", "")

    def get_entries(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent memory entries."""
        if self._data is None:
            return []
        entries = self._data.get("entries", [])
        return entries[-limit:]

    def get_summaries_text(self, limit: int = 20) -> str:
        """Format recent entries for prompt injection."""
        entries = self.get_entries(limit)
        if not entries:
            return "No prior agent activity recorded."
        lines = []
        for entry in entries:
            lines.append(f"- [{entry.get('ts', '')}] {entry.get('summary', '')}")
        return "\n".join(lines)

    async def add_entry(
        self,
        summary: str,
        *,
        tags: list[str] | None = None,
    ) -> None:
        """Append a summarized memory entry."""
        if self._data is None:
            await self.async_load()

        assert self._data is not None
        self._data.setdefault("entries", []).append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "tags": tags or [],
            }
        )
        entries = self._data["entries"]
        if len(entries) > MEMORY_MAX_ENTRIES:
            self._data["entries"] = entries[-MEMORY_MAX_ENTRIES:]
        await self.async_save()

    def update_preference(self, key: str, value: str) -> None:
        """Store a user preference extracted from conversation."""
        if self._data is None:
            self._data = {"mission_statement": "", "entries": [], "user_preferences": {}}
        prefs = self._data.setdefault("user_preferences", {})
        prefs[key] = value

    def get_preferences_text(self) -> str:
        """Format user preferences for prompts."""
        if self._data is None:
            return ""
        prefs = self._data.get("user_preferences", {})
        if not prefs:
            return ""
        return "\n".join(f"- {k}: {v}" for k, v in prefs.items())
