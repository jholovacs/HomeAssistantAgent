"""Update platform for Home Assistant Agent."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_RELEASE_CHECK_INTERVAL, DOMAIN
from .releases.github import GitHubRelease, fetch_latest_release, version_is_newer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the update entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ReleaseUpdateCoordinator = data["release_coordinator"]
    async_add_entities([HomeAssistantAgentUpdateEntity(entry, coordinator)])


class ReleaseUpdateCoordinator(DataUpdateCoordinator[GitHubRelease | None]):
    """Poll GitHub for the latest integration release."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        installed_version: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_release",
            update_interval=timedelta(seconds=DEFAULT_RELEASE_CHECK_INTERVAL),
        )
        self._session = session
        self._installed_version = installed_version

    @property
    def installed_version(self) -> str:
        """Return the currently installed integration version."""
        return self._installed_version

    async def _async_update_data(self) -> GitHubRelease | None:
        release = await fetch_latest_release(self._session)
        if release is None:
            raise UpdateFailed("Unable to fetch latest GitHub release")
        return release


class HomeAssistantAgentUpdateEntity(CoordinatorEntity[ReleaseUpdateCoordinator], UpdateEntity):
    """Report integration update availability and release notes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = "Integration update"
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _attr_title = "Home Assistant Agent"

    def __init__(self, entry: ConfigEntry, coordinator: ReleaseUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_update"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Home Assistant Agent",
            "manufacturer": "Home Assistant Agent",
        }

    @property
    def installed_version(self) -> str | None:
        return self.coordinator.installed_version

    @property
    def latest_version(self) -> str | None:
        release = self.coordinator.data
        return release.version if release else None

    @property
    def release_summary(self) -> str | None:
        release = self.coordinator.data
        return release.summary if release else None

    @property
    def release_url(self) -> str | None:
        release = self.coordinator.data
        return release.url if release else None

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        return version_is_newer(latest_version, installed_version)

    async def async_release_notes(self) -> str | None:
        release = self.coordinator.data
        if not release or not release.body:
            return None
        return release.body

    @property
    def available(self) -> bool:
        release = self.coordinator.data
        if release is None:
            return False
        return version_is_newer(release.version, self.coordinator.installed_version)
