"""Config flow for Home Assistant Agent."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ASSIST_SATELLITE,
    CONF_ENTITY_EXCLUDE,
    CONF_ENTITY_INCLUDE,
    CONF_MAX_ACTIONS,
    CONF_MISSION_STATEMENT,
    CONF_MODEL,
    CONF_NOTIFY_SERVICES,
    CONF_NUM_CTX,
    CONF_OLLAMA_URL,
    CONF_POLL_INTERVAL,
    CONF_TEMPERATURE,
    CONF_WYOMING_PORT,
    DEFAULT_MAX_ACTIONS,
    DEFAULT_MISSION_STATEMENT,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_URL,
    DEFAULT_POLL_INTERVAL,
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
    return result


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
        }
    )


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
            client = OllamaClient(
                self._ollama_url,
                user_input[CONF_MODEL],
                temperature=user_input[CONF_TEMPERATURE],
                num_ctx=user_input[CONF_NUM_CTX],
                session=async_get_clientsession(self.hass),
            )
            if not await client.health_check():
                errors["base"] = "cannot_connect"
            elif user_input[CONF_MODEL] not in self._models:
                errors["base"] = "model_not_found"
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return HomeAssistantAgentOptionsFlow(config_entry)


class HomeAssistantAgentOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._models: list[str] = []
        self._ollama_url: str = ""
        self._defaults: dict = {}

    async def async_step_init(self, user_input=None):
        """Step 1: Ollama URL (re-validate and refresh model list)."""
        data = {**self._config_entry.data, **self._config_entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            client = OllamaClient(
                user_input[CONF_OLLAMA_URL],
                data.get(CONF_MODEL, DEFAULT_MODEL),
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
                    self._defaults = data
                    return await self.async_step_agent()

        schema = vol.Schema(
            {
                vol.Required(CONF_OLLAMA_URL, default=data.get(CONF_OLLAMA_URL)): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_agent(self, user_input=None):
        """Step 2: update agent settings with model picker."""
        defaults = getattr(self, "_defaults", {**self._config_entry.data, **self._config_entry.options})

        if user_input is not None:
            user_input = {**user_input, CONF_OLLAMA_URL: self._ollama_url}
            return self.async_create_entry(
                title="",
                data=_normalize_entry({**defaults, **user_input}),
            )

        return self.async_show_form(
            step_id="agent",
            data_schema=_agent_settings_schema(self._models, defaults),
        )
