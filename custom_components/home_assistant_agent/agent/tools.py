"""Tool/service definitions exposed to the LLM."""

ALLOWED_SERVICE_PREFIXES = (
    "light.",
    "switch.",
    "cover.",
    "climate.",
    "fan.",
    "lock.",
    "media_player.",
    "scene.",
    "script.",
    "automation.",
    "input_boolean.",
    "input_select.",
    "notify.",
    "vacuum.",
    "water_heater.",
    "humidifier.",
    "valve.",
)

SERVICE_EXAMPLES = """
Common services:
- light.turn_on / light.turn_off (target: entity_id, data: brightness, color_temp)
- switch.turn_on / switch.turn_off
- climate.set_temperature (data: temperature)
- scene.turn_on (target: entity_id)
- script.turn_on (target: entity_id)
- automation.trigger (target: entity_id)
"""


def is_allowed_service(service: str, *, admin_mode: bool = False) -> bool:
    """Return True if the service is permitted."""
    if not service or "." not in service:
        return False
    domain = service.split(".", 1)[0]
    from ..const import BLOCKED_DOMAINS

    if domain in BLOCKED_DOMAINS:
        return False
    if admin_mode:
        return True
    return any(service.startswith(prefix) for prefix in ALLOWED_SERVICE_PREFIXES)
