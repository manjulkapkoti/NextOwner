#!/usr/bin/env python3
"""Tests for the squash-merge body guard (`.claude/hooks/guard_squash_merge.py`).

Run:  python scripts/test_squash_merge_guard.py

This guard blocks a merge — a more consequential action than the commit guard
it's modeled on — so a false positive is a wall across every future
`/close-feature`, not a nuisance. Mirrors `test_pr_conventions.py`'s approach:
drive the hook exactly as Claude Code does, over stdin JSON, and assert the
exit code.

Deliberately dependency-free (no pytest): matches the sibling test file, and
keeps this runnable as a bare CI step.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "guard_squash_merge.py"

BLOCK, ALLOW = 2, 0
TMP = Path(tempfile.mkdtemp(prefix="squash-merge-guard-tests-"))


def write(name: str, text: str) -> Path:
    path = TMP / name
    path.write_text(text, encoding="utf-8")
    return path


SHORT_BODY_FILE = write("short.md", "One short summary line.\n")
LONG_BODY_FILE = write(
    "long.md",
    "* docs: spec 005\n\nParagraph one about the spec.\n\n"
    "* feat: slice 1\n\nParagraph about slice 1.\n\n"
    "* feat: slice 2\n\nParagraph about slice 2.\n",
)

# (name, command, expected exit)
CASES = [
    (
        "no gh pr merge at all — untouched",
        "gh pr view 38 --json state",
        ALLOW,
    ),
    (
        "gh pr merge --merge (not squash) — untouched",
        "gh pr merge 38 --merge --delete-branch",
        ALLOW,
    ),
    (
        "gh pr merge --rebase (not squash) — untouched",
        "gh pr merge 38 --rebase --delete-branch",
        ALLOW,
    ),
    (
        "squash with no --body at all",
        "gh pr merge 38 --squash --delete-branch",
        BLOCK,
    ),
    (
        "squash with an empty body — the title-only case",
        'gh pr merge 38 --squash --delete-branch --body ""',
        ALLOW,
    ),
    (
        "squash with one short inline body line",
        'gh pr merge 38 --squash --delete-branch --body "One short summary line."',
        ALLOW,
    ),
    (
        "squash with a two-line inline body",
        'gh pr merge 38 --squash --delete-branch --body "Line one.\nLine two."',
        BLOCK,
    ),
    (
        "squash with a short --body-file",
        f"gh pr merge 38 --squash --delete-branch --body-file {SHORT_BODY_FILE}",
        ALLOW,
    ),
    (
        "squash with a long --body-file (the M5 #38 shape)",
        f"gh pr merge 38 --squash --delete-branch --body-file {LONG_BODY_FILE}",
        BLOCK,
    ),
    (
        "squash with -F shorthand for a long body file",
        f"gh pr merge 38 --squash --delete-branch -F {LONG_BODY_FILE}",
        BLOCK,
    ),
    (
        "squash with -b shorthand inline",
        'gh pr merge 38 --squash --delete-branch -b "One line."',
        ALLOW,
    ),
    (
        "escape hatch honoured even with no body",
        "gh pr merge 38 --squash --delete-branch # merge-body: skip",
        ALLOW,
    ),
    (
        "read-only gh pr commands untouched",
        "gh pr checks 38 --watch",
        ALLOW,
    ),
]


def run_hook(command: str) -> int:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).returncode


def main() -> int:
    failures = 0
    print("hook (.claude/hooks/guard_squash_merge.py)")
    for name, command, expected in CASES:
        actual = run_hook(command)
        ok = actual == expected
        failures += 0 if ok else 1
        verdict = 'BLOCK' if actual == BLOCK else 'allow'
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:52s} {verdict}")

    print(f"\n{len(CASES) - failures}/{len(CASES)} cases behaved as specified.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
