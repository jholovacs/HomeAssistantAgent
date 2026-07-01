"""Config flow for Home Assistant Agent."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ADMIN_MODE,
    CONF_ANNOUNCE_RELEASES,
    CONF_ASSIST_SATELLITE,
    CONF_ENTITY_EXCLUDE,
    CONF_ENTITY_INCLUDE,
    CONF_MAX_ACTIONS,
    CONF_MISSION_STATEMENT,
    CONF_MODEL,
    CONF_NOTIFY_SERVICES,
    CONF_NUM_CTX,
    CONF_OLLAMA_KEEP_ALIVE,
    CONF_OLLAMA_REQUEST_TIMEOUT,
    CONF_OLLAMA_URL,
    CONF_POLL_INTERVAL,
    CONF_RESUME_ON_STARTUP,
    CONF_TEMPERATURE,
    CONF_WYOMING_PORT,
    DEFAULT_ADMIN_MODE,
    DEFAULT_ANNOUNCE_RELEASES,
    DEFAULT_MAX_ACTIONS,
    DEFAULT_MISSION_STATEMENT,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_KEEP_ALIVE,
    DEFAULT_OLLAMA_REQUEST_TIMEOUT,
    DEFAULT_OLLAMA_URL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RESUME_ON_STARTUP,
    DEFAULT_TEMPERATURE,
    DEFAULT_WYOMING_PORT,
    DOMAIN,
)
from .llm.ollama import OllamaClient

_LOGGER = logging.getLogger(__name__)

OLLAMA_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OLLAMA_URL, default=DEFAULT_OLLAMA_URL): str,
    }
)


def _parse_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_entry(data: dict) -> dict:
    """Normalize config entry data."""
    result = dict(data)
    result[CONF_NOTIFY_SERVICES] = _parse_list(data.get(CONF_NOTIFY_SERVICES, ""))
    result[CONF_ENTITY_INCLUDE] = _parse_list(data.get(CONF_ENTITY_INCLUDE, ""))
    result[CONF_ENTITY_EXCLUDE] = _parse_list(data.get(CONF_ENTITY_EXCLUDE, ""))
    satellite = data.get(CONF_ASSIST_SATELLITE, "")
    result[CONF_ASSIST_SATELLITE] = satellite.strip() if satellite else None
    result[CONF_ADMIN_MODE] = bool(data.get(CONF_ADMIN_MODE, DEFAULT_ADMIN_MODE))
    result[CONF_RESUME_ON_STARTUP] = bool(
        data.get(CONF_RESUME_ON_STARTUP, DEFAULT_RESUME_ON_STARTUP)
    )
    result[CONF_ANNOUNCE_RELEASES] = bool(
        data.get(CONF_ANNOUNCE_RELEASES, DEFAULT_ANNOUNCE_RELEASES)
    )
    keep_alive = data.get(CONF_OLLAMA_KEEP_ALIVE, DEFAULT_OLLAMA_KEEP_ALIVE)
    result[CONF_OLLAMA_KEEP_ALIVE] = str(keep_alive).strip() or DEFAULT_OLLAMA_KEEP_ALIVE
    result[CONF_OLLAMA_REQUEST_TIMEOUT] = int(
        data.get(CONF_OLLAMA_REQUEST_TIMEOUT, DEFAULT_OLLAMA_REQUEST_TIMEOUT)
    )
    return result


def _entry_config(config_entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return merged config entry data and options."""
    return {**config_entry.data, **config_entry.options}


def _agent_settings_schema(models: list[str], defaults: dict | None = None) -> vol.Schema:
    """Build schema for model selection and agent settings."""
    defaults = defaults or {}
    model_default = defaults.get(CONF_MODEL)
    if model_default not in models:
        model_default = models[0] if models else DEFAULT_MODEL

    return vol.Schema(
        {
            vol.Required(CONF_MODEL, default=model_default): vol.In(models),
            vol.Required(
                CONF_MISSION_STATEMENT,
                default=defaults.get(CONF_MISSION_STATEMENT, DEFAULT_MISSION_STATEMENT),
            ): str,
            vol.Required(
                CONF_POLL_INTERVAL,
                default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            ): cv.positive_int,
            vol.Required(
                CONF_WYOMING_PORT,
                default=defaults.get(CONF_WYOMING_PORT, DEFAULT_WYOMING_PORT),
            ): cv.port,
            vol.Optional(
                CONF_NOTIFY_SERVICES,
                default=",".join(defaults.get(CONF_NOTIFY_SERVICES, ["persistent_notification"])),
            ): str,
            vol.Optional(CONF_ASSIST_SATELLITE, default=defaults.get(CONF_ASSIST_SATELLITE) or ""): str,
            vol.Optional(
                CONF_ENTITY_INCLUDE,
                default=",".join(defaults.get(CONF_ENTITY_INCLUDE, [])),
            ): str,
            vol.Optional(
                CONF_ENTITY_EXCLUDE,
                default=",".join(defaults.get(CONF_ENTITY_EXCLUDE, [])),
            ): str,
            vol.Required(
                CONF_MAX_ACTIONS,
                default=defaults.get(CONF_MAX_ACTIONS, DEFAULT_MAX_ACTIONS),
            ): cv.positive_int,
            vol.Required(
                CONF_TEMPERATURE,
                default=defaults.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=2)),
            vol.Required(
                CONF_NUM_CTX,
                default=defaults.get(CONF_NUM_CTX, DEFAULT_NUM_CTX),
            ): cv.positive_int,
            vol.Optional(
                CONF_OLLAMA_KEEP_ALIVE,
                default=defaults.get(CONF_OLLAMA_KEEP_ALIVE, DEFAULT_OLLAMA_KEEP_ALIVE),
            ): str,
            vol.Required(
                CONF_OLLAMA_REQUEST_TIMEOUT,
                default=defaults.get(
                    CONF_OLLAMA_REQUEST_TIMEOUT, DEFAULT_OLLAMA_REQUEST_TIMEOUT
                ),
            ): cv.positive_int,
            vol.Optional(
                CONF_ADMIN_MODE,
                default=defaults.get(CONF_ADMIN_MODE, DEFAULT_ADMIN_MODE),
            ): bool,
            vol.Optional(
                CONF_RESUME_ON_STARTUP,
                default=defaults.get(CONF_RESUME_ON_STARTUP, DEFAULT_RESUME_ON_STARTUP),
            ): bool,
            vol.Optional(
                CONF_ANNOUNCE_RELEASES,
                default=defaults.get(CONF_ANNOUNCE_RELEASES, DEFAULT_ANNOUNCE_RELEASES),
            ): bool,
        }
    )


