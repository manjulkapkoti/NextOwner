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

4. **Reconcile & self-heal.** Compare the status files against git + tests. **Trust git + tests.** If `progress.md` says "implementing X" but git shows X committed and a *different* test is red, resume at the real point and note the drift.

5. **Detect an interrupted session.** **Uncommitted changes** on a feature branch = crash residue → surface them (`git diff --stat`); that's where the last session was cut off. If a merge/rebase is in progress (the flight recorder flags it), report that first.

6. **Report the resume point:** current milestone + phase, what's committed (done), what's uncommitted (in progress), the red tests (todo), and the reconstructed **▶ next action** with the exact command to run.

## Guardrails
- **Read-only reconstruction** — do NOT auto-commit, merge, or switch branches without saying so. Report the state + recommend the next command; let the human choose.
- Ground truth is git + the tests; the status files are hints that may be stale or (after a crash) slightly behind.
