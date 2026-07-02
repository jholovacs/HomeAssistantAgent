#!/usr/bin/env python3
"""Verify manifest.json version matches the git release tag."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_utils import ReleaseError, read_manifest_version, tag_version, normalize_tag  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_release_version.py <tag>", file=sys.stderr)
        return 1

    try:
        normalized = normalize_tag(sys.argv[1])
        manifest_version = read_manifest_version()
        version = tag_version(normalized)
        if manifest_version != version:
            print(
                f"manifest.json version {manifest_version!r} does not match tag {version!r}",
                file=sys.stderr,
            )
            return 1
    except ReleaseError as err:
        print(str(err), file=sys.stderr)
        return 1

    print(f"manifest.json version matches tag {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
