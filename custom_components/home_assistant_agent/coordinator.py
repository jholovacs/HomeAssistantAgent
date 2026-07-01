"""State coordinator for periodic home snapshots."""

from __future__ import annotations

import fnmatch
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ADMIN_MODE, CONF_ENTITY_EXCLUDE, CONF_ENTITY_INCLUDE, DOMAIN, KEY_ATTRIBUTES

_LOGGER = logging.getLogger(__name__)


def entity_allowed(
    entity_id: str,
    includes: list[str],
    excludes: list[str],
    *,
    admin_mode: bool = False,
) -> bool:
    """Return True if an entity is visible to the agent."""
    if excludes and any(fnmatch.fnmatch(entity_id, pat) for pat in excludes):
        return False
    if admin_mode:
        return True
    if includes:
        return any(fnmatch.fnmatch(entity_id, pat) for pat in includes)
    return True


def _compact_entity(state) -> dict[str, Any]:
    """Build a compact entity representation."""
    attrs = {
        k: v
        for k, v in state.attributes.items()
        if k in KEY_ATTRIBUTES or k.startswith("friendly")
    }
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": attrs,
        "last_changed": state.last_changed.isoformat(),
    }


class StateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Builds and diffs home state snapshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
    ) -> None:
        poll_interval = config.get("poll_interval", 600)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self._config = config
        self._previous_snapshot: dict[str, Any] | None = None

    def _entity_allowed(self, entity_id: str) -> bool:
        return entity_allowed(
            entity_id,
            self._config.get(CONF_ENTITY_INCLUDE, []),
            self._config.get(CONF_ENTITY_EXCLUDE, []),
            admin_mode=bool(self._config.get(CONF_ADMIN_MODE, False)),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snapshot = self._build_snapshot()
            diff = self._compute_diff(snapshot)
            self._previous_snapshot = snapshot
            return {
                "snapshot": snapshot,
                "diff": diff,
                "has_changes": bool(diff.get("entities")),
            }
        except Exception as err:
            raise UpdateFailed(f"Failed to update home snapshot: {err}") from err

    def _build_snapshot(self) -> dict[str, Any]:
        entities = []
        scenes = []
        scripts = []
        automations = []

        for state in self.hass.states.async_all():
            eid = state.entity_id
            if not self._entity_allowed(eid):
                continue

            domain = eid.split(".", 1)[0]
            compact = _compact_entity(state)

            if domain == "scene":
                scenes.append(compact)
            elif domain == "script":
                scripts.append(compact)
            elif domain == "automation":
                automations.append(compact)
            else:
                entities.append(compact)

        return {
            "entities": entities,
            "scenes": scenes,
            "scripts": scripts,
            "automations": automations,
            "timestamp": datetime.now().isoformat(),
        }

    def _compute_diff(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if self._previous_snapshot is None:
            return {"entities": [], "note": "initial_snapshot"}

        prev_map = {
            e["entity_id"]: e
            for e in self._previous_snapshot.get("entities", [])
        }
        changes = []
        for entity in snapshot.get("entities", []):
            eid = entity["entity_id"]
            prev = prev_map.get(eid)
            if prev is None:
                changes.append({"entity_id": eid, "change": "added", "state": entity["state"]})
            elif prev["state"] != entity["state"]:
                changes.append(
                    {
                        "entity_id": eid,
                        "change": "state_changed",
                        "from": prev["state"],
                        "to": entity["state"],
                    }
                )
            elif entity["state"] in ("unavailable", "unknown"):
                changes.append(
                    {
                        "entity_id": eid,
                        "change": "unavailable",
                        "state": entity["state"],
                    }
                )

        return {"entities": changes}

    def known_entity_ids(self) -> frozenset[str]:
        """Return entity IDs currently visible in the coordinator snapshot."""
        data = self.data or {}
        snapshot = data.get("snapshot", {})
        ids: set[str] = set()
        for key in ("entities", "scenes", "scripts", "automations"):
            for item in snapshot.get(key, []):
                entity_id = item.get("entity_id")
                if entity_id:
                    ids.add(entity_id)
        return frozenset(ids)

    def format_snapshot_for_prompt(self, max_entities: int = 80) -> str:
        """Format snapshot as text for LLM context."""
        data = self.data or {}
        snapshot = data.get("snapshot", {})
        lines = []
        for entity in snapshot.get("entities", [])[:max_entities]:
            name = entity.get("attributes", {}).get("friendly_name", "")
            lines.append(f"- {entity['entity_id']}: {entity['state']} ({name})")
        if len(snapshot.get("entities", [])) > max_entities:
            lines.append(f"... and {len(snapshot['entities']) - max_entities} more entities")
        return "\n".join(lines) if lines else "No entities in scope."

    def format_diff_for_prompt(self) -> str:
        """Format diff as text for LLM context."""
        data = self.data or {}
        diff = data.get("diff", {})
        changes = diff.get("entities", [])
        if not changes:
            return (
                "No entity state changes since last check. "
                "Still evaluate the mission for proactive improvements."
            )
        lines = []
        for change in changes[:50]:
            eid = change.get("entity_id", "")
            if change.get("change") == "state_changed":
                lines.append(f"- {eid}: {change['from']} -> {change['to']}")
            else:
                lines.append(f"- {eid}: {change.get('change')} ({change.get('state', '')})")
        return "\n".join(lines)

    def format_list_for_prompt(self, key: str) -> str:
        """Format scenes/scripts/automations list."""
        data = self.data or {}
        snapshot = data.get("snapshot", {})
        items = snapshot.get(key, [])
        if not items:
            return f"No {key} in scope."
        lines = []
        for item in items[:30]:
            name = item.get("attributes", {}).get("friendly_name", "")
            lines.append(f"- {item['entity_id']}: {item['state']} ({name})")
        return "\n".join(lines)
