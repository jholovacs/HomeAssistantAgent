#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Installing integration test dependencies..."
python -m pip install -q -r requirements-integration.txt

echo "Starting Docker integration stack..."
rm -rf docker/homeassistant/.storage docker/homeassistant/deps docker/homeassistant/home-assistant_v2.db
docker compose -f docker/compose.test.yaml up --build -d

echo "Waiting for Home Assistant to become ready..."
python - <<'PY'
import asyncio
import sys
sys.path.insert(0, "tests/integration")
from helpers import HA_URL, wait_for_url, wait_for_onboarding
import aiohttp

async def main():
    async with aiohttp.ClientSession() as session:
        await wait_for_url(f"{HA_URL}/api/")
        await wait_for_onboarding(session)

asyncio.run(main())
print("Home Assistant is ready.")
PY

cleanup() {
  echo "Stopping Docker integration stack..."
  docker compose -f docker/compose.test.yaml down -v
}
trap cleanup EXIT

export RUN_INTEGRATION=1
export HA_URL="${HA_URL:-http://127.0.0.1:8123}"
export VLLM_MOCK_URL="${VLLM_MOCK_URL:-http://127.0.0.1:8000}"
export HA_VLLM_URL="${HA_VLLM_URL:-http://vllm-mock:8000}"

echo "Running integration tests..."
python -m pytest tests/integration -v --timeout=300 "$@"
