"""Home Assistant Agent services."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, SERVICE_RESUME

if TYPE_CHECKING:
    from .agent.loop import AgentLoop

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant, entry_id: str, agent_loop: AgentLoop) -> None:
    """Register integration services."""

    async def handle_resume(call: ServiceCall) -> None:
        await agent_loop.run_resume(reason="service")

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME,
        handle_resume,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    hass.services.async_remove(DOMAIN, SERVICE_RESUME)


def async_register_startup_resume(
    hass: HomeAssistant,
    entry,
    agent_loop: AgentLoop,
    *,
    resume_on_startup: bool,
) -> None:
    """Resume interrupted runs when Home Assistant finishes starting."""

    async def _on_homeassistant_started(_event) -> None:
        if not resume_on_startup:
            return
        if not agent_loop._checkpoint.has_pending():
            return
        _LOGGER.info("Home Assistant started with a pending agent checkpoint; resuming")
        await _safe_resume(agent_loop, reason="startup")

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, _on_homeassistant_started)
    )


async def _safe_resume(agent_loop: AgentLoop, *, reason: str) -> None:
    try:
        await agent_loop.run_resume(reason=reason)
    except Exception as err:
        _LOGGER.exception("Agent resume failed: %s", err)
