#!/usr/bin/env python3
"""Enforce rule 2: a workstream writes only inside its own paths.

Run in CI on every pull request. The branch name declares the workstream
(``ws-<id>/<sprint>-<slug>``); the diff against the base branch must touch only
paths that workstream owns. Workstream A owns everything, because A integrates.

    python scripts/check_ownership.py --base origin/main
    python scripts/check_ownership.py --base origin/main --workstream E
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

#: Path prefixes each workstream may write. Keep in step with CLAUDE.md and
#: docs/agents/README.md — the three are checked against each other below.
OWNERSHIP: dict[str, list[str]] = {
    "A": ["."],  # architect and integrator
    "B": ["infra/", ".github/", "Makefile", "scripts/", ".env.example", ".gitignore"],
    "C": ["api/inventory/"],
    "D": ["workers/botany/"],
    "E": ["workers/weather/", "api/almanac/"],
    "F": ["workers/hub/"],
    "G": ["api/tending/"],
    "H": ["api/grounds/", "web/src/lib/map/"],
    "I": [
        "web/src/lib/ui/",
        "web/src/app-shell/",
        "web/src/app.html",
        "web/static/",
        # The component gallery is a design-system artefact, not a feature
        # screen, so it belongs to I even though it lives under routes/.
        "web/src/routes/gallery/",
    ],
    "J": ["web/src/routes/"],
    "K": ["workers/plates/", "web/src/routes/journal/"],
    "L": ["tests/", "fixtures/", "docs/user/"],
}

#: Anyone may write these. Sprint notes are shared by design; the
#: NOT_YET_IMPLEMENTED list is a shared progress marker rather than L's test
#: logic, and rule 6 requires the workstream that implements a path to strike
#: its own entry — so making it L-only was a contradiction every sprint hits.
ALWAYS_ALLOWED = (
    "docs/sprints/",
    "tests/contract/test_api_matches_spec.py",
)

#: Nobody but A touches these, whatever else their branch says.
A_ONLY = ("contracts/", "docs/adr/", "CLAUDE.md", "docs/plan/", "docs/design/")

BRANCH_PATTERN = re.compile(r"^ws-([a-l])/", re.IGNORECASE)


def changed_paths(base: str) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in diff.stdout.splitlines() if line]


def workstream_from_branch() -> str | None:
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    match = BRANCH_PATTERN.match(branch)
    return match.group(1).upper() if match else None


def violations(workstream: str, paths: list[str]) -> list[str]:
    if workstream == "A":
        return []
    owned = tuple(OWNERSHIP[workstream])
    out = []
    for path in paths:
        if path.startswith(ALWAYS_ALLOWED):
            continue
        if path.startswith(A_ONLY):
            out.append(f"{path}  (only Workstream A may change this — open an ADR)")
            continue
        if not path.startswith(owned):
            out.append(f"{path}  (Workstream {workstream} owns {', '.join(owned)})")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument(
        "--workstream", help="Override the branch-derived workstream id"
    )
    args = parser.parse_args()

    workstream = (args.workstream or workstream_from_branch() or "").upper()
    if not workstream:
        print("No workstream in the branch name; skipping the ownership check.")
        print("Name branches ws-<id>/<sprint>-<slug>, e.g. ws-e/s3-openmeteo-ingest.")
        return 0
    if workstream not in OWNERSHIP:
        print(
            f"Unknown workstream {workstream!r}. Known: {', '.join(sorted(OWNERSHIP))}"
        )
        return 1

    paths = changed_paths(args.base)
    if not paths:
        print("No changes.")
        return 0

    bad = violations(workstream, paths)
    if bad:
        print(f"Workstream {workstream} touched paths it does not own:\n")
        for line in bad:
            print(f"  {line}")
        print("\nRule 2: own your directory. Cross-cutting changes go through A.")
        return 1

    print(f"Workstream {workstream}: {len(paths)} file(s), all within its own paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
