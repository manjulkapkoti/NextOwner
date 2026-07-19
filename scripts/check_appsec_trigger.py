#!/usr/bin/env python3
"""Decide from the DIFF whether a milestone needs an independent appsec pass.

WHY THIS EXISTS
---------------
The security-critical milestone list (`M1/M2/M3/M5/M7/M8/M10`) is an
enumeration written at planning time, guessing which milestones would turn out
to be security-relevant. On 2026-07-19 it was wrong: M3 was not on it, ran the
independent pass anyway — for the accidental reason that a stale note claimed
it was — and that pass found a **blocking curation bypass** (a seller could
republish unreviewed content via pause → edit → resume). Following the list
literally would have shipped it.

A list predicts. A diff describes. This checks what the branch actually
touched, so a milestone nobody flagged still gets caught:

    python scripts/check_appsec_trigger.py            # vs origin/main
    python scripts/check_appsec_trigger.py main       # vs a given base

The list remains a **floor** — those milestones always get the pass. This can
only ever escalate, never excuse: it prints what it found and why, and exits 1
when a pass is required so a workflow can act on it.

It is deliberately noisy in one direction. A false "you need a review" costs a
few minutes of Sonnet; a false "you don't" costs a vulnerability in a product
whose stated #1 priority is security.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (label, why it matters, path regex, added-line regex or None for "any change")
TRIGGERS: list[tuple[str, str, str, str | None]] = [
    (
        "permission boundary",
        "a trust boundary changed — every privilege check lives here",
        r"backend/app/permissions\.py$",
        None,
    ),
    (
        "authentication",
        "token issuance, hashing or session handling changed",
        r"backend/app/(security|routers/auth)\.py$",
        None,
    ),
    (
        "new or changed route",
        "a new endpoint is new attack surface and needs its forbidden-path test",
        r"backend/app/routers/.*\.py$",
        r"^\+\s*@router\.(get|post|put|patch|delete)",
    ),
    (
        "response model / data exposure",
        "a schema change can leak private or identity fields by shape alone",
        r"backend/app/schemas\.py$",
        r"^\+\s*(class \w+|.*(company_name|website_url|detailed_financials|email|owner_id|password))",
    ),
    (
        "status state machine",
        "a transition is a privilege decision; composed transitions can bypass a gate",
        r"backend/app/routers/.*\.py$",
        r"^\+.*(_transition\(|\.status\s*=(?!=))",
    ),
    (
        "file uploads",
        "uploads are hostile input — type, size and path confinement",
        r"backend/app/(storage\.py|routers/.*upload.*\.py)$",
        None,
    ),
    (
        "money",
        "money fields are a privileged flow; the server must derive them",
        r"backend/app/(models|schemas)\.py$",
        r"^\+.*(Decimal|Money)",
    ),
    (
        "websockets",
        "connect-time authN and per-message membership authZ",
        r"backend/app/.*\.py$",
        r"^\+.*(WebSocket|websocket)",
    ),
]


def diff_against(base: str) -> str:
    try:
        # utf-8 + replace, explicitly: the default codec on Windows is cp1252
        # and chokes on both the em-dashes in our comments and any binary blob
        # in the diff. `--no-color` and text-only paths keep the output clean.
        return subprocess.run(
            ["git", "diff", "--no-color", f"{base}...HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        print(f"Could not diff against {base!r}.", file=sys.stderr)
        raise SystemExit(2)


def scan(diff: str) -> list[tuple[str, str, str]]:
    """(label, why, evidence) for every trigger the diff fires."""
    current_file = ""
    added_by_file: dict[str, list[str]] = {}
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            added_by_file.setdefault(current_file, [])
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            added_by_file[current_file].append(line)

    fired: list[tuple[str, str, str]] = []
    for label, why, path_re, add_re in TRIGGERS:
        for path, added in added_by_file.items():
            if not re.search(path_re, path):
                continue
            if add_re is None:
                if added:
                    fired.append((label, why, path))
                    break
            else:
                match = next((a for a in added if re.search(add_re, a)), None)
                if match:
                    fired.append((label, why, f"{path}: {match.strip()[:90]}"))
                    break
    return fired


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    fired = scan(diff_against(base))

    if not fired:
        print(
            f"No appsec trigger fired against {base}. The diff touches no permission "
            "boundary, route, response model, state transition, upload path, money "
            "field or websocket.\n"
            "The milestone list still applies: M1/M2/M3/M5/M7/M8/M10 always get the pass."
        )
        return 0

    print(f"An independent appsec pass is REQUIRED — {len(fired)} trigger(s) fired against {base}:\n")
    for label, why, evidence in fired:
        print(f"  ! {label}")
        print(f"      why: {why}")
        print(f"      in : {evidence}\n")
    print(
        "Run it diff-scoped and in the background, passing the model explicitly\n"
        '(`model: "sonnet"`, or "opus" for M5). See .claude/skills/run-milestone.\n'
        "\nThis check escalates only; it never excuses a milestone on the list."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
