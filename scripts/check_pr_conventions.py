#!/usr/bin/env python3
"""Fail if a PR carries agent attribution, or a body that isn't the owner's shape.

WHY THIS EXISTS
---------------
The owner's PR conventions (memory `pr-presentation-format`) are absolute: no
agent attribution anywhere — no "Generated with Claude Code" footer in a body,
no `Co-Authored-By: Claude` trailer in a commit — and a body that leads with a
bulleted `## What was shipped` and carries no review or decision narrative.

They were written down, and were still broken on PR #36: all twelve commits
carried the trailer and the body carried the footer. The rule was never the
problem — relying on an agent to recall it was. So the enforcement is bound to
the artefact instead of to anyone's memory, the same move the status-freshness
check made (constitution, 2026-07-19: "the refresh sat on a ceremony any change
can route around").

RELATIONSHIP TO THE HOOK
------------------------
`.claude/hooks/guard_pr_conventions.py` blocks the mistake *before* the command
runs, which is the fast, useful feedback. But hooks live in agent settings and a
git `pre-commit` lives in `.git/`: neither survives a fresh clone, another
machine, or a human committing by hand. This is the backstop that runs where
nothing can route around it — CI, on the PR itself.

Detection, not prevention: rewriting someone's commits from CI would be worse
than the defect. A red build within a minute is the point.

USAGE
    python scripts/check_pr_conventions.py [--base main]

The PR body is read from the GitHub event payload (`GITHUB_EVENT_PATH`) when
present; locally, or on a push build, only the commits are checked and that is
reported rather than silently skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# A Windows console defaults to cp1252, and these messages contain an em-dash.
# Without this, a lint failure could surface as a UnicodeEncodeError rather than
# the explanation it is trying to print.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ATTRIBUTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"co-authored-by:\s*(claude|anthropic|gpt|copilot|codex|devin)", re.I),
        "an agent `Co-Authored-By:` trailer",
    ),
    (
        re.compile(r"generated\s+with\s+\[?\s*claude", re.I),
        'a "Generated with Claude Code" footer',
    ),
    # The pattern needs the character; the *label* must not print it — a Windows
    # console is often cp1252 and would raise on the way out, turning a lint
    # failure into a crash.
    (re.compile("\U0001F916"), "the robot attribution emoji"),
    (
        re.compile(r"\b(?:written|authored|created|generated)\s+by\s+claude\b", re.I),
        'an "authored by Claude" line',
    ),
]

REQUIRED_HEADING = re.compile(r"^#{1,3}\s*What was shipped\s*$", re.I | re.M)

# Matched on heading text only: "review" appears legitimately in this product's
# prose (`pending_review`, the curation queue), so a bare word match is noise.
HEADING_RE = re.compile(r"^#{1,6}\s*(.+?)\s*$", re.M)
FORBIDDEN_HEADING_WORDS = (
    "review",
    "decision",
    "open question",
    "next step",
    "not merging",
    "approval",
    "findings",
    "trade-off",
    "tradeoff",
)


def commit_messages(base: str) -> list[tuple[str, str]]:
    """(sha, full message) for each commit this branch adds over `base`."""
    try:
        shas = subprocess.run(
            ["git", "rev-list", f"origin/{base}..HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        try:
            shas = subprocess.run(
                ["git", "rev-list", f"{base}..HEAD"],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout.split()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return []

    out: list[tuple[str, str]] = []
    for sha in shas:
        message = subprocess.run(
            ["git", "log", "-1", "--format=%B", sha],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        out.append((sha[:8], message))
    return out


def pr_body() -> str | None:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            event = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    pull = event.get("pull_request") or {}
    return pull.get("body") or ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="main")
    args = parser.parse_args()

    problems: list[str] = []

    for sha, message in commit_messages(args.base):
        for pattern, label in ATTRIBUTION_PATTERNS:
            if pattern.search(message):
                subject = message.strip().splitlines()[0][:60]
                problems.append(f"commit {sha} ({subject}) carries {label}")

    body = pr_body()
    if body is None:
        print("note: no PR event payload — checking commits only.", file=sys.stderr)
    elif body.strip():
        for pattern, label in ATTRIBUTION_PATTERNS:
            if pattern.search(body):
                problems.append(f"the PR body carries {label}")
        if not REQUIRED_HEADING.search(body):
            problems.append(
                "the PR body does not lead with a `## What was shipped` section"
            )
        for heading in HEADING_RE.findall(body):
            lowered = heading.lower()
            if any(word in lowered for word in FORBIDDEN_HEADING_WORDS):
                problems.append(
                    f'the PR body section "{heading}" is review/process narrative — '
                    "that belongs in chat, not in the body"
                )

    if problems:
        print("PR conventions violated:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nThe rules (memory `pr-presentation-format`):\n"
            "  * NO agent attribution anywhere - no robot-emoji footer in a PR body, no\n"
            "    `Co-Authored-By: Claude` trailer in a commit.\n"
            "  * The body leads with a bulleted `## What was shipped`, then prose\n"
            "    under bold lead-in labels, then tests/checks.\n"
            "  * Review outcomes, decisions and deferrals go in CHAT, not the body.\n\n"
            "To fix trailers already committed on a branch:\n"
            "  git filter-branch -f --msg-filter \"sed '/^Co-Authored-By: Claude/d'\" "
            f"{args.base}..HEAD && git push --force-with-lease",
            file=sys.stderr,
        )
        return 1

    print("PR conventions: clean — no agent attribution, body shape is correct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
