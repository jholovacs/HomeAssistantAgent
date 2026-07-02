#!/usr/bin/env python3
"""Validate a release tag before publishing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from release_utils import (
    ReleaseError,
    compare_versions,
    git_tag_exists_local,
    git_tag_exists_remote,
    latest_published_version,
    normalize_tag,
    read_manifest_version,
    tag_version,
    github_release_exists,
    git_repo_slug,
    MANIFEST_PATH,
)


def validate_release(
    tag: str,
    *,
    repo: str | None = None,
    manifest_path: Path = MANIFEST_PATH,
    check_increment: bool = True,
    allow_existing_tag: bool = False,
) -> str:
    """Validate release preconditions; return normalized tag."""
    normalized = normalize_tag(tag)
    version = tag_version(normalized)
    manifest_version = read_manifest_version(manifest_path)

    if manifest_version != version:
        raise ReleaseError(
            f"manifest.json version {manifest_version!r} does not match tag {version!r}"
        )

    repo_slug = repo or git_repo_slug()
    latest = latest_published_version(repo_slug)
    if check_increment:
        if latest is None:
            print(f"No prior GitHub release found for {repo_slug}; first release is OK.")
        elif compare_versions(version, latest) <= 0:
            raise ReleaseError(
                f"Version {version!r} must be greater than latest published {latest!r}"
            )
        else:
            print(f"Version increment OK: {latest!r} -> {version!r}")

    if github_release_exists(repo_slug, normalized):
        raise ReleaseError(f"GitHub release already exists for {normalized}")

    tag_on_remote = git_tag_exists_remote(normalized)
    tag_on_local = git_tag_exists_local(normalized)
    if tag_on_remote or tag_on_local:
        if not allow_existing_tag:
            where = []
            if tag_on_local:
                where.append("local")
            if tag_on_remote:
                where.append("remote")
            raise ReleaseError(
                f"Git tag {normalized} already exists ({', '.join(where)}). "
                "Use --allow-existing-tag only to publish a missing GitHub release."
            )
        print(f"Git tag {normalized} already exists; will publish release only.")

    print(f"Release validation passed for {normalized} ({repo_slug})")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Home Assistant Agent release.")
    parser.add_argument(
        "tag",
        nargs="?",
        help="Release tag (default: v{manifest.json version})",
    )
    parser.add_argument("--repo", help="GitHub owner/repo (default: parse from origin)")
    parser.add_argument(
        "--no-check-increment",
        action="store_true",
        help="Skip check that version is newer than latest published release",
    )
    parser.add_argument(
        "--allow-existing-tag",
        action="store_true",
        help="Allow an existing git tag (publish GitHub release only)",
    )
    args = parser.parse_args()

    try:
        tag = args.tag
        if not tag:
            tag = f"v{read_manifest_version()}"
        validate_release(
            tag,
            repo=args.repo,
            check_increment=not args.no_check_increment,
            allow_existing_tag=args.allow_existing_tag,
        )
    except ReleaseError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
