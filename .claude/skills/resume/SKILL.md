---
name: resume
description: Reconstruct where development left off at the start of a new session — from git + npm test (red tests = the to-do list) + docs/progress.md + the flight recorder — self-healing if the status file is stale, and flagging an interrupted (crashed) session. Run first thing in a new session. See docs/session_recovery.md.
---

# Resume (reconstruct where we left off)

Rebuild the working state from **ground truth (git + tests)**, using the status files only as hints — so it works even if the last session died before `/checkpoint` ran. Pairs with `/checkpoint`. Full design: `docs/session_recovery.md`.

## Steps

1. **Read the hints.** `.claude/session-state.md` (the flight recorder — mechanical, ≤1 turn stale) and `docs/progress.md` (semantic "next action"). Note what they claim — but don't trust them blindly (step 4).

2. **Interrogate the live repo:**
   - `git branch -vv`, `git status --short`, `git log --oneline -8`
   - `gh pr list --state open` (full path if `gh` isn't on PATH: `/c/Program Files/GitHub CLI/gh.exe`)
   - Find the in-flight work: an open feature-branch PR, or a non-`main` branch with commits ahead of `main`. If on `main` and clean, the next unit is the next unstarted milestone (`docs/milestones.md`).

3. **Run the tests — the red tests are the to-do list.** `npm test` (or faster: `cd backend && .venv\Scripts\python -m pytest -q`). Failing tests = exactly what's left to implement in the current milestone.

   **Then read the milestone's `specs/NNN-*/plan.md` § Build order** (if a spec exists) and pair the two: **the red tests say *what* is left; the Build order says *which slice is next*.** Match the red set against the slices — the first slice whose named tests are still red is where work resumes. That pairing is the whole resume point: "18 red" is a number, "next slice: #4 `get_current_user`, 3 tests" is an instruction. **`plan.md` has no checkboxes by design** — do not add any, and do not trust any that appear; the tests are the status, the Build order is only the order.

4. **Reconcile & self-heal.** Compare the status files against git + tests. **Trust git + tests.** If `progress.md` says "implementing X" but git shows X committed and a *different* test is red, resume at the real point and note the drift.

   **Also cross-check the two status *claims* against the tracker and flag a mismatch** (cheap drift detection — this is exactly what silently rotted for two milestones before 2026-07-18): does `CLAUDE.md`'s `## Project status:` line, and `progress.md`'s **Milestone status**, agree with `docs/milestones.md` § Progress tracker (the ticked `- [x]` boxes) and the merged-PR history? If a status line names an older milestone than the tracker's last `[x]`, say so — the tracker + git are the truth; the prose line is stale and should be corrected at the next `/dod` close (they're refreshed together there).

5. **Detect an interrupted session.** **Uncommitted changes** on a feature branch = crash residue → surface them (`git diff --stat`); that's where the last session was cut off. If a merge/rebase is in progress (the flight recorder flags it), report that first.

6. **Report the resume point:** current milestone + phase, what's committed (done), what's uncommitted (in progress), the red tests (todo) **and the next Build-order slice they map to**, and the reconstructed **▶ next action** with the exact command to run.

## Guardrails
- **Read-only reconstruction** — do NOT auto-commit, merge, or switch branches without saying so. Report the state + recommend the next command; let the human choose.
- Ground truth is git + the tests; the status files are hints that may be stale or (after a crash) slightly behind.
