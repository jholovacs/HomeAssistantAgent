"""Fixtures for Docker integration tests.

The Docker stack must be started before running these tests, e.g.:

    bash scripts/run_integration_tests.sh

or:

    docker compose -f docker/compose.test.yaml up --build -d --wait
    RUN_INTEGRATION=1 pytest tests/integration -v
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio

from .helpers import (
    HA_URL,
    VLLM_MOCK_URL,
    complete_onboarding,
    get_access_token,
    get_config_entries,
    set_entity_state,
    setup_integration_via_flow,
    wait_for_url,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_INTEGRATION = not os.environ.get("RUN_INTEGRATION")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require the Docker integration stack",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_INTEGRATION"):
        return
    skip = pytest.mark.skip(reason="Set RUN_INTEGRATION=1 to run Docker integration tests")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def integration_stack():
    """Require an externally managed Docker Compose stack."""
    if SKIP_INTEGRATION:
        pytest.skip("RUN_INTEGRATION is not set")
    yield


@pytest_asyncio.fixture(scope="session")
async def ha_session(integration_stack):
    """Authenticated aiohttp session against Home Assistant."""
    await wait_for_url(f"{HA_URL}/api/")
    await wait_for_url(f"{VLLM_MOCK_URL}/health")

    session = aiohttp.ClientSession()
    try:
        token = await complete_onboarding(session)
        if token is None:
            token = await get_access_token(session)
        yield session, token
    finally:
        await session.close()


@pytest_asyncio.fixture(scope="session")
async def integration_entry(ha_session):
    """Ensure the Home Assistant Agent integration is configured."""
    session, token = ha_session
    vllm_url = os.environ.get("HA_VLLM_URL", "http://vllm-mock:8000")
    entry_id = await setup_integration_via_flow(session, token, vllm_url=vllm_url)
    # Allow setup_entry to finish (Wyoming server, coordinator refresh).
    time.sleep(8)
    entries = await get_config_entries(session, token)
    assert any(e["entry_id"] == entry_id for e in entries)
    return session, token, entry_id

