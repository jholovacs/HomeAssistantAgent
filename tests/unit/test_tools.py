"""Tests for service allowlist."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.tools import is_allowed_service


def test_allowed_light_service():
    assert is_allowed_service("light.turn_on")


def test_blocked_homeassistant_service():
    assert not is_allowed_service("homeassistant.restart")


def test_blocked_invalid_service():
    assert not is_allowed_service("not_a_service")
    assert not is_allowed_service("")


def test_allowed_scene_service():
    assert is_allowed_service("scene.turn_on")
