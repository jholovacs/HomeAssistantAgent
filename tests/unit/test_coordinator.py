"""Tests for entity filtering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.coordinator import entity_allowed


def test_entity_allowed_with_include():
    assert entity_allowed("light.kitchen", ["light.*"], [])
    assert not entity_allowed("switch.kitchen", ["light.*"], [])


def test_entity_allowed_with_exclude():
    assert not entity_allowed("light.kitchen", [], ["light.*"])
    assert entity_allowed("switch.kitchen", [], ["light.*"])


def test_entity_allowed_no_filters():
    assert entity_allowed("sensor.temperature", [], [])


def test_admin_mode_bypasses_include_filter():
    assert entity_allowed("switch.kitchen", ["light.*"], [], admin_mode=True)
    assert entity_allowed("todo.shopping", ["light.*"], [], admin_mode=True)


def test_admin_mode_still_respects_exclude():
    assert not entity_allowed("light.kitchen", ["light.*"], ["light.*"], admin_mode=True)
    assert entity_allowed("switch.kitchen", ["light.*"], ["light.*"], admin_mode=True)
