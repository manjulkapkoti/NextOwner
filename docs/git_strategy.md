# NextOwner — Git Strategy

> How version control works for the agent team: a per-milestone **feature branch → PR → squash-merge** workflow, so `main` is always green. Binding alongside `specs/000-constitution.md` (Article 3) and summarized in `CLAUDE.md` § Git workflow.

---

## Principles

### 1. Branch per milestone, not per agent-task

A milestone (e.g., M1 auth) is the real-world equivalent of a ticket/feature — that's the unit that gets a branch and a PR. Multiple agents (`appsec` writes tests, `backend` implements, `frontend` builds) all work on the **same** branch. Branching per agent-spawn would shatter one feature across a dozen branches/PRs — chaos. So: **one branch + one PR per milestone**, and agents commit into it.

### 2. "Commit only when green" becomes "merge to main only when green"

The constitution originally said *commit only when green* — but on a feature branch you **want** to commit work-in-progress, including the **failing-tests-first** commit (that's core to SDD). The refinement: commit freely on the branch (red tests → implement → green); the **PR-merge to `main`** is the green gate. `main` stays always-green; the branch is where the red→green happens. *(Applied — logged as the 2026-07-14 amendment in `specs/000-constitution.md` Article 3 §3.)*

### 3. The orchestrator owns git; agents produce the code

Sub-agents run in isolation and hand work back to the main session. Having each isolated agent independently branch/push/PR would collide. So the **orchestrator** (the main Claude session, in the `tech-lead` coordinating role) owns the branch/commit/push/PR lifecycle; the **agents produce the code and tests** that land as commits on the branch.

---

## The refined per-milestone flow

```
1. Start   →  git checkout main && git pull
              git checkout -b feat/001-auth-roles          (branch off fresh main)   ← /start-milestone
2. Spec    →  product-lead scopes → /new-spec → commit     ("docs: spec M1 auth")
3. Tests   →  appsec writes failing tests → commit         ("test: failing acceptance tests M1")
4. Build   →  backend/frontend implement → commit(s)       ("feat: auth endpoints + JWT")
5. Green   →  /dod: full suite + security must-cover matrix + checklist must pass   (verifies green — does NOT open the PR)
6. Review  →  INLINE by the orchestrator every milestone (architecture + §8 matrix)  ← ON THE BRANCH,
              + 1 independent appsec agent on M1/M2/M3/M5/M7/M8/M10 (diff-scoped)             BEFORE the PR exists
              → fix findings, re-run tests, until clean
7. PR      →  git push -u origin … → gh pr create → main                              ← opened only after sign-off;
              (body: FRs, security-matrix result, test summary, agent sign-off)         a PR = "ready for a human"
8. Human   →  you review the PR → approve
9. Close   →  /close-feature: squash-merge → delete branch → sync local main → next milestone
```

## Branch review (step 6) — inline-first, to conserve context/usage

The pre-PR review is **inline by default**: the orchestrator (in the `tech-lead` role) reviews every milestone's diff itself — architecture + the constitution's invariants + the `docs/security.md` §8 must-cover matrix — reusing warm context (cheap). Cold-spawning review agents re-reads the whole repo and burns the session budget, so we don't do it every milestone.

**One independent `appsec-engineer` agent is added only on the security-critical milestones** — **M1** (auth), **M2** (uploads), **M5 ⭐** (NDA gate), **M7** (offers/money), **M8** (password-reset tokens), **M10** (verification) — for cold, blind-spot-free security eyes. Even then: a **single** agent (no separate `tech-lead` agent), **scoped to the diff** (`git diff main...<branch>` + the relevant §8 rows, not a full-repo read), run **async in the background** (transcript stays out of the main context), on **Sonnet** (Opus only for M5). The `/dod` forbidden-path tests are the always-on security floor on *every* milestone regardless.

---

### The docs audit (added 2026-07-19)

Code has a compiler and a test suite. Prose has neither, and every documentation defect this project has hit was a defect of **fact** written in fluent English: a `progress.md` contradicting the constitution on which milestones get a security pass, three documents each defining the design tokens, a spec still calling a shipped design system "a later concern", a `CLAUDE.md` claiming a guarantee its trigger did not provide, and a constitution amendment reporting "six paths" when there were 11.

None of those needed better writing. They needed a reader who was not the author — the same argument as the independent appsec pass, applied to prose.

`scripts/check_docs_trigger.py` decides when: **any change to a binding document** (constitution, `CLAUDE.md`, `security.md`, `requirements.md`), or **more than 40 changed lines** of other prose. Below that it stays quiet, deliberately — a typo fix does not need an auditor, and a check that fires on everything is one people learn to skip.

The **`docs-auditor`** agent audits, it does not edit: contradictions (quoting both sides), duplicated truth, stale references, over-claiming, unverifiable numbers, untestable acceptance criteria, and absence claims with no stated search. Explicitly **no style, tone or restructuring** — volume is how a review becomes noise. Hand it the diff *and* the binding documents, since the contradiction it needs to find usually spans both.

### The bounded re-verification round (added 2026-07-19)

A review that only runs **before** the fix leaves the fix itself unchecked — and a fix is exactly where a new bug enters. On M3 the independent pass found a blocking curation bypass, the orchestrator patched it, and nothing verified the patch: it happened to be sound, but only because a mechanical reachability test existed to prove it, not because the process demanded proof.

So after fixing any **blocking** finding, run **one** re-verification round:

- **Send it to the same agent, not a fresh one.** Continue the existing reviewer (`SendMessage` by id or name) — it already holds the finding, the code and the attack it wrote. A cold spawn re-derives all of that and costs many times more for a worse answer.
- **Ask three narrow questions**, not "review it again": does this close the finding or is there a variant it misses; does the fix break a legitimate flow (a guard that fires on more states changes valid paths too); and is the new test's coverage sound or does it give false confidence?
- **Exactly one round.** If the agent still objects afterwards, it is no longer a review loop — surface it to the human as a decision. Unbounded loops rubber-stamp and burn budget.

Non-blocking findings do not get a round. They are either fixed inline, or recorded **with the trigger that should reopen them** ("when M4's seed data lands"), never as an undated "later".

## Two open PRs (staleness + conflict recovery)

Milestones are built **one at a time**, so each branch is cut from fresh `main` and squash-merges cleanly — normally there's only one PR in flight and this never comes up. But when two PRs are open at once (e.g. a process/hotfix PR alongside a milestone), the moment the first merges the second is based on an **older `main`**:

- **No file overlap** → the second still merges cleanly, in either order. Just re-sync its branch (`git merge origin/main`) and re-run `/dod` before merging, so it's verified against the `main` it actually lands on (keeps `main` always-green).
- **Same lines touched** → GitHub marks the second `CONFLICTING`. `gh pr merge` and `/close-feature` **refuse** it (fail-safe — never a blind merge). Recover on the **branch**:

  1. **Sync onto the new main:** `git checkout <branch> && git fetch origin && git merge origin/main` (or `rebase`).
  2. **Resolve the markers** — reconcile *both* PRs' intent (their specs + commits). A conflict in a **security-sensitive file** (`permissions.py`, auth, status state machines, response models) is new security surface — a bad merge silently drops a guard, so treat it as such.
  3. **Commit + push.**
  4. **Re-gate — the resolution is new, unreviewed code:** `/dod` (tests + §8 matrix) must pass **and** the branch review re-runs on the merged result — inline, plus the `appsec-engineer` agent if the conflict touched a security-sensitive file. Never merge a hand-resolved conflict blind.
  5. **Then** `/close-feature <pr#>`.

**Semantic conflicts** (two milestones changing the same business/security rule in different directions) don't have a mechanical answer — surface both options for a human call rather than guess. **Best avoided entirely:** keep milestone PRs sequential; when an independent change must run alongside, merge it first and re-sync/re-gate the rest.

## CI (added 2026-07-16)

`.github/workflows/ci.yml` runs the full suite — backend pytest + frontend tsc/vitest, the same gate as the root `npm test` — on **every PR** and on every push to `main`, so the "merge only when green" rule is machine-checked, not just convention. **`main` is branch-protected** (applied 2026-07-16, when the repo went public): merging requires a PR with **both checks green** and the branch **up to date with `main`** (strict mode — machine-enforces the § Two open PRs re-sync rule), direct pushes / force-pushes / deletion are blocked, and it's **enforced for admins** too. Formal GitHub approvals aren't required (GitHub forbids approving your own PR — solo repo); the human review stays the `/close-feature` discipline. `/dod` remains the richer local gate (checklist + security matrix); CI + protection are the floor that can't be skipped, and the `.git/hooks/pre-commit` guard stays as the local backstop.

### Status freshness — the third check (added 2026-07-19)

A third job, **Status freshness**, runs `scripts/check_status_freshness.py` on **push to `main` only** (a no-op on PRs, where in-flight language is correct). It fails the build if any status surface still describes work as unfinished — in-flight/awaiting-review wording, a named branch that has merged and been deleted, or an unticked tracker row for landed work.

**Why it is mounted here and not on `/dod`.** The refresh was originally bound to the milestone-close command, and drifted stale twice regardless: **#26/#27** merged as small follow-ups that never ran `/dod`, and **#28** ran it but recorded *"PR open — awaiting approval"* — true when committed, false the moment it merged. A trigger only holds if it sits on a step nothing can route around, and it cannot ask a branch to assert something that only becomes true later. **The merge is that step**, and it is where the check now lives. The single fact it enforces needs no judgement: ***`main` contains only merged work.***

It **detects rather than prevents** — auto-fixing would require a bot committing to protected `main`. That is the accepted trade: drift surfaces as a red build within a minute of landing, instead of surviving milestones in silence. `/dod` step 6 stays the first line; this is the backstop. Run it locally before opening a PR with `python scripts/check_status_freshness.py --force`.

## Conventions

- **Branches:** `feat|fix|chore/NNN-slug` (e.g. `feat/001-auth-roles`).
- **Commits:** Conventional Commits — `feat:` / `fix:` / `test:` / `docs:` / `chore:`.
- **Merge:** **squash-merge** — one clean commit per milestone on `main`; delete the branch after. **A PR must have green CI checks before `/close-feature` merges it.**
- **Never commit directly to `main`** — enforced locally by a `.git/hooks/pre-commit` guard (override for a one-off: `git commit --no-verify`).

## Tooling

- `/start-milestone <name>` → step 1 (cut the branch off fresh `main`).
- `/dod` → step 5 only (the green gate: full suite + security matrix + checklist). It **no longer opens the PR** — the branch review (step 6 — inline, plus an independent `appsec` pass on the security-critical milestones) runs first, and the push + `gh pr create` (step 7) happen only after it's clean. The orchestrator (or `/run-milestone`) owns that push/PR step; never auto-merges.
- `/run-milestone <slug>` → automates steps 1–7 (branch → spec → failing tests → implement → `/dod` green gate → branch review — inline, + appsec on security-critical milestones → open the PR once vetted), then stops at the PR for the human.
- `/close-feature [pr#]` → step 9: after your approval, squash-merges (`gh pr merge --squash --delete-branch`) if the PR is still open — or just syncs if you already merged — then `git checkout main && git pull --ff-only && git fetch --prune` to ready the next branch. On a `CONFLICTING` PR it stops (no blind merge) — see § Two open PRs. Queries status on demand (no passive notification); run on a `/loop` to poll.
