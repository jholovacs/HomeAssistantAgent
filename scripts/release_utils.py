"""Shared helpers for release validation and publishing."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

MANIFEST_PATH = Path("custom_components/home_assistant_agent/manifest.json")
TAG_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")


class ReleaseError(Exception):
    """Release validation or publish failure."""


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a semver string (optional leading v) into (major, minor, patch)."""
    cleaned = version.removeprefix("v").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", cleaned):
        raise ReleaseError(f"Invalid semver: {version!r}")
    major, minor, patch = (int(part) for part in cleaned.split("."))
    return major, minor, patch


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0, or 1 comparing left to right."""
    l_parts = parse_version(left)
    r_parts = parse_version(right)
    if l_parts < r_parts:
        return -1
    if l_parts > r_parts:
        return 1
    return 0


def normalize_tag(tag: str) -> str:
    """Return a tag in vX.Y.Z form."""
    match = TAG_PATTERN.match(tag.strip())
    if not match:
        raise ReleaseError(f"Invalid release tag format: {tag!r} (expected vX.Y.Z)")
    return f"v{match.group(1)}"


def tag_version(tag: str) -> str:
    """Return the semver portion of a vX.Y.Z tag."""
    return normalize_tag(tag)[1:]


def read_manifest_version(manifest_path: Path = MANIFEST_PATH) -> str:
    """Read integration version from manifest.json."""
    if not manifest_path.is_file():
        raise ReleaseError(f"Manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(data.get("version", "")).strip()
    if not version:
        raise ReleaseError("manifest.json is missing a version")
    parse_version(version)
    return version


def git_repo_slug() -> str:
    """Return owner/repo from origin remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        check=True,
        capture_output=True,
        text=True,
    )
    url = result.stdout.strip()
    if url.endswith(".git"):
        url = url[:-4]
    if "github.com" in url:
        slug = url.split("github.com/", 1)[-1].strip("/")
        if slug:
            return slug
    raise ReleaseError(f"Could not parse GitHub repo slug from origin URL: {url!r}")


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_tag_exists_local(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def git_tag_exists_remote(tag: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def git_is_clean() -> bool:
    return _run_git("status", "--porcelain") == ""


def git_current_branch() -> str:
    return _run_git("rev-parse", "--abbrev-ref", "HEAD")


def fetch_json(url: str) -> dict | list | None:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "HomeAssistantAgent-release"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise ReleaseError(f"GitHub API error {err.code} for {url}") from err
    except urllib.error.URLError as err:
        raise ReleaseError(f"Failed to reach GitHub API: {err}") from err


def github_release_exists(repo: str, tag: str) -> bool:
    payload = fetch_json(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
    return payload is not None


def github_latest_release_version(repo: str) -> str | None:
    payload = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if not payload or not isinstance(payload, dict):
        return None
    tag_name = str(payload.get("tag_name", "")).strip()
    if not tag_name:
        return None
    return tag_version(tag_name)


def github_latest_tag_version(repo: str) -> str | None:
    payload = fetch_json(f"https://api.github.com/repos/{repo}/tags?per_page=100")
    if not payload or not isinstance(payload, list):
        return None
    versions: list[tuple[int, int, int]] = []
    for item in payload:
        name = str(item.get("name", "")).strip()
        if TAG_PATTERN.match(name):
            versions.append(parse_version(name))
    if not versions:
        return None
    latest = max(versions)
    return f"{latest[0]}.{latest[1]}.{latest[2]}"


def latest_published_version(repo: str) -> str | None:
    """Return the newest semver from GitHub releases, falling back to tags."""
    return github_latest_release_version(repo) or github_latest_tag_version(repo)
