# Session Recovery — resume development across sessions

> How to stop work at the end of a day (or an abrupt crash) and have the **next
> session pick up exactly where the last one left off**. Applied strategy, wired
> into this repo. Summarized in `CLAUDE.md` § Session continuity.

---

## The problem

Development spans many sessions across days, and a session can die **mid-task** —
a crash, a closed tab, or the **usage/session limit hit mid-turn**. A resume
strategy that depends on a tidy end-of-session "save" is a single point of
failure: if the session dies before that save runs, the state is lost.

So the design assumes **the session can die at any instant** and must still be
recoverable.

## Two principles

1. **Durability is continuous & automatic — not end-of-session.** Every turn
   leaves a durable trace on disk, mechanically, so an abrupt death loses at
   most the current in-progress slice (and even that is on disk).
2. **Resume rebuilds from ground truth (git + tests), never trusts a status
   file.** The status files are *hints*; the live repo and the test results are
   the truth. This makes resume self-healing even when no clean checkpoint ran.

## The core insight (SDD-native)

**In spec-driven development, the failing tests _are_ your bookmark.** Stop
halfway through a milestone, come back, run `npm test`, and the **red tests are
your exact remaining to-do list.** A huge amount of "where was I" is captured for
free — no notes required.

---

## The layers

Each layer has one job; they don't duplicate each other, so nothing drifts.

| Layer | Answers | Where | Updated |
|---|---|---|---|
| **Git** (commits, PRs, branches) | What's **done** | the repo / GitHub | every commit; a merged PR = a finished milestone |
| **`docs/progress.md`** | Where we **are** + **▶ next action** | committed, on the branch | by `/checkpoint` (mid-milestone, manual) **and** automatically at milestone close (`/dod`'s pre-PR commit, step 6 — see below) |
| **`docs/milestones.md`** § Progress tracker | Which milestones are **shipped** (checked boxes) | committed, on the branch | automatically at milestone close (same `/dod` step 6 commit as `progress.md`) |
| **`.claude/session-state.md`** (flight recorder) | The **mechanical git snapshot** for crash recovery | gitignored, local | **automatically, every turn** (the `Stop` hook) |
| **Claude memory** (`~/.claude/.../memory/`) | Durable **facts / preferences** (not volatile status) | auto-loaded each session | when a durable fact appears |
| **Red tests** (`npm test`) | What's **left to do** in the current milestone | the test suite | continuously, as you implement |

## The automatic safety net — the `Stop` hook

`.claude/settings.json` registers a **`Stop` hook** that runs
`.claude/hooks/flight_recorder.py` **after every turn**. Because the *harness*
runs it (not the model), it fires whether the session ends cleanly or dies right
after — so it can't be skipped by a crash.

The recorder is deliberately harmless: it **only reads git and writes the single
gitignored file `.claude/session-state.md`** (branch, recent commits, uncommitted
working tree, timestamp, and any in-progress merge/rebase). It **never commits,
stages, or mutates git** — so it cannot interfere with the deliberate git
orchestration the milestone workflow does. Being gitignored, it adds zero git
noise; being on disk, it survives a crash.

> Design choice: the hook is snapshot-only, not auto-commit. Your code is already
> durable (every edit hits disk instantly, recoverable via `git status`/`git
> diff`), so a file-only hook gets the crash-proof context with **zero risk** of
> a per-turn commit colliding with a deliberate git operation. Durable restore
> points come from committing WIP at natural steps (see `/checkpoint`), which
> squash-merge collapses to one clean commit on `main`.

## The rituals

- **`/checkpoint`** (end of a session, or before a long/risky op) — updates
  `docs/progress.md` (the ▶ next action), commits WIP on the feature branch,
  pushes, and ensures a **draft PR** exists. Makes the work durable and off-machine.
- **Milestone close** (`/dod` step 6, automated end-to-end by `/run-milestone`) —
  once the branch review is clean, refreshes `docs/progress.md` (status + ▶ next
  action + carryover notes) **and** ticks the milestone's box in
  `docs/milestones.md` § Progress tracker, as one of the final commits **on the
  feature branch**, before the PR opens. This is the only reliable automatic
  trigger point: branch protection blocks direct commits to `main`, and no local
  hook can observe a GitHub merge event (a PR can merge from the browser, in a
  different session, or well after the branch work ended) — so baking both edits
  into the PR's own commits is what makes `main`'s copy correct **the instant it
  merges**, with zero lag and no risk of colliding with the milestone's git
  orchestration.
- **`/resume`** (first thing in a new session) — reads the flight recorder +
  `progress.md`, then **interrogates git + runs the tests**, reconciles (trusting
  git + tests), flags an interrupted session (uncommitted residue), and reports
  the reconstructed **▶ next action**.

`CLAUDE.md` points every new session at `/resume`.

---

## How each failure mode is covered

| Failure | Why the next session still resumes cleanly |
|---|---|
| **Crash / process killed** | The `Stop` hook wrote the flight recorder on the last completed turn; every edit is already on disk; commits survive. `/resume` rebuilds from git + tests. |
| **Tab/session closed mid-task** | Same — plus `/resume` detects the uncommitted diff and surfaces it as "work was in progress here." |
| **Usage/session limit hit mid-turn** | Prior turns' state is on disk + committed; `/resume` reads it and **re-runs the interrupted step** (each milestone step — spec / tests / implement / `/dod` — is idempotent, so re-running is safe). |
| **Status file stale / never checkpointed** | `/resume` trusts git + tests over the files and self-heals, reporting any drift. |
| **Machine loss** | Mitigated by `/checkpoint` pushing WIP + the early **draft PR** — the branch and progress live on `origin`, recoverable from another machine. |

## Day-to-day loop

```
End of day:      /checkpoint   → progress.md updated, WIP committed + pushed, draft PR up
                 (and the Stop hook has been snapshotting every turn regardless)

Next day (new session):
                 /resume        → reads git + runs npm test (red = todo) + reconciles
                               → "You're on feat/003-…, PR #9 draft, test_reject_* is red
                                  → next: implement POST /admin/listings/{id}/reject"
                 …continue.
```

The cleanest cadence is **~one milestone per session** (`/run-milestone` already
stops at a clean checkpoint — the PR); `progress.md` + the red tests carry
anything that spills across days.

## Files in this strategy

| Path | Role | Tracked? |
|---|---|---|
| `docs/session_recovery.md` | This document | yes |
| `docs/progress.md` | Semantic "you are here + ▶ next" | yes |
| `docs/milestones.md` | The M0→M12 checklist; § Progress tracker ticks per milestone | yes |
| `.claude/settings.json` | Registers the `Stop` hook | yes |
| `.claude/hooks/flight_recorder.py` | Writes the flight recorder each turn | yes |
| `.claude/session-state.md` | The flight recorder output | **no** (gitignored, per-machine) |
| `.claude/skills/checkpoint/SKILL.md` | The `/checkpoint` ritual | yes |
| `.claude/skills/dod/SKILL.md` | Green gate; step 6 also refreshes `progress.md` + ticks `milestones.md` pre-PR | yes |
| `.claude/skills/resume/SKILL.md` | The `/resume` ritual | yes |

## Verifying the hook

The hook loads at session start. To confirm it fires on your machine: finish a
turn, then check `.claude/session-state.md`'s timestamp updated. If it didn't,
the hook command (`python .claude/hooks/flight_recorder.py`) may need adjusting
for your shell/PATH (e.g., an absolute `python` path) — the recorder script
itself is verified working and resolves the repo root independent of the cwd.
