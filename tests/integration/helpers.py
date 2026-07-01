"""Helpers for Docker-based Home Assistant integration tests."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import aiohttp

HA_URL = os.environ.get("HA_URL", "http://127.0.0.1:8123").rstrip("/")
HA_WS_URL = os.environ.get("HA_WS_URL", HA_URL.replace("http", "ws") + "/api/websocket")
VLLM_MOCK_URL = os.environ.get("VLLM_MOCK_URL", "http://127.0.0.1:8000").rstrip("/")
WYOMING_HOST = os.environ.get("WYOMING_HOST", "127.0.0.1")
WYOMING_PORT = int(os.environ.get("WYOMING_PORT", "10500"))
TEST_USERNAME = os.environ.get("HA_TEST_USERNAME", "integration")
TEST_PASSWORD = os.environ.get("HA_TEST_PASSWORD", "integration-test")
TEST_CLIENT_ID = "https://home-assistant-agent.test/integration"
TEST_REDIRECT_URI = "https://home-assistant-agent.test/integration/callback"
TEST_MODEL = "test-model"
TEST_ENTITY = "input_boolean.agent_test_switch"
INTEGRATION_DOMAIN = "home_assistant_agent"


class HaApiError(RuntimeError):
    """Raised when a Home Assistant API call fails."""


async def wait_for_url(
    url: str,
    *,
    timeout: float = 300,
    interval: float = 2,
) -> None:
    """Wait until an HTTP endpoint responds."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    async with aiohttp.ClientSession() as session:
        while time.monotonic() < deadline:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status < 500:
                        return
            except Exception as err:
                last_error = err
            await asyncio.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _parse_onboarding_raw(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list) and raw and isinstance(raw[0], str):
        return [{"step": step, "done": False} for step in raw]
    return raw


def _pending_onboarding_steps(raw: Any) -> list[str]:
    return [item["step"] for item in _parse_onboarding_raw(raw) if not item.get("done")]


def _onboarding_complete(raw: Any) -> bool:
    parsed = _parse_onboarding_raw(raw)
    return not parsed or not _pending_onboarding_steps(parsed)


