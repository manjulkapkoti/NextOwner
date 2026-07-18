#!/usr/bin/env python3
"""Block `git commit` while on `main`.

`main` is protected (constitution Article 3 §3): it is updated only by merging a
green PR, never by a direct commit. There is already a `.git/hooks/pre-commit`
guard, but git hooks live in `.git/` and so are **not cloned** — a fresh clone,
a new machine, or a worktree silently loses the protection. This hook lives in
the repo, so it travels with it.

Exit 2 blocks the tool call and shows stderr to the agent.

Deliberate escape hatch: `--no-verify` in the command is honoured, matching the
local git hook, so a genuine one-off stays possible without editing this file.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

# Matches a real commit invocation, not `git log --grep=commit` or similar.
COMMIT_RE = re.compile(r"\bgit\s+(?:-[^\s]+\s+)*commit\b")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Never break the session over a malformed payload.

    command = (payload.get("tool_input") or {}).get("command", "")
    if not COMMIT_RE.search(command):
        return 0
    if "--no-verify" in command:
        return 0

    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0  # Not a git repo, or git unavailable — nothing to guard.

    if branch != "main":
        return 0

    print(
        "Blocked: you are on `main`, which is updated only by merging a green PR "
        "(constitution Article 3 §3).\n\n"
        "Cut a branch first:\n"
        "    git checkout -b feat/<NNN>-<slug>\n\n"
        "then commit there and open a PR. If this genuinely needs to bypass the "
        "rule, add --no-verify.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
