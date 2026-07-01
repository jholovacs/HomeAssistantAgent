"""Fetch release metadata from GitHub."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from ..const import GITHUB_API_RELEASES_LATEST, GITHUB_REPO

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "home-assistant-agent"


@dataclass(frozen=True, slots=True)
class GitHubRelease:
    """Parsed GitHub release."""

    tag: str
    name: str
    body: str
    url: str

    @property
    def version(self) -> str:
        """Return a normalized semver-like version string."""
        return normalize_version(self.tag)

    @property
    def summary(self) -> str:
        """Return a short single-line summary for notifications."""
        if not self.body:
            return f"Version {self.version} is available."
        first_line = self.body.strip().splitlines()[0].strip()
        if len(first_line) > 240:
            return first_line[:237] + "..."
        return first_line or f"Version {self.version} is available."


def normalize_version(version: str) -> str:
    """Strip a leading ``v`` from release tags."""
    return version.removeprefix("v").strip()


def version_is_newer(latest: str, installed: str) -> bool:
    """Return True when ``latest`` is newer than ``installed``."""
    return AwesomeVersion(
        normalize_version(latest),
        find_first_match=True,
        ensure_strategy=[AwesomeVersionStrategy.SEMVER],
    ) > AwesomeVersion(
        normalize_version(installed),
        find_first_match=True,
        ensure_strategy=[AwesomeVersionStrategy.SEMVER],
    )


def parse_release(payload: dict[str, Any]) -> GitHubRelease:
    """Parse a GitHub release API response."""
    return GitHubRelease(
        tag=str(payload.get("tag_name", "")),
        name=str(payload.get("name") or payload.get("tag_name", "")),
        body=str(payload.get("body") or ""),
        url=str(payload.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"),
    )


async def fetch_latest_release(session: aiohttp.ClientSession) -> GitHubRelease | None:
    """Fetch the latest published GitHub release."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    try:
        async with session.get(
            GITHUB_API_RELEASES_LATEST,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 404:
                _LOGGER.debug("No GitHub releases published yet")
                return None
            resp.raise_for_status()
            return parse_release(await resp.json())
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.debug("Failed to fetch latest GitHub release: %s", err)
        return None


async def fetch_release_for_version(
    session: aiohttp.ClientSession, version: str
) -> GitHubRelease | None:
    """Fetch release notes for a specific installed version."""
    normalized = normalize_version(version)
    for tag in (normalized, f"v{normalized}"):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{tag}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        }
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 404:
                    continue
                resp.raise_for_status()
                return parse_release(await resp.json())
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Failed to fetch GitHub release %s: %s", tag, err)
    return None
