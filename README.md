# Home Assistant Agent

[![CI](https://github.com/jholovacs/HomeAssistantAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jholovacs/HomeAssistantAgent/actions/workflows/ci.yml)

An autonomous AI agent custom integration for [Home Assistant](https://www.home-assistant.io/). It periodically evaluates your home state against a **mission statement**, plans and executes actions, verifies outcomes, remembers summarized context, and communicates via notifications and voice (Wyoming / Assist Satellite).

<!-- CI-STATUS:BEGIN -->
## CI Status

| Check | Status | Tests |
|-------|--------|-------|
| Unit tests | **passing** | 42/42 |
| Integration tests (Docker) | **passing** | 6/6 |
| **Overall** | **passing** | 48/48 |

Last successful CI run on `main`: 2026-07-01 23:15 UTC ([`6620f3c`](https://github.com/jholovacs/HomeAssistantAgent/actions/runs/28553954255))
<!-- CI-STATUS:END -->

## Features

- **Autonomous agent loop** — plan → execute → verify → retry
- **vLLM inference** — OpenAI-compatible API (`/v1/chat/completions`) for GPU-accelerated local models
- **Mission statement** — defines how you want your home to behave
- **Persistent memory** — summarized history for future prompt context
- **Periodic polling** — watches entities, automations, scenes, and scripts
- **Conversation agent** — text interaction via Home Assistant Assist
- **Wyoming protocol** — voice pipeline integration as an intent handle service
- **Notifications** — persistent notifications, notify services, and optional `assist_satellite.announce`

## Requirements

- Home Assistant 2024.1 or newer (2026.x tested in CI)
- [vLLM](https://docs.vllm.ai/) OpenAI-compatible server reachable **from the Home Assistant host** (e.g. your GX10)
- At least one instruct model served by vLLM (see [Choosing vLLM](#choosing-vllm-server--model))

---

## End-user setup

### 1. Install and run vLLM

Run [vLLM](https://docs.vllm.ai/en/latest/getting_started/quickstart/) on a machine Home Assistant can reach (your GX10, a GPU server, etc.):

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 8000
```

| Scenario | vLLM URL to use in HA |
|----------|----------------------|
| vLLM on same machine as HA | `http://127.0.0.1:8000` |
| vLLM on LAN server (e.g. GX10) | `http://192.168.x.x:8000` |
| HA Docker, vLLM on host | `http://host.docker.internal:8000` |
| vLLM in Docker on same compose network | `http://<service-name>:8000` |

Verify from the **same network as Home Assistant**:

```bash
curl http://<vllm-host>:8000/v1/models
```

### 2. Install the integration

#### HACS (recommended)

1. In HACS, open the **⋮** menu → **Custom repositories**.
2. Enter `https://github.com/jholovacs/HomeAssistantAgent` and set category to **Integration**, then click **Add**.
3. Go to **HACS → Integrations** and search for **Home Assistant Agent** (custom repos do not appear in the default community browse list).
4. Click **Download**, then restart Home Assistant.

If the repository does not appear after step 2, check for a red error toast — HACS requires a valid `hacs.json`, `manifest.json`, and `brand/icon.png` in the integration folder.

#### Manual

Copy `custom_components/home_assistant_agent` into your Home Assistant `config/custom_components/` directory and restart.

### 3. Add the integration in Home Assistant

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Home Assistant Agent**.
3. **Step 1 — vLLM URL:** enter the base URL reachable from HA (and optional API key).
4. **Step 2 — Model & settings:** pick a model from the dropdown (loaded live from vLLM), set your mission statement, and adjust other options.
5. Finish the wizard.

### 4. Optional: voice and Assist

- **Wyoming voice** — [Wyoming Voice Setup](#wyoming-voice-setup)
- **Assist text** — [Assist Text Setup](#assist-text-setup)

---

## Choosing vLLM server & model

The config flow is a **two-step wizard**:

1. **vLLM URL** — validated with a live connection test (`GET /v1/models` or `/health`).
2. **Model** — dropdown populated from models served by vLLM.

**Recommended models** (good JSON plan output for the agent):

| Model | Serve command | Notes |
|-------|---------------|-------|
| Qwen 2.5 7B Instruct | `vllm serve Qwen/Qwen2.5-7B-Instruct` | Default; strong JSON reliability |
| Llama 3.1 8B Instruct | `vllm serve meta-llama/Llama-3.1-8B-Instruct` | Widely available |
| Mistral 7B Instruct | `vllm serve mistralai/Mistral-7B-Instruct-v0.3` | Lighter footprint |

The agent requests JSON plans via OpenAI `response_format: json_object`. Models without reliable JSON output may cause no-op cycles or parse failures.

**Troubleshooting**

- `cannot_connect` — wrong URL, firewall, or vLLM not running on that host.
- `no_models` — vLLM is up but returned no models; check `vllm serve` arguments.
- `model_not_found` — model name in HA must match the `--served-model-name` / HuggingFace ID vLLM exposes.

---

## Configuration reference

| Setting | Description |
|---------|-------------|
| vLLM URL | Base URL of vLLM **from HA's perspective** (port 8000 default) |
| vLLM API key | Optional bearer token if your server requires auth |
| Model | Selected from live list on your vLLM server |
| Mission statement | Free-text goals for autonomous behavior |
| Poll interval | Seconds between background evaluations (default 600) |
| Wyoming port | TCP port for embedded Wyoming handle service (default 10500) |
| Notify services | Comma-separated, e.g. `persistent_notification,notify.mobile_app_phone` |
| Assist satellite | Optional `assist_satellite.*` entity for voice announcements |
| Entity include/exclude | Glob patterns to scope which entities the agent may act on |
| Max actions per cycle | Safety cap per agent run (default 10) |
| Temperature / max output tokens | LLM inference parameters (`max_tokens` in vLLM) |
| vLLM request timeout | Max seconds to wait for a completion (default 600) |

Update anytime via **Configure** on the integration card (options flow re-fetches models when the URL changes).

## Wyoming Voice Setup

1. Note the Wyoming port from integration settings (default `10500`).
2. In Home Assistant: **Settings → Devices & Services → Add Integration → Wyoming Protocol**.
3. Enter your HA host IP and the configured port.
4. Add the Wyoming **handle** service to your voice assistant pipeline.

## Assist Text Setup

1. Go to **Settings → Voice assistants**.
2. Create or edit an assistant.
3. Set **Conversation agent** to **Home Assistant Agent**.

After setup you should also see a `conversation.*` entity under the integration device. If the agent does not appear in the dropdown, reload the integration or update to the latest version (conversation platform registration is required for Assist).

You can also send text directly via the API using the config entry ID as `agent_id`:

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text":"Turn on the kitchen light","agent_id":"<config_entry_id>"}' \
  http://homeassistant.local:8123/api/conversation/process
```

## Example Mission Statements

```
Keep the home energy-efficient. Turn off lights in empty rooms when motion
has been absent for 30 minutes. Maintain bedroom temperature at 68°F overnight.
Notify me if any exterior door is open more than 5 minutes while away mode is on.
```

```
Prioritize comfort for occupants. Pre-cool the living area to 72°F before
scheduled calendar events marked "guests". Never unlock doors autonomously.
```

## Architecture

The integration runs entirely inside Home Assistant:

- **StateCoordinator** — periodic snapshots and diffs
- **AgentLoop** — orchestrates planning, execution, and verification
- **VllmClient** — OpenAI-compatible `/v1/chat/completions` with JSON plan output
- **MemoryStore** — persistent summarized history via `helpers.storage`
- **WyomingServer** — embedded TCP handle service for voice
- **AbstractConversationAgent** — Assist text conversations

---

## Developer setup

### Clone and install

```bash
git clone https://github.com/jholovacs/HomeAssistantAgent.git
cd HomeAssistantAgent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run unit tests

```bash
pytest tests/unit -v
```

### Run integration tests (Docker)

Requires Docker Compose v2.

```bash
pip install -r requirements-integration.txt
bash scripts/run_integration_tests.sh
```

Or manually:

```bash
docker compose -f docker/compose.test.yaml up --build -d
RUN_INTEGRATION=1 pytest tests/integration -v --timeout=300
docker compose -f docker/compose.test.yaml down -v
```

### Link into a local Home Assistant instance

```bash
# Linux / macOS example — adjust paths for your HA config directory
ln -s "$(pwd)/custom_components/home_assistant_agent" /path/to/ha/config/custom_components/home_assistant_agent
```

Restart Home Assistant, then add the integration from the UI.

### CI

GitHub Actions workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs:

- **Unit tests** on every push and PR
- **Integration tests** (Home Assistant + mock vLLM in Docker) on every push and PR
- **README CI status** auto-updated on `main` after successful runs

---

## License

MIT — see [LICENSE](LICENSE).
