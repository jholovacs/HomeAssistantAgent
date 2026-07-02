"""Constants for the Home Assistant Agent integration."""

DOMAIN = "home_assistant_agent"

CONF_VLLM_URL = "vllm_url"
CONF_VLLM_API_KEY = "vllm_api_key"
CONF_MODEL = "model"
CONF_MISSION_STATEMENT = "mission_statement"
CONF_POLL_INTERVAL = "poll_interval"
CONF_WYOMING_PORT = "wyoming_port"
CONF_NOTIFY_SERVICES = "notify_services"
CONF_ASSIST_SATELLITE = "assist_satellite"
CONF_ENTITY_INCLUDE = "entity_include"
CONF_ENTITY_EXCLUDE = "entity_exclude"
CONF_ADMIN_MODE = "admin_mode"
CONF_RESUME_ON_STARTUP = "resume_on_startup"
CONF_MAX_ACTIONS = "max_actions_per_cycle"
CONF_TEMPERATURE = "temperature"
CONF_NUM_CTX = "num_ctx"
CONF_VLLM_REQUEST_TIMEOUT = "vllm_request_timeout"
CONF_ANNOUNCE_RELEASES = "announce_releases"

# Legacy keys migrated from Ollama (v1 config entries).
LEGACY_CONF_OLLAMA_URL = "ollama_url"
LEGACY_CONF_OLLAMA_REQUEST_TIMEOUT = "ollama_request_timeout"
LEGACY_OLLAMA_DEFAULT_PORT = 11434
LEGACY_OLLAMA_DEFAULT_MODEL = "qwen2.5:7b-instruct"

# Cap output tokens sent to vLLM (OpenAI max_tokens is output-only, not context size).
MAX_OUTPUT_TOKEN_CAP = 4096
DEFAULT_SUMMARIZE_MAX_TOKENS = 512

DEFAULT_VLLM_URL = "http://127.0.0.1:8000"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_VLLM_REQUEST_TIMEOUT = 600


def _migrate_legacy_vllm_url(url: str) -> str:
    """Rewrite a legacy Ollama URL to the default vLLM port when unchanged."""
    if f":{LEGACY_OLLAMA_DEFAULT_PORT}" in url:
        return url.replace(f":{LEGACY_OLLAMA_DEFAULT_PORT}", ":8000")
    return url


def _migrate_legacy_model(model: str) -> str:
    """Map common Ollama model tags to HuggingFace-style vLLM model IDs."""
    normalized = model.strip().lower()
    if normalized in {LEGACY_OLLAMA_DEFAULT_MODEL, "qwen2.5:7b"}:
        return DEFAULT_MODEL
    return model


def migrate_legacy_config(data: dict) -> dict:
    """Map Ollama config keys to vLLM equivalents."""
    result = dict(data)
    if LEGACY_CONF_OLLAMA_URL in result and CONF_VLLM_URL not in result:
        result[CONF_VLLM_URL] = result.pop(LEGACY_CONF_OLLAMA_URL)
    if LEGACY_CONF_OLLAMA_REQUEST_TIMEOUT in result and CONF_VLLM_REQUEST_TIMEOUT not in result:
        result[CONF_VLLM_REQUEST_TIMEOUT] = result.pop(LEGACY_CONF_OLLAMA_REQUEST_TIMEOUT)
    result.pop("ollama_keep_alive", None)

    if CONF_VLLM_URL not in result:
        result[CONF_VLLM_URL] = DEFAULT_VLLM_URL
    else:
        result[CONF_VLLM_URL] = _migrate_legacy_vllm_url(result[CONF_VLLM_URL])

    if CONF_MODEL in result:
        result[CONF_MODEL] = _migrate_legacy_model(result[CONF_MODEL])
    elif "model" not in result:
        result[CONF_MODEL] = DEFAULT_MODEL

    if CONF_VLLM_REQUEST_TIMEOUT not in result:
        result[CONF_VLLM_REQUEST_TIMEOUT] = DEFAULT_VLLM_REQUEST_TIMEOUT

    return result


GITHUB_REPO = "jholovacs/HomeAssistantAgent"
GITHUB_API_RELEASES_LATEST = (
    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
)
DEFAULT_RELEASE_CHECK_INTERVAL = 21600  # 6 hours

DEFAULT_POLL_INTERVAL = 600
DEFAULT_WYOMING_PORT = 10500
DEFAULT_MAX_ACTIONS = 10
DEFAULT_TEMPERATURE = 0.3
DEFAULT_NUM_CTX = 2048
DEFAULT_ANNOUNCE_RELEASES = True
DEFAULT_ADMIN_MODE = False
DEFAULT_RESUME_ON_STARTUP = True
DEFAULT_MISSION_STATEMENT = (
    "Maintain a comfortable, safe, and energy-efficient home. "
    "Take proactive action when something is clearly wrong or wasteful. "
    "Prefer minimal disruption to occupants."
)

MAX_RETRIES = 3
VERIFY_DELAY_SECONDS = 2
MEMORY_MAX_ENTRIES = 50
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_memory"
CHECKPOINT_STORAGE_VERSION = 1
CHECKPOINT_STORAGE_KEY = f"{DOMAIN}_checkpoint"
RELEASE_STORAGE_VERSION = 1
RELEASE_STORAGE_KEY = f"{DOMAIN}_releases"

EVENT_RESUME = f"{DOMAIN}_resume"
EVENT_CHECKPOINT_SAVED = f"{DOMAIN}_checkpoint_saved"

SERVICE_RESUME = "resume"

BLOCKED_DOMAINS = frozenset({"homeassistant", "hassio", "supervisor", "auth"})

KEY_ATTRIBUTES = frozenset(
    {
        "friendly_name",
        "device_class",
        "unit_of_measurement",
        "temperature",
        "brightness",
        "color_temp",
        "hvac_mode",
        "current_temperature",
        "battery_level",
    }
)
