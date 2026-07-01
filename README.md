# Home Assistant Agent

[![CI](https://github.com/jholovacs/HomeAssistantAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jholovacs/HomeAssistantAgent/actions/workflows/ci.yml)

An autonomous AI agent custom integration for [Home Assistant](https://www.home-assistant.io/). It periodically evaluates your home state against a **mission statement**, plans and executes actions, verifies outcomes, remembers summarized context, and communicates via notifications and voice (Wyoming / Assist Satellite).

<!-- CI-STATUS:BEGIN -->
## CI Status

| Check | Status | Tests |
|-------|--------|-------|
| Unit tests | **passing** | 16/16 |
| Integration tests (Docker) | **passing** | 6/6 |
| **Overall** | **passing** | 22/22 |

Last successful CI run on `main`: 2026-07-01 18:10 UTC ([`9fd691e`](https://github.com/jholovacs/HomeAssistantAgent/actions/runs/28538006090))
<!-- CI-STATUS:END -->

## Features

- **Autonomous agent loop** — plan → execute → verify → retry
- **Ollama LLM** — configurable URL and model (direct HTTP, no cloud required)
- **Mission statement** — defines how you want your home to behave
- **Persistent memory** — summarized history for future prompt context
- **Periodic polling** — watches entities, automations, scenes, and scripts
- **Conversation agent** — text interaction via Home Assistant Assist
- **Wyoming protocol** — voice pipeline integration as an intent handle service
- **Notifications** — persistent notifications, notify services, and optional `assist_satellite.announce`

## Requirements

- Home Assistant 2024.1 or newer (2026.x tested in CI)
- [Ollama](https://ollama.com/) reachable **from the Home Assistant host** (not just from your laptop)
- At least one instruct model pulled on that Ollama server (see [Choosing Ollama](#choosing-ollama-server--model))

---

## End-user setup

### 1. Install Ollama

Install [Ollama](https://ollama.com/download) on a machine that Home Assistant can reach:

- **Same machine as HA** — install Ollama on the HA host; use `http://127.0.0.1:11434`
- **Another computer / NAS** — install Ollama there; use `http://<ip>:11434`
- **HA in Docker, Ollama on host** — often `http://host.docker.internal:11434` (platform-dependent)
- **HA OS / Supervised** — Ollama is not built-in; run it on another box or use an add-on/community guide for your platform

Start the server (usually automatic after install):

```bash
ollama serve
```

Pull a recommended model:

```bash
ollama pull qwen2.5:7b-instruct
```

Verify from the **same network as Home Assistant**:

```bash
curl http://<ollama-host>:11434/api/tags
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
3. **Step 1 — Ollama URL:** enter the base URL reachable from HA (see table below).
4. **Step 2 — Model & settings:** pick a model from the dropdown (loaded live from your Ollama server), set your mission statement, and adjust other options.
5. Finish the wizard.

### 4. Optional: voice and Assist

- **Wyoming voice** — [Wyoming Voice Setup](#wyoming-voice-setup)
- **Assist text** — [Assist Text Setup](#assist-text-setup)

---

## Choosing Ollama server & model

The config flow is a **two-step wizard**:

1. **Ollama URL** — validated with a live connection test (`GET /api/tags`).
2. **Model** — dropdown populated from models installed on that server (no manual typing required).

| Scenario | Ollama URL to try |
|----------|-------------------|
| Ollama on same machine as HA | `http://127.0.0.1:11434` |
| Ollama on LAN server | `http://192.168.x.x:11434` |
| HA Docker, Ollama on host | `http://host.docker.internal:11434` |
| Ollama in Docker on same compose network | `http://<service-name>:11434` |

**Recommended models** (good JSON plan output for the agent):

| Model | Pull command | Notes |
|-------|--------------|-------|
| Qwen 2.5 7B Instruct | `ollama pull qwen2.5:7b-instruct` | Default; strong JSON reliability |
| Llama 3.1 8B Instruct | `ollama pull llama3.1:8b-instruct` | Widely available |
| Mistral 7B Instruct | `ollama pull mistral:7b-instruct` | Lighter footprint |

The agent sends structured JSON plans to Ollama (`format: json`). Models without reliable JSON output may cause no-op cycles or parse failures.

**Troubleshooting**

- `cannot_connect` — wrong URL, firewall, or Ollama not running on that host.
- `no_models` — Ollama is up but empty; run `ollama pull <model>` on the Ollama machine.
- `model_not_found` — model was removed from Ollama; re-open **Configure** and pick a current model.

---

## Configuration reference

| Setting | Description |
|---------|-------------|
| Ollama URL | Base URL of Ollama **from HA's perspective** |
| Model | Selected from live list on your Ollama server |
| Mission statement | Free-text goals for autonomous behavior |
| Poll interval | Seconds between background evaluations (default 600) |
| Wyoming port | TCP port for embedded Wyoming handle service (default 10500) |
| Notify services | Comma-separated, e.g. `persistent_notification,notify.mobile_app_phone` |
| Assist satellite | Optional `assist_satellite.*` entity for voice announcements |
| Entity include/exclude | Glob patterns to scope which entities the agent may act on |
| Max actions per cycle | Safety cap per agent run (default 10) |
| Temperature / context window | LLM inference parameters |

Update anytime via **Configure** on the integration card (options flow re-fetches models when the URL changes).

## Wyoming Voice Setup

1. Note the Wyoming port from integration settings (default `10500`).
2. In Home Assistant: **Settings → Devices & Services → Add Integration → Wyoming Protocol**.
3. Enter your HA host IP and the configured port.
4. Add the Wyoming **handle** service to your voice assistant pipeline.

## Assist Text Setup

1. Go to **Settings → Voice Assistants**.
2. Create or edit an assistant.
3. Set **Conversation agent** to **Home Assistant Agent** (use the config entry ID if prompted).

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
- **OllamaClient** — direct `/api/chat` calls with JSON plan output
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
- **Integration tests** (Home Assistant + mock Ollama in Docker) on every push and PR
- **README CI status** auto-updated on `main` after successful runs

---

## License

MIT — see [LICENSE](LICENSE).
