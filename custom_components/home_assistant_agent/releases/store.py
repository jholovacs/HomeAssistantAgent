"""Persist which release announcements were already delivered."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from ..const import RELEASE_STORAGE_KEY, RELEASE_STORAGE_VERSION


class ReleaseAnnouncementStore:
    """Tracks announced versions to avoid duplicate notifications."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(
            hass,
            RELEASE_STORAGE_VERSION,
            RELEASE_STORAGE_KEY,
        )
        self._data: dict[str, str | None] = {
            "last_announced_version": None,
            "last_notified_available_version": None,
        }

    async def async_load(self) -> None:
        """Load stored announcement state."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._data.update(stored)

    @callback
    def get_last_announced_version(self) -> str | None:
        """Return the last version announced after upgrade."""
        value = self._data.get("last_announced_version")
        return str(value) if value else None

    @callback
    def get_last_notified_available_version(self) -> str | None:
        """Return the last available update version we notified about."""
        value = self._data.get("last_notified_available_version")
        return str(value) if value else None

    async def async_set_last_announced_version(self, version: str) -> None:
        """Record that the installed version was announced."""
        self._data["last_announced_version"] = version
        await self._store.async_save(self._data)

    async def async_set_last_notified_available_version(self, version: str) -> None:
        """Record that an available update was announced."""
        self._data["last_notified_available_version"] = version
        await self._store.async_save(self._data)
