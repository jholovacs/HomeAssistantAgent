"""Tool/service definitions exposed to the LLM."""

# The integration sends user notifications itself; do not let the LLM call these.
BLOCKED_SERVICE_PREFIXES = (
    "notify.",
    "persistent_notification.",
)

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

def is_allowed_service(service: str, *, admin_mode: bool = False) -> bool:
    """Return True if the service is permitted."""
    if not service or "." not in service:
        return False
    domain = service.split(".", 1)[0]
    from ..const import BLOCKED_DOMAINS

    if domain in BLOCKED_DOMAINS:
        return False
    if any(service.startswith(prefix) for prefix in BLOCKED_SERVICE_PREFIXES):
        return False
    if admin_mode:
        return True
    return any(service.startswith(prefix) for prefix in ALLOWED_SERVICE_PREFIXES)


def entity_ids_from_step(
    *,
    target: dict | None = None,
    data: dict | None = None,
    expected: dict | None = None,
) -> list[str]:
    """Collect entity IDs referenced by a plan step."""
    ids: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, str) and value:
            ids.append(value)
        elif isinstance(value, list):
            ids.extend(item for item in value if isinstance(item, str) and item)

    target = target or {}
    data = data or {}
    expected = expected or {}
    add(target.get("entity_id"))
    add(data.get("entity_id"))
    add(expected.get("entity_id"))
    return ids
