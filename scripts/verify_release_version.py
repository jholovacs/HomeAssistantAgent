#!/usr/bin/env python3
"""Verify manifest.json version matches the git release tag."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_release_version.py <tag>", file=sys.stderr)
        return 1

    tag = sys.argv[1].removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", tag):
        print(f"Invalid release tag format: {sys.argv[1]}", file=sys.stderr)
        return 1

    manifest_path = Path("custom_components/home_assistant_agent/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_version = str(manifest.get("version", ""))

    if manifest_version != tag:
        print(
            f"manifest.json version {manifest_version!r} does not match tag {tag!r}",
            file=sys.stderr,
        )
        return 1

    print(f"manifest.json version matches tag {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
