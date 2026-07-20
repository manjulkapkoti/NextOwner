#!/usr/bin/env python3
"""Fail if the commit that just landed on `main` is a wall of text.

WHY THIS EXISTS
---------------
The owner's rule (memory `squash-merge-commit-message`): the squash-merge
commit that lands on `main` is short — one line, two at most — never the raw
concatenation of every commit on the branch. `gh pr merge --squash` produces
exactly that concatenation by default when no `--body` is given, and it
happened for real closing M5 (PR #38): a milestone branch with twenty commits
landed as a single commit whose body was all twenty commits' full messages,
one after another.

`.claude/hooks/guard_squash_merge.py` blocks the mistake before the merge
command runs, which is the useful, fast feedback. But hooks live in agent
settings, so a merge from the GitHub web UI, a different machine, or a human
merging by hand never goes through it — this is the backstop that runs where
nothing can route around it: on the artefact itself, once it has landed.

WHAT IT DOES NOT DO
-------------------
It detects, it does not prevent — rewriting history on `main` from CI would be
worse than the defect it is catching. A red build within a minute of the merge
is the point, the same trade `check_status_freshness.py` makes.

USAGE
    python scripts/check_last_main_commit.py
"""

from __future__ import annotations

import subprocess
import sys

# + the title = 2 total, matching the owner's "1 line, 2 at most" — the same
# rule guard_squash_merge.py enforces on the way in.
MAX_LINES = 2


def main() -> int:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]

    if len(lines) <= MAX_LINES:
        print(f"HEAD's commit message is {len(lines)} line(s) — within the {MAX_LINES}-line rule.")
        return 0

    print(
        f"HEAD's commit message is {len(lines)} lines; the owner's rule (memory "
        f"`squash-merge-commit-message`) is at most {MAX_LINES} — the PR title, "
        "optionally with one short summary line.\n\n"
        "Message:\n" + "\n".join(f"  {ln}" for ln in lines) + "\n\n"
        "This is almost always `gh pr merge --squash` falling back to its default "
        "body (every commit on the branch, concatenated) because no --body was "
        "given. .claude/hooks/guard_squash_merge.py should have blocked this "
        "before it happened — if it didn't, the merge did not go through the "
        "agent's Bash tool (a browser merge, a different machine, a hook that "
        "didn't fire).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
