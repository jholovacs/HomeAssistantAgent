"""Notification and voice outreach."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_ASSIST_SATELLITE, CONF_NOTIFY_SERVICES

_LOGGER = logging.getLogger(__name__)


class Notifier:
    """Sends notifications via notify services and assist satellites."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self._hass = hass
        self._config = config

    async def notify_significant(self, title: str, message: str) -> None:
        """Notify user through configured channels."""
        services = self._config.get(CONF_NOTIFY_SERVICES) or ["persistent_notification"]
        for service_path in services:
            await self._call_notify(service_path, title, message)

        satellite = self._config.get(CONF_ASSIST_SATELLITE)
        if satellite:
            await self._announce(satellite, message)

    async def _call_notify(self, service_path: str, title: str, message: str) -> None:
        if "." not in service_path:
            domain, service = "notify", service_path
        else:
            domain, service = service_path.split(".", 1)

        if not self._hass.services.has_service(domain, service):
            _LOGGER.debug("Notify service unavailable: %s.%s", domain, service)
            return

        try:
            if domain == "persistent_notification":
                await self._hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {"title": title, "message": message},
                    blocking=True,
                )
            else:
                await self._hass.services.async_call(
                    domain,
                    service,
                    {"title": title, "message": message},
                    blocking=True,
                )
        except Exception as err:
            _LOGGER.warning("Failed to send notification via %s.%s: %s", domain, service, err)

    async def _announce(self, entity_id: str, message: str) -> None:
        if not self._hass.services.has_service("assist_satellite", "announce"):
            _LOGGER.debug("assist_satellite.announce not available")
            return

        try:
            await self._hass.services.async_call(
                "assist_satellite",
                "announce",
                {
                    "message": message,
                    "entity_id": entity_id,
                },
                blocking=True,
            )
        except Exception as err:
            _LOGGER.warning("Failed to announce on %s: %s", entity_id, err)
