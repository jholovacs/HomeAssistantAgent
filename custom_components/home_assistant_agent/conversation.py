"""Conversation platform for Home Assistant Agent."""

from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.intent import IntentResponse

from .agent.loop import AgentLoop
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HomeAssistantAgentConversationEntity(entry, data["agent_loop"])])


class HomeAssistantAgentConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Conversation agent powered by the autonomous agent loop."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry, agent_loop: AgentLoop) -> None:
        self._entry = entry
        self._agent_loop = agent_loop
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Home Assistant Agent",
            "manufacturer": "Home Assistant Agent",
        }

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register as a conversation agent when the entity is added."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)
        _LOGGER.info(
            "Registered conversation agent (entity: %s, agent_id: %s)",
            self.entity_id,
            self._entry.entry_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the conversation agent."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process user input through the agent loop."""
        intent_response = IntentResponse(language=user_input.language)

        try:
            result = await self._agent_loop.run_conversation(user_input.text)
            speech = result.response_text or "Done."
            intent_response.async_set_speech(speech)
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=user_input.agent_id,
                    content=speech,
                )
            )
        except Exception as err:
            _LOGGER.exception("Conversation processing failed: %s", err)
            speech = "Sorry, I encountered an error processing your request."
            intent_response.async_set_speech(speech)
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=user_input.agent_id,
                    content=speech,
                )
            )

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )
