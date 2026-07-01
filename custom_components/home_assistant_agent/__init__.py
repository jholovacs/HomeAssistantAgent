"""Home Assistant Agent integration."""

from __future__ import annotations

import logging
from typing import Any

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .agent.executor import Executor
from .agent.loop import AgentLoop
from .agent.planner import Planner
from .agent.verifier import Verifier
from .const import (
    CONF_ANNOUNCE_RELEASES,
    CONF_MISSION_STATEMENT,
    CONF_OLLAMA_KEEP_ALIVE,
    CONF_OLLAMA_REQUEST_TIMEOUT,
    CONF_RESUME_ON_STARTUP,
    CONF_WYOMING_PORT,
    DEFAULT_ANNOUNCE_RELEASES,
    DOMAIN,
)
from .llm.errors import OllamaRequestError
from .coordinator import StateCoordinator
from .llm.ollama import OllamaClient
from .memory.checkpoint import CheckpointStore
from .memory.store import MemoryStore
from .memory.summarizer import MemorySummarizer
from .notify import Notifier
from .releases.store import ReleaseAnnouncementStore
from .services import async_register_startup_resume, async_setup_services, async_unload_services
from .wyoming_server import WyomingServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CONVERSATION, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _merged_config(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Assistant Agent from a config entry."""
    config = _merged_config(entry)

    llm = OllamaClient(
        config["ollama_url"],
        config["model"],
        temperature=config.get("temperature", 0.3),
        num_ctx=config.get("num_ctx", 8192),
        keep_alive=config.get(CONF_OLLAMA_KEEP_ALIVE, "30m"),
        request_timeout=config.get(CONF_OLLAMA_REQUEST_TIMEOUT, 600),
        session=async_get_clientsession(hass),
    )

    memory = MemoryStore(hass, entry.entry_id)
    await memory.async_load()
    memory.set_mission_statement(config.get(CONF_MISSION_STATEMENT, ""))

    checkpoint = CheckpointStore(hass, entry.entry_id)
    await checkpoint.async_load()

    coordinator = StateCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    planner = Planner(llm, config)
    executor = Executor(hass, config)
    verifier = Verifier(hass)
    summarizer = MemorySummarizer(llm)
    notifier = Notifier(hass, config)

    from homeassistant.loader import async_get_integration
    from .releases.announcements import async_handle_release_announcements
    from .update import ReleaseUpdateCoordinator

    integration = await async_get_integration(hass, DOMAIN)
    installed_version = integration.version or "0.0.0"
    session = async_get_clientsession(hass)
    release_coordinator = ReleaseUpdateCoordinator(hass, session, installed_version)
    release_store = ReleaseAnnouncementStore(hass)
    await release_store.async_load()

    agent_loop = AgentLoop(
        hass,
        config,
        coordinator,
        planner,
        executor,
        verifier,
        memory,
        summarizer,
        notifier,
        checkpoint,
    )

    wyoming = WyomingServer(
        agent_loop,
        config.get(CONF_WYOMING_PORT, 10500),
    )
    await wyoming.start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "agent_loop": agent_loop,
        "wyoming": wyoming,
        "llm": llm,
        "memory": memory,
        "checkpoint": checkpoint,
        "release_coordinator": release_coordinator,
        "release_store": release_store,
        "notifier": notifier,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_services(hass, entry.entry_id, agent_loop)
    async_register_startup_resume(
        hass,
        entry,
        agent_loop,
        resume_on_startup=config.get(CONF_RESUME_ON_STARTUP, True),
    )

    try:
        await release_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.debug("Release check skipped on startup: %s", err)

    announce_releases = config.get(CONF_ANNOUNCE_RELEASES, DEFAULT_ANNOUNCE_RELEASES)

    async def _run_release_announcements() -> None:
        try:
            await async_handle_release_announcements(
                session=session,
                notifier=notifier,
                store=release_store,
                installed_version=installed_version,
                announce_releases=announce_releases,
            )
        except Exception as err:
            _LOGGER.debug("Release announcement skipped: %s", err)

    hass.async_create_task(_run_release_announcements())

    @callback
    def _on_release_update() -> None:
        hass.async_create_task(_run_release_announcements())

    entry.async_on_unload(release_coordinator.async_add_listener(_on_release_update))

    @callback
    def _on_coordinator_update() -> None:
        hass.async_create_task(_safe_background_run(agent_loop))

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Home Assistant Agent initialized (Wyoming: %s)", wyoming.uri)
    return True


async def _safe_background_run(agent_loop: AgentLoop) -> None:
    try:
        await agent_loop.run_background()
    except OllamaRequestError as err:
        _LOGGER.warning("Background agent run skipped: %s", err)
    except (TimeoutError, asyncio.TimeoutError) as err:
        _LOGGER.warning("Background agent run timed out: %s", err)
    except Exception as err:
        _LOGGER.exception("Background agent run failed: %s", err)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})

    async_unload_services(hass)

    wyoming: WyomingServer | None = data.get("wyoming")
    if wyoming:
        await wyoming.stop()

    llm: OllamaClient | None = data.get("llm")
    if llm:
        await llm.close()

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