def _full_settings_schema(models: list[str], defaults: dict | None = None) -> vol.Schema:
    """Build schema for editing all settings in one form."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_OLLAMA_URL,
                default=defaults.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL),
            ): str,
            **_agent_settings_schema(models, defaults).schema,
        }
    )


async def _discover_models(hass, ollama_url: str, current_model: str) -> tuple[list[str], str | None]:
    """Fetch models from Ollama; return models and optional error key."""
    client = OllamaClient(
        ollama_url,
        current_model or DEFAULT_MODEL,
        session=async_get_clientsession(hass),
    )
    if not await client.health_check():
        return [], "cannot_connect"

    models = await client.list_models()
    if not models:
        return [], "no_models"

    if current_model and current_model not in models:
        models = [current_model, *models]
    return models, None


async def _validate_submission(
    hass,
    user_input: dict[str, Any],
    models: list[str],
) -> str | None:
    """Validate submitted settings; return error key or None."""
    client = OllamaClient(
        user_input[CONF_OLLAMA_URL],
        user_input[CONF_MODEL],
        temperature=user_input[CONF_TEMPERATURE],
        num_ctx=user_input[CONF_NUM_CTX],
        session=async_get_clientsession(hass),
    )
    if not await client.health_check():
        return "cannot_connect"
    if user_input[CONF_MODEL] not in models:
        return "model_not_found"
    return None


class HomeAssistantAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Agent."""

    VERSION = 1

    def __init__(self) -> None:
        self._ollama_url: str = DEFAULT_OLLAMA_URL
        self._models: list[str] = []

    async def async_step_user(self, user_input=None):
        """Step 1: connect to Ollama and discover models."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = OllamaClient(
                user_input[CONF_OLLAMA_URL],
                DEFAULT_MODEL,
                session=async_get_clientsession(self.hass),
            )
            if not await client.health_check():
                errors["base"] = "cannot_connect"
            else:
                self._models = await client.list_models()
                if not self._models:
                    errors["base"] = "no_models"
                else:
                    self._ollama_url = user_input[CONF_OLLAMA_URL]
                    return await self.async_step_agent()

        return self.async_show_form(
            step_id="user",
            data_schema=OLLAMA_STEP_SCHEMA,
            errors=errors,
        )

    async def async_step_agent(self, user_input=None):
        """Step 2: choose model and configure the agent."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**user_input, CONF_OLLAMA_URL: self._ollama_url}
            if error := await _validate_submission(self.hass, user_input, self._models):
                errors["base"] = error
            else:
                self._abort_if_unique_id_configured("single")
                return self.async_create_entry(
                    title="Home Assistant Agent",
                    data=_normalize_entry(user_input),
                    options={},
                )

        return self.async_show_form(
            step_id="agent",
            data_schema=_agent_settings_schema(self._models),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Allow changing all settings after initial setup."""
        entry = self._get_reconfigure_entry()
        defaults = _entry_config(entry)
        errors: dict[str, str] = {}
        ollama_url = (
            user_input.get(CONF_OLLAMA_URL, defaults.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL))
            if user_input
            else defaults.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL)
        )
        models, discover_error = await _discover_models(
            self.hass,
            ollama_url,
            defaults.get(CONF_MODEL, DEFAULT_MODEL),
        )

        if user_input is not None:
            if discover_error:
                errors["base"] = discover_error
            elif error := await _validate_submission(self.hass, user_input, models):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=_normalize_entry(user_input),
                    options={},
                )
        elif discover_error:
            errors["base"] = discover_error

        if not models:
            models = [defaults.get(CONF_MODEL, DEFAULT_MODEL)]

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_full_settings_schema(models, defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return HomeAssistantAgentOptionsFlow()


class HomeAssistantAgentOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    async def async_step_init(self, user_input=None):
        """Show all settings on one form."""
        defaults = _entry_config(self.config_entry)
        errors: dict[str, str] = {}
        ollama_url = (
            user_input.get(CONF_OLLAMA_URL, defaults.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL))
            if user_input
            else defaults.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL)
        )
        models, discover_error = await _discover_models(
            self.hass,
            ollama_url,
            defaults.get(CONF_MODEL, DEFAULT_MODEL),
        )

        if user_input is not None:
            if discover_error:
                errors["base"] = discover_error
            elif error := await _validate_submission(self.hass, user_input, models):
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=_normalize_entry(user_input),
                    options={},
                )
                return self.async_create_entry(data={})

        elif discover_error:
            errors["base"] = discover_error

        if not models:
            models = [defaults.get(CONF_MODEL, DEFAULT_MODEL)]

        return self.async_show_form(
            step_id="init",
            data_schema=_full_settings_schema(models, defaults),
            errors=errors,
        )
