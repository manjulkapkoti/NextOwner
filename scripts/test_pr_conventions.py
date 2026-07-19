#!/usr/bin/env python3
"""Tests for both PR-convention guards (hook + CI check).

Run:  python scripts/test_pr_conventions.py

These guards block commits and PRs, so a false positive is not a nuisance — it
is a wall. The first version of the CI check failed on its own pull request,
because that PR's body quoted the forbidden strings in order to document them.
The "documents the rule" cases below are that bug, kept permanently.

Deliberately dependency-free (no pytest): these run in CI on a bare Python step,
beside the checker itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "guard_pr_conventions.py"
CHECK = ROOT / "scripts" / "check_pr_conventions.py"

BLOCK, ALLOW = 2, 0
TMP = Path(tempfile.mkdtemp(prefix="pr-conventions-tests-"))


def write(name: str, text: str) -> Path:
    path = TMP / name
    path.write_text(text, encoding="utf-8")
    return path


# ── fixtures ─────────────────────────────────────────────────────────────────

AGENT_TRAILER = write(
    "agent_trailer.txt",
    "feat: a thing\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n",
)
HUMAN_TRAILER = write(
    "human_trailer.txt",
    "feat: a thing\n\nCo-Authored-By: Dana Patel <dana@example.com>\n",
)
# The regression: a message that *documents* the rule must not trip it.
DOCUMENTS_RULE = write(
    "documents_rule.txt",
    "chore: enforce PR conventions\n\n"
    "Blocks a `Co-Authored-By: Claude` trailer and the "
    '"Generated with Claude Code" footer before they are written.\n\n'
    "A human Co-Authored-By trailer stays allowed.\n",
)
GOOD_BODY = write("good_body.md", "## What was shipped\n\n- Buyers can browse listings.\n")
BODY_DOCUMENTS_RULE = write(
    "body_documents_rule.md",
    "## What was shipped\n\n"
    "- A `Co-Authored-By: Claude` trailer can no longer reach a commit.\n"
    '- The "Generated with Claude Code" footer is blocked in a PR body.\n',
)
BODY_WITH_FOOTER = write(
    "body_footer.md",
    "## What was shipped\n\n- A thing.\n\n"
    "\U0001F916 Generated with [Claude Code](https://claude.com/claude-code)\n",
)
BODY_WITH_REVIEW = write(
    "body_review.md",
    "## What was shipped\n\n- A thing.\n\n## Review outcome\n\nThe appsec pass found...\n",
)
BODY_NO_HEADING = write("body_no_heading.md", "## Overview\n\nSome prose.\n")


# ── hook cases: (name, command, expected exit) ───────────────────────────────

HOOK_CASES = [
    ("commit: inline agent trailer", 'git commit -m "x\n\nCo-Authored-By: Claude <a@b>"', BLOCK),
    ("commit: agent trailer in a file", f"git commit -F {AGENT_TRAILER}", BLOCK),
    ("commit: clean message", 'git commit -m "feat: a clean message"', ALLOW),
    ("commit: HUMAN co-author", f"git commit -F {HUMAN_TRAILER}", ALLOW),
    ("commit: DOCUMENTS the rule", f"git commit -F {DOCUMENTS_RULE}", ALLOW),
    ("pr create: good body", f"gh pr create --base main --body-file {GOOD_BODY}", ALLOW),
    ("pr create: body DOCUMENTS rule", f"gh pr create --body-file {BODY_DOCUMENTS_RULE}", ALLOW),
    ("pr create: real footer", f"gh pr create --body-file {BODY_WITH_FOOTER}", BLOCK),
    ("pr create: review section", f"gh pr create --body-file {BODY_WITH_REVIEW}", BLOCK),
    ("pr create: no What was shipped", f"gh pr create --body-file {BODY_NO_HEADING}", BLOCK),
    ("pr edit: real footer inline", 'gh pr edit 36 --body "## What was shipped\n\n- x\n\nGenerated with [Claude Code]"', BLOCK),
    ("gh pr view untouched", "gh pr view 36 --json state", ALLOW),
    ("gh pr merge untouched", "gh pr merge 36 --squash", ALLOW),
    ("escape hatch honoured", 'git commit -m "x Co-Authored-By: Claude" # pr-conventions: skip', ALLOW),
]

# ── CI-check cases: (name, body, expected exit) ──────────────────────────────

CHECK_CASES = [
    ("body: good", GOOD_BODY.read_text(encoding="utf-8"), 0),
    ("body: DOCUMENTS the rule", BODY_DOCUMENTS_RULE.read_text(encoding="utf-8"), 0),
    ("body: real footer", BODY_WITH_FOOTER.read_text(encoding="utf-8"), 1),
    ("body: review section", BODY_WITH_REVIEW.read_text(encoding="utf-8"), 1),
    ("body: no What was shipped", BODY_NO_HEADING.read_text(encoding="utf-8"), 1),
]


def run_hook(command: str) -> int:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).returncode


def run_check(body: str) -> int:
    event = TMP / "event.json"
    event.write_text(json.dumps({"pull_request": {"body": body}}), encoding="utf-8")
    env = dict(os.environ, GITHUB_EVENT_PATH=str(event), PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, str(CHECK), "--base", "main"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(ROOT),
    ).returncode


def main() -> int:
    failures = 0

    print("hook (.claude/hooks/guard_pr_conventions.py)")
    for name, command, expected in HOOK_CASES:
        actual = run_hook(command)
        ok = actual == expected
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:34s} {'BLOCK' if actual == BLOCK else 'allow'}")

    print("\nCI check (scripts/check_pr_conventions.py)")
    for name, body, expected in CHECK_CASES:
        actual = run_check(body)
        ok = actual == expected
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:34s} {'FAIL' if actual else 'pass'}")

    total = len(HOOK_CASES) + len(CHECK_CASES)
    print(f"\n{total - failures}/{total} cases behaved as specified.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
