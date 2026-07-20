#!/usr/bin/env python3
"""Block a squash-merge that would land a wall of text on `main`.

`gh pr merge --squash` with no explicit `--body` does not leave the merge
commit's body blank — it falls back to GitHub's own default, which
concatenates the full message of every commit on the branch. A milestone
branch on this project routinely carries fifteen-plus slice/fix/docs commits,
each deliberately written with its own multi-paragraph rationale
(`docs/git_strategy.md` § Conventions) — exactly the detail that belongs on
the *branch*, and exactly what must not land wholesale on `main`. It happened
for real closing M5 (PR #38): the squash commit `gh` produced was the
verbatim concatenation of twenty commits.

The owner's rule (memory `squash-merge-commit-message`): the commit that
lands on `main` is **one line, two at most** — the PR title, optionally with
a single short summary line. So this hook requires an explicit `-b`/`--body`
(or `-F`/`--body-file`) on every `--squash` merge — even an empty one is
fine, that is the "one line" case — and if the body has content, caps it at
one non-blank line (title + 1 = 2 total).

Exit 2 blocks the tool call and shows stderr to the agent.

Scope: `gh pr merge ... --squash` only. `--merge` and `--rebase` do not share
this failure mode — GitHub does not synthesize a body for either. Only the
long `--squash` flag is matched, not the `-s` shorthand — `/close-feature`
and `docs/git_strategy.md` always spell it out, and the CI backstop
(`scripts/check_last_main_commit.py`) catches anything that reaches `main`
by whichever flag form.

This is the hook half of a two-layer guard, mirroring
`guard_pr_conventions.py`: it catches the mistake *before* the command runs,
for the fast feedback. The CI script above is the backstop for anything that
reaches `main` another way — a merge from the GitHub web UI, a different
machine, a hook that never fired.

Escape hatch: `merge-body: skip` in the command, matching the
`pr-conventions: skip` convention in `guard_pr_conventions.py`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# A Windows console defaults to cp1252; these messages contain an em-dash.
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MERGE_RE = re.compile(r"\bgh(?:\.exe)?\b[^|;]*\bpr\s+merge\b")
SQUASH_RE = re.compile(r"--squash\b")

BODY_FILE_RE = re.compile(r"(?:--body-file|-F)\b[=\s]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
BODY_INLINE_RE = re.compile(r"(?:--body|-b)\b[=\s]+(?:\"([^\"]*)\"|'([^']*)')")

# + the title (always present — the PR title if -t/--subject is omitted, which
# is itself already one line) = 2 total, matching the owner's "1 or 2 lines".
MAX_BODY_LINES = 1


def body_text(command: str) -> tuple[bool, str | None]:
    """(was a body argument given at all, its resolved text if known)."""
    file_match = BODY_FILE_RE.search(command)
    if file_match:
        raw = next((g for g in file_match.groups() if g), None)
        if raw == "-":
            return True, None  # stdin — can't introspect statically, don't block
        try:
            return True, Path(raw).read_text(encoding="utf-8", errors="replace")
        except OSError:
            # An unreadable path is `gh`'s problem to report, not this hook's
            # to second-guess — the CI backstop still covers the result.
            return True, None

    inline_match = BODY_INLINE_RE.search(command)
    if inline_match:
        return True, next((g for g in inline_match.groups() if g is not None), "")

    return False, None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Never break the session over a malformed payload.

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or "merge-body: skip" in command:
        return 0
    if not (MERGE_RE.search(command) and SQUASH_RE.search(command)):
        return 0

    given, text = body_text(command)

    if not given:
        print(
            "Blocked: `gh pr merge --squash` with no explicit --body (or "
            "--body-file) lets GitHub fall back to its own default, which "
            "concatenates every commit on the branch into the merge commit on "
            "`main` — this is exactly how M5's squash commit (PR #38) ended up as "
            "twenty commits' worth of paragraphs.\n\n"
            "Add an explicit body, e.g.:\n"
            '    gh pr merge <n> --squash --delete-branch --body "One short summary line."\n\n'
            'An empty body is fine too (--body "") — the merge commit is then just '
            "the PR title, which satisfies the owner's rule: the commit on `main` "
            "is one line, two at most.\n\n"
            "For a deliberate one-off, add `merge-body: skip` to the command.",
            file=sys.stderr,
        )
        return 2

    if text is None:
        return 0  # stdin body or unreadable file — nothing more to check here

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > MAX_BODY_LINES:
        print(
            f"Blocked: this squash-merge body is {len(lines)} lines. The owner's "
            "rule (memory `squash-merge-commit-message`): the commit on `main` is "
            f"one line, two at most — the PR title plus at most {MAX_BODY_LINES} "
            "short line of body.\n\n"
            "Body given:\n"
            + "\n".join(f"  {ln}" for ln in lines)
            + '\n\nShorten it to one line, or drop --body entirely to use the title '
            'alone (pass --body "" explicitly for no body at all).\n\n'
            "For a deliberate one-off, add `merge-body: skip` to the command.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
