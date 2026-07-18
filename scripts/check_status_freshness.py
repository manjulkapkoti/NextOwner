#!/usr/bin/env python3
"""Fail if `main`'s status surfaces still describe work as unfinished.

WHY THIS EXISTS
---------------
Three files claim project status: `CLAUDE.md`'s `## Project status:` line,
`docs/progress.md`, and the `docs/milestones.md` tracker. The refresh was
originally bound to the milestone-close command (`/dod` step 6), and drifted
stale twice anyway:

  #26 / #27  merged as small follow-ups that never ran /dod at all
  #28        ran /dod, but recorded "PR open - awaiting human approval" —
             true when committed, false the moment it merged

Both failures share a cause: the trigger sat on a *ceremony*, which any change
can route around, and it asked a branch to record a claim that only became true
later. This check is bound to the one step nothing can skip — landing on
`main` — and it asserts the one thing that is unambiguously true there:

    `main` contains only merged work, so nothing on `main` is "in flight".

Any sentence on `main` claiming otherwise is stale by definition. That makes
this a mechanical check, not a judgement call.

WHAT IT DOES NOT DO
-------------------
It detects, it does not prevent: writing the fix automatically would mean a bot
committing to protected `main`. Detection at the merge is still the fix that
matters — drift now surfaces within a minute of landing, as a red build, rather
than being discovered milestones later by accident.

Run on branches too if you like: it only enforces when checking `main`, since
in-flight language is correct on a feature branch.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Phrases that can only be true of unlanded work. Matched case-insensitively
# inside the status regions below — not across whole files, so ordinary prose
# and the amendment logs are unaffected.
IN_FLIGHT_PHRASES = (
    "in flight",
    "in-flight",
    "pr open",
    "awaiting human approval",
    "awaiting approval",
    "awaiting review",
)

# A branch token like `feat/003-admin` or `chore/x`. If a status line names one
# that no longer exists on the remote, the branch merged and the claim is stale.
BRANCH_RE = re.compile(r"\b((?:feat|fix|chore)/[A-Za-z0-9._/-]+)")

# `- [ ] **Name** ...` — an unticked tracker row.
UNTICKED_ROW_RE = re.compile(r"^- \[ \] (.+)$", re.MULTILINE)


def remote_branches() -> set[str] | None:
    """Branch names on origin, or None if the remote can't be reached."""
    try:
        out = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return {line.split("refs/heads/", 1)[1].strip() for line in out.splitlines() if "refs/heads/" in line}


def status_regions() -> list[tuple[str, str]]:
    """(label, text) pairs for the parts of each file that claim status.

    Deliberately narrow: only the lines that make a status claim, so a
    retrospective mention of a branch elsewhere in a doc is not a false alarm.
    """
    regions: list[tuple[str, str]] = []

    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for line in claude.splitlines():
        if line.startswith("## Project status:"):
            regions.append(("CLAUDE.md '## Project status:' line", line))

    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    for line in progress.splitlines():
        if line.startswith(("**Milestone status:**", "**In flight:**", "**Open PRs:**")):
            regions.append((f"docs/progress.md '{line.split('**')[1]}**' line", line))

    return regions


def check() -> list[str]:
    problems: list[str] = []
    regions = status_regions()

    if not regions:
        problems.append(
            "No status lines found. Expected '## Project status:' in CLAUDE.md and "
            "'**In flight:**' / '**Open PRs:**' in docs/progress.md — if those "
            "headings were renamed, update this script with them."
        )
        return problems

    # 1. No in-flight language on main.
    for label, text in regions:
        lowered = text.lower()
        for phrase in IN_FLIGHT_PHRASES:
            if phrase in lowered:
                # "**In flight:** nothing" is the label itself, correctly answered.
                if phrase in ("in flight", "in-flight") and re.search(
                    r"\*\*in flight:\*\*\s*(nothing|none)", lowered
                ):
                    continue
                problems.append(
                    f"{label} says {phrase!r}, but `main` only contains merged work.\n"
                    f"      -> {text.strip()[:160]}"
                )

    # 2. No references to branches that have already merged and been deleted.
    branches = remote_branches()
    if branches is None:
        print("  note: remote unreachable, skipping the deleted-branch check", file=sys.stderr)
    else:
        for label, text in regions:
            for branch in BRANCH_RE.findall(text):
                if branch not in branches:
                    problems.append(
                        f"{label} names branch {branch!r}, which no longer exists on origin "
                        f"(it merged) — so the claim around it is stale."
                    )

    # 3. No unticked tracker row for work that has already landed.
    tracker = (ROOT / "docs" / "milestones.md").read_text(encoding="utf-8")
    for row in UNTICKED_ROW_RE.findall(tracker):
        if branches is not None:
            for branch in BRANCH_RE.findall(row):
                if branch not in branches:
                    problems.append(
                        f"docs/milestones.md has an unticked tracker row naming branch "
                        f"{branch!r}, which merged and was deleted — tick the box.\n"
                        f"      -> {row.strip()[:160]}"
                    )
        if re.search(r"\bmerged\b", row, re.IGNORECASE):
            problems.append(
                f"docs/milestones.md has an unticked row that says 'merged' — tick the box.\n"
                f"      -> {row.strip()[:160]}"
            )

    return problems


def current_branch() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="run the checks even when not on main (useful locally before opening a PR)",
    )
    args = parser.parse_args()

    branch = current_branch()
    if not args.force and branch != "main":
        print(f"On '{branch}', not main — status freshness is only enforced on main. Skipping.")
        return 0

    problems = check()
    if not problems:
        print("Status surfaces are consistent with main: nothing claims to be unfinished.")
        return 0

    print(f"\nStale status on main — {len(problems)} problem(s):\n", file=sys.stderr)
    for problem in problems:
        print(f"  x {problem}\n", file=sys.stderr)
    print(
        "`main` only ever contains merged work, so no status surface on it may describe\n"
        "work as in flight, awaiting review, or unticked. Update CLAUDE.md's status line,\n"
        "docs/progress.md, and the docs/milestones.md tracker, then push the fix.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
