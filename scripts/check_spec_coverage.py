#!/usr/bin/env python3
"""Fail if a spec's acceptance criterion has no test citing it.

WHY THIS EXISTS
---------------
The constitution's central rule (Article 3 §2) is:

    every GIVEN/WHEN/THEN acceptance criterion becomes exactly one test

Nothing enforced it. A criterion could be dropped during the build and every
gate would still pass — the suite would be green, `/dod` would be green, CI
would be green, and the milestone would simply not do something it promised.
That is the one failure the test suite structurally cannot catch by itself,
because a missing test is invisible to the tests that exist.

This makes the rule mechanical: every criterion ID in `specs/*/spec.md` must
appear in at least one test file. The convention is already in use — tests
carry `A1`, `H2`, `AS5` in their names and comments — so this checks a habit
rather than imposing a new one.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It cannot tell whether the test *actually verifies* the criterion — only that
one claims to. That is a real limit, not an oversight: proving semantic
coverage needs a human, and this is the cheap mechanical half. A citation is
also a much better anchor for review than the reviewer's memory of the spec.

It also checks only ONE direction: spec → test. It cannot tell you that a test
cites a criterion the spec does not define. **This is a known hole, and it has
already bitten once**: during M5's branch review (2026-07-20) two criteria were
lost from `specs/005-nda-gate/spec.md` before the commit while the tests citing
them landed, and this script printed a clean `62/62`. A docs audit caught it;
nothing mechanical would have.

The reverse check was built and then **deliberately reverted**, because the
citation convention cannot support it. `F7` means "MVP feature 7"
(`requirements.md` F1–F12) in one test file and "criterion F7" (spec 004's
frontend group) in another, and tokens like `HS256` are shaped exactly like
criterion ids. The honest implementation produced 14 false positives against 0
true ones — and a check that cries wolf is worse than no check, for the same
reason `ci.yml` refuses to block on moderate npm advisories. Making it work
needs a distinguishable citation syntax (e.g. `spec:005/C12`), which is a
repo-wide convention change, not a milestone's business. Recorded here so the
next person weighs the same trade-off with the measurement already done.

Usage:
    python scripts/check_spec_coverage.py            # every spec
    python scripts/check_spec_coverage.py 001        # one milestone
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"

TEST_GLOBS = (
    ("backend/tests", "*.py"),
    ("app/src", "*.test.tsx"),
    ("app/src", "*.test.ts"),
    ("app/e2e", "*.spec.ts"),
)

# `- **A1** — GIVEN ... WHEN ... THEN ...`
# Anchored on GIVEN/WHEN/THEN so that other bold labels in a spec (section
# headings, FR references, decision markers) are not mistaken for criteria.
CRITERION_RE = re.compile(
    r"^\s*[-*]\s*\*\*(?P<id>[A-Z]{1,3}\d+)\*\*.*?\bGIVEN\b.*?\bWHEN\b.*?\bTHEN\b",
    re.IGNORECASE | re.DOTALL,
)

# A criterion struck through is one deliberately withdrawn — `~~**A4** ...~~`.
# Those are decisions, not omissions, so they are reported separately.
STRUCK_RE = re.compile(r"~~.*?\*\*(?P<id>[A-Z]{1,3}\d+)\*\*.*?~~", re.DOTALL)


# Criterion IDs are unique only *within* a spec — `A1` exists in 001, 002 and
# 003 alike — so a global search reports false coverage for every spec after the
# first. Tests are therefore attributed to a spec first, using the milestone tag
# each test file already declares in its header (`M2`, `spec pre-003`).
HEADER_LINES = 6
TAG_RE = re.compile(r"\bM(\d+)\b|\bspec\s+(pre-)?(\d+)", re.IGNORECASE)


def tags_for_spec(spec_dir: str) -> set[str]:
    """Tags a test file may use to claim this spec — e.g. '003' -> {003, M3}."""
    prefix = spec_dir.split("-", 1)[0]          # '003' or 'pre'
    if spec_dir.startswith("pre-"):
        prefix = "-".join(spec_dir.split("-", 2)[:2])   # 'pre-003'
        return {prefix.lower()}
    tags = {prefix.lstrip("0") or "0", prefix}
    if prefix.isdigit():
        tags.add(f"m{int(prefix)}")
    return {t.lower() for t in tags}


def tags_in_header(path: Path) -> set[str]:
    head = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:HEADER_LINES])
    found: set[str] = set()
    for m_num, pre, spec_num in TAG_RE.findall(head):
        if m_num:
            found.add(f"m{int(m_num)}")
        if spec_num:
            found.add(f"pre-{spec_num}" if pre else str(int(spec_num)))
            found.add(spec_num)
    return {t.lower() for t in found}


def attribute_tests() -> tuple[dict[str, str], list[str]]:
    """(tag -> concatenated source, files declaring no milestone)."""
    by_tag: dict[str, list[str]] = {}
    orphans: list[str] = []
    for directory, pattern in TEST_GLOBS:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob(pattern):
            tags = tags_in_header(path)
            if not tags:
                orphans.append(str(path.relative_to(ROOT)))
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            for tag in tags:
                by_tag.setdefault(tag, []).append(body)
    return {tag: "\n".join(chunks) for tag, chunks in by_tag.items()}, orphans


def criteria_in(spec: Path) -> tuple[list[str], set[str]]:
    text = spec.read_text(encoding="utf-8", errors="replace")
    struck = {m.group("id") for m in STRUCK_RE.finditer(text)}
    found: list[str] = []
    for line in text.splitlines():
        match = CRITERION_RE.match(line)
        if match:
            cid = match.group("id")
            if cid not in found:
                found.append(cid)
    return found, struck


def main() -> int:
    wanted = sys.argv[1] if len(sys.argv) > 1 else None
    if not SPECS.exists():
        print("No specs/ directory — nothing to check.")
        return 0

    by_tag, orphans = attribute_tests()
    if not by_tag:
        print("No test files found — cannot verify coverage.", file=sys.stderr)
        return 1
    if orphans:
        print(
            "Note — these test files declare no milestone in their first "
            f"{HEADER_LINES} lines, so their tests count for no spec:",
            file=sys.stderr,
        )
        for orphan in orphans:
            print(f"  ? {orphan}", file=sys.stderr)
        print(file=sys.stderr)

    total = 0
    gaps: list[tuple[str, str]] = []
    withdrawn: list[tuple[str, str]] = []

    for spec in sorted(SPECS.glob("*/spec.md")):
        milestone = spec.parent.name
        if wanted and wanted not in milestone:
            continue
        found, struck = criteria_in(spec)
        if not found:
            continue

        # Only this spec's own tests may satisfy this spec's criteria.
        tests = "\n".join(by_tag.get(tag, "") for tag in tags_for_spec(milestone))

        covered = []
        for cid in found:
            if cid in struck:
                withdrawn.append((milestone, cid))
                continue
            total += 1
            # Case-insensitive: specs write `A3`, Python test names write
            # `test_a3_...`. Word-boundary anchored so `A1` does not match
            # `A10` or `DATA1`. Underscores are word characters, so `test_a3_`
            # is matched by `\ba3\b` only because `_` bounds it — hence the
            # explicit separator class rather than a bare \b on the left.
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(cid)}(?![A-Za-z0-9])", tests, re.IGNORECASE):
                covered.append(cid)
            else:
                gaps.append((milestone, cid))

        print(f"{milestone}: {len(covered)}/{len([c for c in found if c not in struck])} criteria cited by a test")

    if withdrawn:
        print("\nWithdrawn (struck through in the spec — a decision, not a gap):")
        for milestone, cid in withdrawn:
            print(f"  ~ {milestone} {cid}")

    if gaps:
        print(f"\nUNCITED — {len(gaps)} of {total} criteria have no test naming them:", file=sys.stderr)
        for milestone, cid in gaps:
            print(f"  x {milestone} {cid}", file=sys.stderr)
        print(
            "\nEvery GIVEN/WHEN/THEN criterion becomes exactly one test "
            "(constitution Article 3 §2). Either write the test and name the "
            "criterion in it, or strike the criterion through in the spec if it "
            "was deliberately withdrawn — silence is the one option that is not "
            "available.",
            file=sys.stderr,
        )
        return 1

    print(f"\nAll {total} acceptance criteria are cited by a test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
