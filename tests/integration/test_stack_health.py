"""Docker stack health checks."""

import pytest
from wyoming.client import AsyncClient
from wyoming.handle import Handled, NotHandled
from wyoming.info import Describe, Info
from wyoming.intent import Recognize
from wyoming.ping import Ping, Pong

from .helpers import HA_URL, VLLM_MOCK_URL, WYOMING_HOST, WYOMING_PORT, wait_for_url

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_home_assistant_api_is_up(integration_stack):
    await wait_for_url(f"{HA_URL}/api/")


@pytest.mark.asyncio
async def test_vllm_mock_is_up(integration_stack):
    await wait_for_url(f"{VLLM_MOCK_URL}/health")


@pytest.mark.asyncio
async def test_integration_config_entry_exists(integration_entry):
    _session, _token, entry_id = integration_entry
    assert entry_id


@pytest.mark.asyncio
async def test_wyoming_describe_and_ping(integration_entry):
    _session, _token, _entry_id = integration_entry
    uri = f"tcp://{WYOMING_HOST}:{WYOMING_PORT}"
    async with AsyncClient.from_uri(uri) as client:
        await client.write_event(Describe().event())
        event = await client.read_event()
        assert Info.is_type(event.type)
        info = Info.from_event(event)
        assert info.handle

        await client.write_event(Ping(text="test").event())
        event = await client.read_event()
        assert Pong.is_type(event.type)


@pytest.mark.asyncio
async def test_wyoming_recognize_returns_handled(integration_entry):
    _session, _token, _entry_id = integration_entry
    uri = f"tcp://{WYOMING_HOST}:{WYOMING_PORT}"
    async with AsyncClient.from_uri(uri) as client:
        await client.write_event(
            Recognize(text="turn on agent test switch").event()
        )
        while True:
            event = await client.read_event()
            if event is None:
                pytest.fail("Wyoming client disconnected before response")
            if Handled.is_type(event.type):
                handled = Handled.from_event(event)
                assert handled.text
                return
            if NotHandled.is_type(event.type):
                pytest.fail(f"Wyoming not handled: {NotHandled.from_event(event).text}")
