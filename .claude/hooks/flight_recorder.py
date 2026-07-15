#!/usr/bin/env python3
"""Session flight recorder — the crash-proof half of the session-recovery strategy.

Run by the `Stop` hook after EVERY turn (see .claude/settings.json), so a fresh
session can reconstruct where work left off even if the previous one died
abruptly (crash, closed tab, usage limit mid-turn) before /checkpoint ran.

It is deliberately harmless: it only READS git and WRITES the single gitignored
file `.claude/session-state.md`. It never commits, stages, or mutates git state,
so it cannot interfere with the deliberate git orchestration the workflow does.

The semantic "next action" lives in docs/progress.md (written by /checkpoint);
the red tests are the real to-do list (surfaced by /resume). This file is just
the mechanical snapshot that ties them to the live repo. See docs/session_recovery.md.
"""

from __future__ import annotations

import datetime
import os
import subprocess

# Repo root = two levels up from this script (.claude/hooks/flight_recorder.py),
# so it works regardless of the hook's working directory or shell.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return r.stdout.strip()
    except Exception as e:  # never let the recorder break a turn
        return f"(git unavailable: {e})"


def in_progress_op() -> str:
    g = os.path.join(ROOT, ".git")
    if os.path.exists(os.path.join(g, "MERGE_HEAD")):
        return "MERGE in progress"
    if os.path.isdir(os.path.join(g, "rebase-merge")) or os.path.isdir(
        os.path.join(g, "rebase-apply")
    ):
        return "REBASE in progress"
    return ""


def main() -> None:
    branch = git("branch", "--show-current") or "(detached HEAD)"
    status = git("status", "--short") or "(working tree clean)"
    recent = git("log", "--oneline", "-6")
    ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    op = in_progress_op()
    op_line = f"\n- **⚠ Git op in progress:** {op}" if op else ""

    body = f"""# Session flight recorder — auto-written every turn (do not edit)

_Last turn recorded: {ts}_

- **Branch:** `{branch}`{op_line}
- **Recent commits:**

```
{recent}
```

- **Uncommitted (working tree):**

```
{status}
```

> Mechanical crash-recovery snapshot. The semantic "▶ next action" lives in
> `docs/progress.md`; the failing tests are the real to-do list. Start a new
> session with **/resume**, which reconciles this against the live repo + tests.
> Full design: `docs/session_recovery.md`.
"""

    dest = os.path.join(ROOT, ".claude", "session-state.md")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(body)


if __name__ == "__main__":
    main()
