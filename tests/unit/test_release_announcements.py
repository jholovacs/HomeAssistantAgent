"""Tests for release announcement helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.releases.announcements import (
    should_announce_update_available,
    should_announce_upgrade,
)
from home_assistant_agent.releases.github import (
    normalize_version,
    parse_release,
    version_is_newer,
)


def test_normalize_version_strips_v_prefix():
    assert normalize_version("v0.3.0") == "0.3.0"
    assert normalize_version("0.3.0") == "0.3.0"


def test_version_is_newer():
    assert version_is_newer("0.3.0", "0.2.1")
    assert not version_is_newer("0.2.1", "0.3.0")
    assert not version_is_newer("0.3.0", "0.3.0")


def test_parse_release_summary_uses_first_line():
    release = parse_release(
        {
            "tag_name": "v0.3.0",
            "name": "0.3.0",
            "body": "Added release announcements.\n\nMore details here.",
            "html_url": "https://github.com/jholovacs/HomeAssistantAgent/releases/tag/v0.3.0",
        }
    )
    assert release.version == "0.3.0"
    assert release.summary == "Added release announcements."


def test_should_announce_upgrade():
    assert not should_announce_upgrade("0.3.0", None)
    assert should_announce_upgrade("0.3.0", "0.2.1")
    assert not should_announce_upgrade("0.3.0", "0.3.0")


def test_should_announce_update_available():
    assert should_announce_update_available("0.3.1", "0.3.0", None)
    assert not should_announce_update_available("0.3.0", "0.3.0", None)
    assert not should_announce_update_available("0.3.1", "0.3.0", "0.3.1")
    assert should_announce_update_available("0.3.2", "0.3.0", "0.3.1")
