"""End-to-end agent behavior against Docker Home Assistant."""

from __future__ import annotations

import asyncio
import time

import aiohttp
import pytest

from .helpers import (
    TEST_ENTITY,
    find_conversation_agent_id,
    get_entity_state,
    process_conversation,
    set_entity_state,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_conversation_turns_on_test_switch(integration_entry):
    _session, token, entry_id = integration_entry

    async with aiohttp.ClientSession() as session:
        await set_entity_state(session, token, TEST_ENTITY, "off")
        assert await get_entity_state(session, token, TEST_ENTITY) == "off"

        agent_id = await find_conversation_agent_id(session, token, entry_id)
        speech = await process_conversation(
            session,
            token,
            "Please turn on the agent test switch.",
            agent_id=agent_id,
        )
        assert speech

        deadline = time.monotonic() + 30
        state = "off"
        while time.monotonic() < deadline:
            state = await get_entity_state(session, token, TEST_ENTITY)
            if state == "on":
                return
            await asyncio.sleep(1)

    pytest.fail(f"Expected {TEST_ENTITY} to be on, got {state}")
