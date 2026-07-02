"""Tests for release validation helpers."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from release_utils import (  # noqa: E402
    ReleaseError,
    compare_versions,
    normalize_tag,
    parse_version,
    tag_version,
)
from validate_release import validate_release  # noqa: E402


def test_parse_version():
    assert parse_version("0.4.2") == (0, 4, 2)
    assert parse_version("v1.10.3") == (1, 10, 3)


def test_compare_versions():
    assert compare_versions("0.4.2", "0.4.1") == 1
    assert compare_versions("0.4.1", "0.4.2") == -1
    assert compare_versions("0.4.0", "0.4.0") == 0


def test_normalize_tag():
    assert normalize_tag("v0.4.2") == "v0.4.2"
    assert tag_version("v0.4.2") == "0.4.2"


def test_normalize_tag_rejects_invalid():
    with pytest.raises(ReleaseError):
        normalize_tag("0.4.2")


@patch("validate_release.github_release_exists", return_value=False)
@patch("validate_release.git_tag_exists_remote", return_value=False)
@patch("validate_release.git_tag_exists_local", return_value=False)
@patch("validate_release.latest_published_version", return_value="0.4.1")
@patch("validate_release.read_manifest_version", return_value="0.4.2")
@patch("validate_release.git_repo_slug", return_value="owner/repo")
def test_validate_release_accepts_increment(
    _slug,
    _manifest,
    _latest,
    _local,
    _remote,
    _release,
    tmp_path,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": "0.4.2"}', encoding="utf-8")
    tag = validate_release(
        "v0.4.2",
        repo="owner/repo",
        manifest_path=manifest,
    )
    assert tag == "v0.4.2"


@patch("validate_release.github_release_exists", return_value=False)
@patch("validate_release.git_tag_exists_remote", return_value=False)
@patch("validate_release.git_tag_exists_local", return_value=False)
@patch("validate_release.latest_published_version", return_value="0.4.2")
@patch("validate_release.read_manifest_version", return_value="0.4.2")
def test_validate_release_rejects_duplicate_version(
    _manifest,
    _latest,
    _local,
    _remote,
    _release,
    tmp_path,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": "0.4.2"}', encoding="utf-8")
    with pytest.raises(ReleaseError, match="greater than latest"):
        validate_release("v0.4.2", repo="owner/repo", manifest_path=manifest)


@patch("validate_release.github_release_exists", return_value=True)
@patch("validate_release.git_tag_exists_remote", return_value=True)
@patch("validate_release.git_tag_exists_local", return_value=True)
@patch("validate_release.latest_published_version", return_value="0.4.1")
@patch("validate_release.read_manifest_version", return_value="0.4.2")
def test_validate_release_rejects_existing_release(
    _manifest,
    _latest,
    _local,
    _remote,
    _release,
    tmp_path,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": "0.4.2"}', encoding="utf-8")
    with pytest.raises(ReleaseError, match="already exists"):
        validate_release("v0.4.2", repo="owner/repo", manifest_path=manifest)
