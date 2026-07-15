---
name: checkpoint
description: Save a clean, resumable stopping point — update docs/progress.md (the "next action"), commit WIP on the feature branch, push, and ensure a draft PR exists. Run at the end of a work session or before a risky/long operation so a new session can resume from exactly here. See docs/session_recovery.md.
---

# Checkpoint (save a resume point)

Persist enough state that a fresh session — or you, next day — resumes in seconds, even if this session then dies. Pairs with `/resume`. The crash-proof `Stop` hook already snapshots git state every turn; this skill adds the **semantic** resume point and makes the work **durable** (committed + pushed). Full design: `docs/session_recovery.md`.

## Steps

1. **Read the state.** `git branch --show-current`, `git status --short`, `git log --oneline -5`. Note the current milestone and phase (spec / red tests / implementing / review).

2. **Update `docs/progress.md`** — the semantic resume point:
   - **Milestone status** + the **in-flight branch/PR**.
   - **▶ NEXT ACTION** — one concrete sentence (the single most important line). Mid-milestone, name the exact next step and/or the failing test to make green.
   - **Carryover notes** — decisions made, anything non-obvious to remember next time.

   Keep it short — git and the red tests carry the detail.

3. **Commit WIP (feature branch only).** If on a `feat|fix|chore/*` branch with changes: `git add -A && git commit -m "wip: <short> (checkpoint)"` (no attribution trailer; squash-merge cleans wip noise). **Never commit to `main`** — if on `main`, skip the commit and just report the next milestone.

4. **Make it durable.** `git push` the branch so `origin` has it. If no PR exists yet, open a **draft** PR (`gh pr create --draft`) so the in-flight work is recoverable off your machine too.

5. **Report the resume point** — branch, PR, and the ▶ NEXT ACTION — so it's visible now and preserved in `progress.md` for next time.

## Guardrails
- Never commits to `main`, never merges — read / commit-on-branch / push only.
- `wip:` commits are expected and fine; squash-merge collapses them into one clean commit on `main`.
- If a merge/rebase is in progress, finish that first — don't checkpoint over it.
