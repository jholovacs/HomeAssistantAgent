"""Tests for entity filtering."""

import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))


def entity_allowed(
    entity_id: str,
    includes: list[str],
    excludes: list[str],
) -> bool:
    """Mirror coordinator entity filter logic."""
    if excludes and any(fnmatch.fnmatch(entity_id, pat) for pat in excludes):
        return False
    if includes:
        return any(fnmatch.fnmatch(entity_id, pat) for pat in includes)
    return True


def test_entity_allowed_with_include():
    assert entity_allowed("light.kitchen", ["light.*"], [])
    assert not entity_allowed("switch.kitchen", ["light.*"], [])


def test_entity_allowed_with_exclude():
    assert not entity_allowed("light.kitchen", [], ["light.*"])
    assert entity_allowed("switch.kitchen", [], ["light.*"])


def test_entity_allowed_no_filters():
    assert entity_allowed("sensor.temperature", [], [])
