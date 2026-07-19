#!/usr/bin/env python3
"""Decide from the DIFF whether a branch needs an independent docs audit.

WHY THIS EXISTS
---------------
Documentation defects in this repo have never been style problems. They have
been defects of *fact*, written in fluent English, that survived because the
author re-read their own prose and saw what they meant:

  * `docs/progress.md` asserted a security-critical list contradicting the
    constitution — and a milestone was reviewed on the strength of it.
  * Three separate documents each defined the design tokens.
  * An app-shell spec still called the design system "a later concern" after
    it shipped.
  * `CLAUDE.md` claimed a guarantee its trigger did not provide.
  * A constitution amendment said "six paths" when the real number was 11 —
    a `head -6` reported as a total.

None of those needed a compiler. All of them needed a second reader who was
not the author. This decides when to get one:

    python scripts/check_docs_trigger.py            # vs origin/main
    python scripts/check_docs_trigger.py main       # vs a given base

Exits 1 when an audit is warranted, so a workflow can act on it.

DELIBERATELY NOT TRIGGERED by a small edit. A typo fix or a one-line note does
not need an auditor, and firing on everything is how a check becomes noise
people learn to skip.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Binding documents: any change at all is worth a look, because everything
# else in the repo is measured against them.
BINDING = (
    r"^specs/000-constitution\.md$",
    r"^CLAUDE\.md$",
    r"^docs/security\.md$",
    r"^docs/requirements\.md$",
)

# Ordinary prose: worth an audit past a threshold, not for a typo.
PROSE = (r"^docs/.*\.md$", r"^specs/.*\.md$", r"^README\.md$")

# Below this many changed prose lines, a diff is a tweak, not a rewrite.
PROSE_LINE_THRESHOLD = 40


def diff_numstat(base: str) -> list[tuple[int, int, str]]:
    try:
        out = subprocess.run(
            ["git", "diff", "--numstat", f"{base}...HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        print(f"Could not diff against {base!r}.", file=sys.stderr)
        raise SystemExit(2)

    rows: list[tuple[int, int, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if added == "-":          # binary
            continue
        rows.append((int(added), int(removed), path.replace("\\", "/")))
    return rows


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    rows = diff_numstat(base)

    binding_hits = [
        (path, added + removed)
        for added, removed, path in rows
        if any(re.search(p, path) for p in BINDING)
    ]
    prose_lines = sum(
        added + removed
        for added, removed, path in rows
        if any(re.search(p, path) for p in PROSE)
        and not any(re.search(b, path) for b in BINDING)
    )
    prose_files = [
        path
        for _, _, path in rows
        if any(re.search(p, path) for p in PROSE)
        and not any(re.search(b, path) for b in BINDING)
    ]

    reasons: list[str] = []
    if binding_hits:
        for path, changed in binding_hits:
            reasons.append(
                f"binding document changed: {path} ({changed} lines) — everything "
                "else in the repo is measured against it"
            )
    if prose_lines >= PROSE_LINE_THRESHOLD:
        reasons.append(
            f"{prose_lines} lines of prose changed across {len(prose_files)} file(s) "
            f"(threshold {PROSE_LINE_THRESHOLD})"
        )

    if not reasons:
        print(
            f"No docs audit needed against {base}: no binding document changed, and "
            f"{prose_lines} prose lines is under the {PROSE_LINE_THRESHOLD}-line threshold.\n"
            "A typo fix does not need an auditor — firing on everything is how a check "
            "becomes noise."
        )
        return 0

    print(f"An independent docs audit is WARRANTED against {base}:\n")
    for reason in reasons:
        print(f"  ! {reason}")
    print(
        "\nSpawn `docs-auditor` diff-scoped and in the background, passing the model\n"
        'explicitly (`model: "sonnet"`). Give it the diff AND the binding documents —\n'
        "a contradiction lives between the diff and a file the diff never touched.\n"
        "It reports defects of fact and consistency only; it never edits for style."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
