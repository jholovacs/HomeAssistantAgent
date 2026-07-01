"""Tests for service allowlist."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.tools import entity_ids_from_step, is_allowed_service


def test_allowed_light_service():
    assert is_allowed_service("light.turn_on")


def test_blocked_homeassistant_service():
    assert not is_allowed_service("homeassistant.restart")


def test_blocked_invalid_service():
    assert not is_allowed_service("not_a_service")
    assert not is_allowed_service("")


def test_allowed_scene_service():
    assert is_allowed_service("scene.turn_on")


def test_admin_mode_allows_any_domain_except_blocked():
    assert is_allowed_service("number.set_value", admin_mode=True)
    assert is_allowed_service("todo.add_item", admin_mode=True)
    assert not is_allowed_service("homeassistant.restart", admin_mode=True)
    assert not is_allowed_service("hassio.host_shutdown", admin_mode=True)


def test_non_allowlisted_domain_blocked_without_admin_mode():
    assert not is_allowed_service("number.set_value")
    assert not is_allowed_service("todo.add_item")


def test_entity_ids_from_step_collects_target_and_expected():
    ids = entity_ids_from_step(
        target={"entity_id": "climate.office_fan"},
        expected={"entity_id": "climate.office_fan", "state": "cool"},
    )
    assert ids == ["climate.office_fan", "climate.office_fan"]
