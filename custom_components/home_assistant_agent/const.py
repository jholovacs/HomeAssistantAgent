"""Constants for the Home Assistant Agent integration."""

DOMAIN = "home_assistant_agent"

CONF_OLLAMA_URL = "ollama_url"
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
CONF_OLLAMA_KEEP_ALIVE = "ollama_keep_alive"
CONF_OLLAMA_REQUEST_TIMEOUT = "ollama_request_timeout"
CONF_ANNOUNCE_RELEASES = "announce_releases"

GITHUB_REPO = "jholovacs/HomeAssistantAgent"
GITHUB_API_RELEASES_LATEST = (
    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
)
DEFAULT_RELEASE_CHECK_INTERVAL = 21600  # 6 hours

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_POLL_INTERVAL = 600
DEFAULT_WYOMING_PORT = 10500
DEFAULT_MAX_ACTIONS = 10
DEFAULT_TEMPERATURE = 0.3
DEFAULT_NUM_CTX = 8192
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"
DEFAULT_OLLAMA_REQUEST_TIMEOUT = 600
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
