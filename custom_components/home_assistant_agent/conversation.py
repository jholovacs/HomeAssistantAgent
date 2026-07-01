"""Home Assistant conversation agent."""

from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .agent.loop import AgentLoop

_LOGGER = logging.getLogger(__name__)


class HomeAssistantAgentConversation(conversation.AbstractConversationAgent):
    """Conversation agent powered by the autonomous agent loop."""

    def __init__(self, entry: ConfigEntry, agent_loop: AgentLoop) -> None:
        self._entry = entry
        self._agent_loop = agent_loop

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process user input through the agent loop."""
        intent_response = intent.IntentResponse(language=user_input.language)

        try:
            result = await self._agent_loop.run_conversation(user_input.text)
            speech = result.response_text or "Done."
            intent_response.async_set_speech(speech)
        except Exception as err:
            _LOGGER.exception("Conversation processing failed: %s", err)
            intent_response.async_set_speech(
                "Sorry, I encountered an error processing your request."
            )

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )


async def async_setup_conversation(
    hass: HomeAssistant,
    entry: ConfigEntry,
    agent_loop: AgentLoop,
) -> None:
    """Register the conversation agent."""
    agent = HomeAssistantAgentConversation(entry, agent_loop)
    conversation.async_set_agent(hass, entry, agent)


async def async_unload_conversation(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unregister the conversation agent."""
    conversation.async_unset_agent(hass, entry)
