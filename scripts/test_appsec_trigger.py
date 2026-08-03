"""Tests for `check_appsec_trigger.py` — the guard that decides when a branch
needs an independent security review.

**Why this file exists.** On 2026-08-03 the M13 branch added `seed/make_admin.py`,
a CLI whose entire purpose is setting `user.is_admin = 1`, and the trigger
reported *"No appsec trigger fired — the diff touches no permission boundary."*
The pass happened anyway, because a human noticed. That is exactly the
dependency the trigger exists to remove.

The independent pass then demonstrated five blind spots against synthetic
diffs. Each one is pinned below. The constitution's framing is what makes this
worth testing at all: **a list predicts; a diff describes** — so a describer
that cannot see half the diff is worse than the list it was meant to backstop.

Run:  python scripts/test_appsec_trigger.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_appsec_trigger import scan  # noqa: E402


def _diff(path: str, *lines: str) -> str:
    """A minimal unified diff for one file."""
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,1 @@\n" + "\n".join(lines)


CASES: list[tuple[str, str, bool]] = [
    # (name, diff, must_fire)
    (
        "a permission dependency is REMOVED from a route",
        _diff("backend/app/routers/admin.py", "-    admin: User = Depends(require_admin),"),
        True,
    ),
    (
        "a response_model is REMOVED from a route",
        _diff("backend/app/routers/listings.py", '-@router.get("/listings", response_model=ListingPage)'),
        True,
    ),
    (
        "a script outside backend/app grants is_admin",
        _diff("seed/make_admin.py", "+    user.is_admin = True"),
        True,
    ),
    (
        "a script outside backend/app deletes a file",
        _diff("scripts/wipe.py", "+    path.unlink(missing_ok=True)"),
        True,
    ),
    (
        "debug routes are enabled by default in config",
        _diff("backend/app/config.py", "+    enable_debug_routes: bool = True"),
        True,
    ),
    (
        "the JWT secret default is weakened",
        _diff("backend/app/config.py", '+    jwt_secret: str = "dev"'),
        True,
    ),
    (
        "upload path confinement changes",
        _diff("backend/app/uploads.py", "+    return Path(user_supplied)"),
        True,
    ),
    (
        "the rate limiter changes",
        _diff("backend/app/ratelimit.py", "+    return True  # always allow"),
        True,
    ),
    (
        "a security CI job is deleted",
        _diff(".github/workflows/ci.yml", "-        run: python scripts/check_spec_coverage.py"),
        True,
    ),
    (
        "recipient derivation changes",
        _diff("backend/app/notifications.py", "+    recipients = body.recipients"),
        True,
    ),
    # ...and the other half of a useful guard: it must stay quiet on work that
    # genuinely touches nothing. A trigger that fires on everything gets muted,
    # which is the same outcome as one that fires on nothing.
    (
        "a docs-only change",
        _diff("docs/progress.md", "+- a note about what shipped"),
        False,
    ),
    (
        "a frontend styling change",
        _diff("app/src/theme.ts", "+  spacing: 8,"),
        False,
    ),
]


def main() -> None:
    failures: list[str] = []
    for name, diff, must_fire in CASES:
        fired = scan(diff)
        if must_fire and not fired:
            failures.append(f"MISSED: {name} — the trigger stayed silent")
        elif not must_fire and fired:
            labels = ", ".join(label for label, _, _ in fired)
            failures.append(f"FALSE POSITIVE: {name} — fired [{labels}]")

    for failure in failures:
        print(failure, file=sys.stderr)

    if failures:
        print(f"\n{len(failures)}/{len(CASES)} appsec-trigger cases failed.", file=sys.stderr)
        raise SystemExit(1)

    print(f"All {len(CASES)} appsec-trigger cases behave as specified.")


if __name__ == "__main__":
    main()
