"""Pytest configuration with Home Assistant stubs for unit tests."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _install_ha_stubs() -> None:
    """Install minimal homeassistant stubs so integration modules can import."""
    if "homeassistant" in sys.modules:
        return

    ha = MagicMock()
    sys.modules["homeassistant"] = ha

    stubs = [
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.helpers",
        "homeassistant.helpers.config_validation",
        "homeassistant.helpers.aiohttp_client",
        "homeassistant.helpers.storage",
        "homeassistant.helpers.typing",
        "homeassistant.helpers.update_coordinator",
        "homeassistant.helpers.intent",
        "homeassistant.components",
        "homeassistant.components.conversation",
    ]
    for name in stubs:
        sys.modules[name] = MagicMock()

    cv = sys.modules["homeassistant.helpers.config_validation"]
    cv.config_entry_only_config_schema = lambda domain: MagicMock()
    cv.positive_int = int
    cv.port = int

    const = sys.modules["homeassistant.const"]
    const.Platform = MagicMock()
    const.MATCH_ALL = "*"

    coordinator_mod = sys.modules["homeassistant.helpers.update_coordinator"]

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, name="", update_interval=None):
            self.hass = hass
            self.data = None

        def __class_getitem__(cls, item):
            return cls

        async def async_config_entry_first_refresh(self):
            return None

        def async_add_listener(self, callback):
            def unsub():
                pass

            return unsub

    coordinator_mod.DataUpdateCoordinator = DataUpdateCoordinator
    coordinator_mod.UpdateFailed = UpdateFailed


_install_ha_stubs()
