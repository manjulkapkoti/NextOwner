#!/usr/bin/env python3
"""Block agent attribution and malformed PR bodies before they are written.

The owner's PR conventions (memory `pr-presentation-format`) are simple and
absolute: **no agent attribution anywhere** — no "Generated with Claude Code"
footer in a PR body, no `Co-Authored-By: Claude` trailer in a commit — and a PR
body that leads with a bulleted `## What was shipped` and carries no review or
decision narrative (that belongs in chat).

Those rules were already written down, and were still broken on PR #36: every
commit carried the trailer and the body carried the footer. **The rule was not
the problem; relying on the agent to recall it was.** So this is bound to the
moment the mistake happens rather than to a document someone must remember to
read — the same reasoning that moved status-freshness onto CI (constitution,
2026-07-19: "the refresh sat on a ceremony any change can route around").

Exit 2 blocks the tool call and shows stderr to the agent.

Scope: `git commit`, `gh pr create`, `gh pr edit`. Read-only PR commands
(`view`, `checks`, `merge`, `list`) are untouched.

Because a message is usually passed as a file (`-F`, `--body-file`) rather than
inline, this scans the command text **and** the contents of any message file it
references. Checking only the command string would miss the common case — which
is precisely how #36's trailers got through a review that was looking for them.

Escape hatch: put `pr-conventions: skip` in the command for a deliberate
one-off, matching the `--no-verify` convention in `guard_main_commit.py`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# A Windows console defaults to cp1252. These messages contain an em-dash, and
# the patterns match an emoji — without this, a lint failure could surface as a
# UnicodeEncodeError instead of the explanation it is trying to print.
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

COMMIT_RE = re.compile(r"\bgit\s+(?:-[^\s]+\s+)*commit\b")
PR_WRITE_RE = re.compile(r"\bgh(?:\.exe)?\b[^|;]*\bpr\s+(create|edit)\b")

# Any message file the command points at: `git commit -F x`, `gh pr create
# --body-file x`. Quoted forms first so a Windows path with spaces survives.
FILE_ARG_RE = re.compile(
    r"(?:--body-file|--file|-F)[=\s]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))"
)

# Attribution. Two deliberate narrowings, both learned rather than guessed:
#
#   1. A *human* `Co-Authored-By` trailer is legitimate, so only agent
#      co-authors are matched.
#   2. Every pattern is LINE-ANCHORED and code spans are stripped first, so
#      *documenting* the rule does not trip it. The CI twin of this check failed
#      on its own PR because that PR's body quoted the forbidden strings in
#      order to explain them — a guard that cannot tell "carries attribution"
#      from "talks about attribution" makes the docs unwritable.
#
# The signal is position: a real trailer or footer starts its own line, while
# prose quotes it mid-sentence or in backticks. Leading non-word characters are
# tolerated so an emoji-prefixed footer still matches.
_LEAD = r"^[^\w\n]{0,4}"

ATTRIBUTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(_LEAD + r"co-authored-by:\s*(claude|anthropic|gpt|copilot|codex|devin)", re.I | re.M),
        "an agent `Co-Authored-By:` trailer",
    ),
    (
        re.compile(_LEAD + r"generated\s+with\s+\[?\s*claude", re.I | re.M),
        'a "Generated with Claude Code" footer',
    ),
    (
        re.compile(_LEAD + r"(?:written|authored|created|generated)\s+by\s+claude\b", re.I | re.M),
        'an "authored by Claude" line',
    ),
]

# Fenced blocks and inline code spans hold *examples*, never live attribution.
_FENCED = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    return _INLINE_CODE.sub(" ", _FENCED.sub(" ", text))

REQUIRED_HEADING = re.compile(r"^#{1,3}\s*What was shipped\s*$", re.I | re.M)

# Headings that mean the body drifted into review/process narrative. Matched on
# the heading text only — "review" appears legitimately in this product's prose
# (`pending_review`, the curation queue), so a bare word match would be noise.
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


def referenced_files(command: str) -> list[str]:
    out: list[str] = []
    for match in FILE_ARG_RE.finditer(command):
        path = next((g for g in match.groups() if g), None)
        if path:
            out.append(path)
    return out


def gather_text(command: str) -> str:
    """The command plus the contents of any message file it references."""
    chunks = [command]
    for raw in referenced_files(command):
        try:
            chunks.append(Path(raw).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            # A path we can't read is not a reason to block a commit; the CI
            # check (scripts/check_pr_conventions.py) is the backstop.
            continue
    return "\n".join(chunks)


def body_text(command: str) -> str | None:
    """The PR body only — file contents, or an inline `--body "..."`."""
    for raw in referenced_files(command):
        try:
            return Path(raw).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    inline = re.search(r"--body[=\s]+(?:\"([^\"]+)\"|'([^']+)')", command)
    if inline:
        return next((g for g in inline.groups() if g), None)
    return None


def check_attribution(text: str) -> list[str]:
    stripped = strip_code(text)
    return [
        f"  - {label}"
        for pattern, label in ATTRIBUTION_PATTERNS
        if pattern.search(stripped)
    ]


def check_body_shape(body: str) -> list[str]:
    problems: list[str] = []
    if not REQUIRED_HEADING.search(body):
        problems.append(
            '  - the body must lead with a `## What was shipped` section, written as\n'
            "    bullet points: what a person can now *do* because of this PR"
        )
    for heading in HEADING_RE.findall(body):
        lowered = heading.lower()
        for word in FORBIDDEN_HEADING_WORDS:
            if word in lowered:
                problems.append(
                    f'  - the section "{heading}" is review/process narrative — that goes\n'
                    "    in chat, never in the PR body. The body records only what shipped."
                )
                break
    return problems


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Never break the session over a malformed payload.

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or "pr-conventions: skip" in command:
        return 0

    is_commit = bool(COMMIT_RE.search(command))
    is_pr_write = bool(PR_WRITE_RE.search(command))
    if not (is_commit or is_pr_write):
        return 0

    problems = check_attribution(gather_text(command))

    if is_pr_write:
        body = body_text(command)
        if body is not None:
            problems += check_body_shape(body)

    if not problems:
        return 0

    what = "PR body" if is_pr_write else "commit message"
    print(
        f"Blocked: this {what} breaks the owner's PR conventions.\n\n"
        + "\n".join(problems)
        + "\n\nThe rules (memory `pr-presentation-format`):\n"
        "  * NO agent attribution anywhere — no robot-emoji footer in a PR body, no\n"
        "    `Co-Authored-By: Claude` trailer in a commit.\n"
        "  * The PR body leads with a bulleted `## What was shipped`, then prose\n"
        "    under bold lead-in labels, then tests/checks.\n"
        "  * Review outcomes, decisions and deferrals are raised in CHAT, never\n"
        "    in the PR body.\n\n"
        "Fix the message and retry. For a deliberate one-off, add\n"
        "`pr-conventions: skip` to the command.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
