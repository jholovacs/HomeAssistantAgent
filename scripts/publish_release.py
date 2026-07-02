#!/usr/bin/env python3
"""Create and publish a GitHub release from manifest.json."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Allow running from repo root without installing scripts as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_utils import (  # noqa: E402
    ReleaseError,
    git_current_branch,
    git_is_clean,
    git_repo_slug,
    git_tag_exists_local,
    git_tag_exists_remote,
    github_release_exists,
    normalize_tag,
    read_manifest_version,
    tag_version,
)
from validate_release import validate_release  # noqa: E402


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise ReleaseError(f"Required command not found: {name}")


def _run(command: list[str], *, dry_run: bool = False) -> None:
    printable = " ".join(command)
    if dry_run:
        print(f"[dry-run] {printable}")
        return
    print(f"+ {printable}")
    subprocess.run(command, check=True)


def publish_release(
    *,
    tag: str | None = None,
    yes: bool = False,
    dry_run: bool = False,
    skip_tests: bool = False,
    allow_existing_tag: bool = False,
) -> str:
    """Validate, tag, push, and create a GitHub release."""
    _require_tool("git")
    _require_tool("gh")

    if not skip_tests and not dry_run:
        _run([sys.executable, "-m", "pytest", "tests/unit", "-q"])

    if not git_is_clean():
        raise ReleaseError("Git working tree is not clean; commit or stash changes first")

    branch = git_current_branch()
    if branch != "main":
        raise ReleaseError(f"Expected branch 'main', currently on {branch!r}")

    manifest_version = read_manifest_version()
    normalized = normalize_tag(tag or f"v{manifest_version}")
    version = tag_version(normalized)
    if version != manifest_version:
        raise ReleaseError(
            f"Requested tag {normalized!r} does not match manifest version {manifest_version!r}"
        )

    repo = git_repo_slug()
    tag_exists = git_tag_exists_local(normalized) or git_tag_exists_remote(normalized)
    validate_release(
        normalized,
        repo=repo,
        check_increment=True,
        allow_existing_tag=allow_existing_tag or tag_exists,
    )

    if not yes and not dry_run:
        answer = input(f"Publish {normalized} to {repo}? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            raise ReleaseError("Aborted")

    if not tag_exists:
        _run(
            [
                "git",
                "tag",
                "-a",
                normalized,
                "-m",
                f"Release {normalized}\n\nHome Assistant Agent {version}",
            ],
            dry_run=dry_run,
        )
        _run(["git", "push", "origin", normalized], dry_run=dry_run)
    else:
        print(f"Tag {normalized} already exists; skipping tag create/push.")

    if dry_run:
        print(f"[dry-run] gh release create {normalized} ...")
        return normalized

    if github_release_exists(repo, normalized):
        print(f"GitHub release {normalized} already exists.")
        return normalized

    title = f"Home Assistant Agent {version}"
    _run(
        [
            "gh",
            "release",
            "create",
            normalized,
            "--title",
            title,
            "--generate-notes",
            "--verify-tag",
        ],
    )
    print(f"Published {normalized}: https://github.com/{repo}/releases/tag/{normalized}")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a Home Assistant Agent release from manifest.json.",
    )
    parser.add_argument(
        "tag",
        nargs="?",
        help="Release tag (default: v{manifest.json version})",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print commands only")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unit tests before release")
    parser.add_argument(
        "--allow-existing-tag",
        action="store_true",
        help="Publish GitHub release for an existing tag",
    )
    args = parser.parse_args()

    try:
        publish_release(
            tag=args.tag,
            yes=args.yes,
            dry_run=args.dry_run,
            skip_tests=args.skip_tests,
            allow_existing_tag=args.allow_existing_tag,
        )
    except ReleaseError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as err:
        print(f"error: command failed with exit code {err.returncode}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
