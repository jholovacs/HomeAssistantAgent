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
CONF_MAX_ACTIONS = "max_actions_per_cycle"
CONF_TEMPERATURE = "temperature"
CONF_NUM_CTX = "num_ctx"

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_POLL_INTERVAL = 600
DEFAULT_WYOMING_PORT = 10500
DEFAULT_MAX_ACTIONS = 10
DEFAULT_TEMPERATURE = 0.3
DEFAULT_NUM_CTX = 8192
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