async def wait_for_onboarding(session: aiohttp.ClientSession) -> Any:
    """Wait until the onboarding API is available and return its payload."""
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            async with session.get(
                f"{HA_URL}/api/onboarding",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        await asyncio.sleep(2)
    raise TimeoutError("Timed out waiting for Home Assistant onboarding API")


async def get_onboarding_raw(session: aiohttp.ClientSession) -> Any:
    async with session.get(f"{HA_URL}/api/onboarding") as resp:
        resp.raise_for_status()
        return await resp.json()


async def _exchange_auth_code(session: aiohttp.ClientSession, code: str) -> str:
    async with session.post(
        f"{HA_URL}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": TEST_CLIENT_ID,
        },
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise HaApiError(f"Token exchange failed ({resp.status}): {body}")
        payload = await resp.json()
        return payload["access_token"]


async def complete_onboarding(session: aiohttp.ClientSession) -> str | None:
    """Finish HA first-run onboarding. Returns token if created during onboarding."""
    raw = await wait_for_onboarding(session)
    if _onboarding_complete(raw):
        return None

    token: str | None = None
    auth_headers: dict[str, str] = {}

    pending = _pending_onboarding_steps(raw)
    if "user" in pending:
        async with session.post(
            f"{HA_URL}/api/onboarding/users",
            json={
                "name": "Integration Tester",
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
                "language": "en",
                "client_id": TEST_CLIENT_ID,
            },
        ) as resp:
            if resp.status == 400:
                body = await resp.json()
                if body.get("message") != "User already exists":
                    resp.raise_for_status()
            else:
                resp.raise_for_status()
                data = await resp.json()
                token = await _exchange_auth_code(session, data["auth_code"])
                auth_headers = {"Authorization": f"Bearer {token}"}

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        raw = await get_onboarding_raw(session)
        if _onboarding_complete(raw):
            return token

        pending = _pending_onboarding_steps(raw)
        if not auth_headers:
            token = await get_access_token(session)
            auth_headers = {"Authorization": f"Bearer {token}"}

        if "core_config" in pending:
            async with session.post(
                f"{HA_URL}/api/onboarding/core_config",
                headers=auth_headers,
                json={
                    "latitude": 45.0,
                    "longitude": -93.0,
                    "elevation": 0,
                    "unit_system": "metric",
                    "time_zone": "UTC",
                },
            ) as resp:
                resp.raise_for_status()
            continue

        if "analytics" in pending:
            async with session.post(
                f"{HA_URL}/api/onboarding/analytics",
                headers=auth_headers,
                json={"analytics": False},
            ) as resp:
                resp.raise_for_status()
            continue

        if "integration" in pending:
            async with session.post(
                f"{HA_URL}/api/onboarding/integration",
                headers=auth_headers,
                json={
                    "client_id": TEST_CLIENT_ID,
                    "redirect_uri": TEST_REDIRECT_URI,
                },
            ) as resp:
                resp.raise_for_status()
            continue

        await asyncio.sleep(2)

    raise TimeoutError("Home Assistant onboarding did not complete in time")


async def get_access_token(session: aiohttp.ClientSession) -> str:
    """Obtain an access token via the HA login flow."""
    last_error = ""
    for _attempt in range(10):
        try:
            return await _login_for_access_token(session)
        except HaApiError as err:
            last_error = str(err)
            if "invalid_auth" not in last_error:
                raise
            await asyncio.sleep(3)
    raise HaApiError(f"Login failed after retries: {last_error}")


async def _login_for_access_token(session: aiohttp.ClientSession) -> str:
    async with session.post(
        f"{HA_URL}/auth/login_flow",
        json={
            "client_id": TEST_CLIENT_ID,
            "redirect_uri": TEST_REDIRECT_URI,
            "handler": ["homeassistant", None],
        },
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise HaApiError(f"Login flow start failed ({resp.status}): {body}")
        flow = await resp.json()

    flow_id = flow["flow_id"]
    async with session.post(
        f"{HA_URL}/auth/login_flow/{flow_id}",
        json={
            "client_id": TEST_CLIENT_ID,
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise HaApiError(f"Login flow submit failed ({resp.status}): {body}")
        result = await resp.json()

    if result.get("type") != "create_entry":
        raise HaApiError(f"Unexpected login flow result: {result}")

    code = result["result"]["code"]
    async with session.post(
        f"{HA_URL}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": TEST_CLIENT_ID,
        },
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise HaApiError(f"Token request failed ({resp.status}): {body}")
        payload = await resp.json()
        return payload["access_token"]


async def ws_send(ws: aiohttp.ClientWebSocketResponse, msg: dict[str, Any]) -> dict[str, Any]:
    """Send a WebSocket message and wait for the matching response."""
    await ws.send_json(msg)
    msg_id = msg["id"]
    while True:
        raw = await ws.receive()
        if raw.type != aiohttp.WSMsgType.TEXT:
            continue
        data = json.loads(raw.data)
        if data.get("id") == msg_id:
            return data


async def ws_connect(session: aiohttp.ClientSession, token: str) -> aiohttp.ClientWebSocketResponse:
    ws = await session.ws_connect(HA_WS_URL)
    auth_required = await ws.receive_json()
    if auth_required.get("type") != "auth_required":
        raise HaApiError(f"Unexpected WS greeting: {auth_required}")
    await ws.send_json({"type": "auth", "access_token": token})
    auth_result = await ws.receive_json()
    if auth_result.get("type") != "auth_ok":
        raise HaApiError(f"WebSocket auth failed: {auth_result}")
    return ws


async def get_config_entries(session: aiohttp.ClientSession, token: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(f"{HA_URL}/api/config/config_entries/entry", headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()


async def delete_config_entry(
    session: aiohttp.ClientSession,
    token: str,
    entry_id: str,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with session.delete(
        f"{HA_URL}/api/config/config_entries/entry/{entry_id}",
        headers=headers,
    ) as resp:
        resp.raise_for_status()


async def setup_integration_via_flow(
    session: aiohttp.ClientSession,
    token: str,
    *,
    vllm_url: str,
) -> str:
    """Create the integration via REST config flow; return entry_id."""
    headers = {"Authorization": f"Bearer {token}"}

    existing = await get_config_entries(session, token)
    for entry in existing:
        if entry.get("domain") == INTEGRATION_DOMAIN:
            await delete_config_entry(session, token, entry["entry_id"])

    agent_input = {
        "model": TEST_MODEL,
        "mission_statement": "Turn on the test switch when asked.",
        "poll_interval": 3600,
        "wyoming_port": WYOMING_PORT,
        "notify_services": "persistent_notification",
        "assist_satellite": "",
        "entity_include": "input_boolean.*",
        "entity_exclude": "",
        "max_actions_per_cycle": 5,
        "temperature": 0.1,
        "num_ctx": 4096,
    }

    last_error = ""
    for _attempt in range(12):
        try:
            async with session.post(
                f"{HA_URL}/api/config/config_entries/flow",
                headers=headers,
                json={"handler": INTEGRATION_DOMAIN},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise HaApiError(f"Flow create failed ({resp.status}): {body}")
                step = await resp.json()

            flow_id = step["flow_id"]

            # Step 1: vLLM URL
            async with session.post(
                f"{HA_URL}/api/config/config_entries/flow/{flow_id}",
                headers=headers,
                json={"vllm_url": vllm_url, "vllm_api_key": ""},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise HaApiError(f"Flow submit (vllm) failed ({resp.status}): {body}")
                step = await resp.json()

            # Step 2: agent settings (if not already complete)
            if step.get("type") == "form":
                async with session.post(
                    f"{HA_URL}/api/config/config_entries/flow/{flow_id}",
                    headers=headers,
                    json=agent_input,
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise HaApiError(f"Flow submit (agent) failed ({resp.status}): {body}")
                    step = await resp.json()

            if step.get("type") != "create_entry":
                raise HaApiError(f"Unexpected flow result: {step}")
            return step["result"]["entry_id"]
        except HaApiError as err:
            last_error = str(err)
            await asyncio.sleep(5)

    raise HaApiError(f"Could not configure {INTEGRATION_DOMAIN}: {last_error}")


async def get_entity_state(
    session: aiohttp.ClientSession,
    token: str,
    entity_id: str,
) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(f"{HA_URL}/api/states/{entity_id}", headers=headers) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data["state"]


async def set_entity_state(
    session: aiohttp.ClientSession,
    token: str,
    entity_id: str,
    state: str,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    service = "turn_off" if state == "off" else "turn_on"
    domain = entity_id.split(".", 1)[0]
    async with session.post(
        f"{HA_URL}/api/services/{domain}/{service}",
        headers=headers,
        json={"entity_id": entity_id},
    ) as resp:
        resp.raise_for_status()


async def find_conversation_agent_id(
    session: aiohttp.ClientSession,
    token: str,
    entry_id: str,
) -> str:
    """Return the agent_id for our config entry (entry_id string)."""
    return entry_id


async def process_conversation(
    session: aiohttp.ClientSession,
    token: str,
    text: str,
    *,
    agent_id: str | None = None,
) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    payload: dict[str, Any] = {"text": text, "language": "en"}
    if agent_id:
        payload["agent_id"] = agent_id
    async with session.post(
        f"{HA_URL}/api/conversation/process",
        headers=headers,
        json=payload,
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    response = data.get("response", {})
    speech = response.get("speech", {})
    plain = speech.get("plain", {})
    return plain.get("speech", "")
