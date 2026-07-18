#!/usr/bin/env python3
"""Lint a frontend file immediately after it is edited.

Catches the mistakes that are cheapest to fix in the same breath as the edit —
an unused import left after a refactor, a hook dependency, a stray `any` — so
they surface now instead of at the `/dod` gate ten edits later.

Scope is deliberately narrow:

  * only `app/src/**` TypeScript/TSX files, since that is where eslint is
    configured;
  * **eslint only, not `tsc`** — a project-wide typecheck runs several seconds
    and would tax every single edit. `tsc -b` still runs in `/dod` and in CI,
    where a few seconds cost nothing.

Never blocks. Lint findings are advisory here: the edit may be one of several
that only make sense together, and a half-finished refactor failing the tool
call would be worse than the warning. `/dod` and CI are the gates that stop
things; this is a nudge.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "app"
SUFFIXES = {".ts", ".tsx"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    raw_path = (payload.get("tool_input") or {}).get("file_path")
    if not raw_path:
        return 0

    path = Path(raw_path)
    if path.suffix not in SUFFIXES:
        return 0

    try:
        relative = path.resolve().relative_to(APP / "src")
    except ValueError:
        return 0  # Outside app/src — not eslint's territory here.

    try:
        result = subprocess.run(
            # Default (stylish) formatter — `compact` was removed from core
            # ESLint and asking for it turns every run into an install nag.
            ["npx", "eslint", str(path.resolve())],
            cwd=APP,
            capture_output=True,
            text=True,
            timeout=90,
            shell=sys.platform == "win32",  # npx is a .cmd shim on Windows
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0

    if result.returncode == 0:
        return 0

    output = (result.stdout or result.stderr).strip()
    if output:
        print(f"eslint — src/{relative.as_posix()}:\n{output}", file=sys.stderr)
    return 0  # Advisory only; never block the edit.


if __name__ == "__main__":
    sys.exit(main())
