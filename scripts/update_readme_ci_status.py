#!/usr/bin/env python3
"""Update the CI status section in README.md."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _badge(passed: int, total: int) -> str:
    if total == 0:
        return "unknown"
    return "passing" if passed == total else "failing"


def main() -> int:
    if len(sys.argv) != 8:
        print(
            "Usage: update_readme_ci_status.py "
            "<unit_passed> <unit_total> <integration_passed> <integration_total> "
            "<commit_sha> <workflow_url> <readme_path>",
            file=sys.stderr,
        )
        return 1

    unit_passed = int(sys.argv[1])
    unit_total = int(sys.argv[2])
    integration_passed = int(sys.argv[3])
    integration_total = int(sys.argv[4])
    commit_sha = sys.argv[5]
    workflow_url = sys.argv[6]
    readme_path = Path(sys.argv[7])

    unit_status = _badge(unit_passed, unit_total)
    integration_status = _badge(integration_passed, integration_total)
    overall = _badge(unit_passed + integration_passed, unit_total + integration_total)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    section = f"""<!-- CI-STATUS:BEGIN -->
## CI Status

| Check | Status | Tests |
|-------|--------|-------|
| Unit tests | **{unit_status}** | {unit_passed}/{unit_total} |
| Integration tests (Docker) | **{integration_status}** | {integration_passed}/{integration_total} |
| **Overall** | **{overall}** | {unit_passed + integration_passed}/{unit_total + integration_total} |

Last successful CI run on `main`: {timestamp} ([`{commit_sha[:7]}`]({workflow_url}))
<!-- CI-STATUS:END -->"""

    content = readme_path.read_text(encoding="utf-8")
    pattern = r"<!-- CI-STATUS:BEGIN -->.*?<!-- CI-STATUS:END -->"
    if not re.search(pattern, content, flags=re.DOTALL):
        print("CI status markers not found in README", file=sys.stderr)
        return 1

    updated = re.sub(pattern, section, content, count=1, flags=re.DOTALL)
    readme_path.write_text(updated, encoding="utf-8")
    print(f"Updated {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
