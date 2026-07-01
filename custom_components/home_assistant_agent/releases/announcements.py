"""Deliver release announcements through configured notification channels."""

from __future__ import annotations

import logging

import aiohttp
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from ..notify import Notifier
from .github import (
    GitHubRelease,
    fetch_latest_release,
    fetch_release_for_version,
    normalize_version,
    version_is_newer,
)
from .store import ReleaseAnnouncementStore

_LOGGER = logging.getLogger(__name__)


def _awesome(version: str) -> AwesomeVersion:
    return AwesomeVersion(
        normalize_version(version),
        find_first_match=True,
        ensure_strategy=[AwesomeVersionStrategy.SEMVER],
    )


def should_announce_upgrade(installed: str, last_announced: str | None) -> bool:
    """Return True when the installed version was upgraded since last announcement."""
    if not last_announced:
        return False
    return _awesome(installed) > _awesome(last_announced)


def should_announce_update_available(
    latest: str,
    installed: str,
    last_notified: str | None,
) -> bool:
    """Return True when a newer release is available and not yet announced."""
    if not version_is_newer(latest, installed):
        return False
    if last_notified and not version_is_newer(latest, last_notified):
        return False
    return True


async def async_handle_release_announcements(
    *,
    session: aiohttp.ClientSession,
    notifier: Notifier,
    store: ReleaseAnnouncementStore,
    installed_version: str,
    announce_releases: bool,
) -> None:
    """Announce upgrades and newly available updates."""
    if not announce_releases:
        return

    installed = normalize_version(installed_version)
    last_announced = store.get_last_announced_version()

    if last_announced is None:
        await store.async_set_last_announced_version(installed)
        last_announced = installed

    if should_announce_upgrade(installed, last_announced):
        release = await fetch_release_for_version(session, installed)
        await _announce_upgrade(notifier, installed, release)
        await store.async_set_last_announced_version(installed)

    latest_release = await fetch_latest_release(session)
    if latest_release is None:
        return

    last_notified = store.get_last_notified_available_version()
    if should_announce_update_available(
        latest_release.version,
        installed,
        last_notified,
    ):
        await _announce_update_available(notifier, latest_release)
        await store.async_set_last_notified_available_version(latest_release.version)


async def _announce_upgrade(
    notifier: Notifier,
    installed_version: str,
    release: GitHubRelease | None,
) -> None:
    title = f"Home Assistant Agent updated to {installed_version}"
    if release and release.body:
        message = f"{release.summary}\n\n{release.url}"
    else:
        message = f"Home Assistant Agent is now running version {installed_version}."
    await notifier.notify_significant(title, message)
    _LOGGER.info("Announced integration upgrade to %s", installed_version)


async def _announce_update_available(
    notifier: Notifier,
    release: GitHubRelease,
) -> None:
    title = f"Home Assistant Agent {release.version} available"
    message = f"{release.summary}\n\nUpdate via HACS, then restart Home Assistant.\n{release.url}"
    await notifier.notify_significant(title, message)
    _LOGGER.info("Announced available integration update %s", release.version)
