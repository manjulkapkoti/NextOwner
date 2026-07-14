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
5. Green   →  /dod: full suite + security must-cover matrix must pass
6. Push    →  git push -u origin feat/001-auth-roles                                  ┐
7. PR      →  open PR → main (body: FRs, security-matrix result, test summary)        ┘ ← /dod (gh pr create)
8. Review  →  tech-lead reviews the diff · appsec runs the matrix on the PR   ← your "reviewers"
9. Land    →  you approve → /land: squash-merge → delete branch → sync local main → next milestone
```

---

## Conventions

- **Branches:** `feat|fix|chore/NNN-slug` (e.g. `feat/001-auth-roles`).
- **Commits:** Conventional Commits — `feat:` / `fix:` / `test:` / `docs:` / `chore:`.
- **Merge:** **squash-merge** — one clean commit per milestone on `main`; delete the branch after.
- **Never commit directly to `main`** — enforced locally by a `.git/hooks/pre-commit` guard (override for a one-off: `git commit --no-verify`).

## Tooling

- `/start-milestone <name>` → step 1 (cut the branch off fresh `main`).
- `/dod` → steps 5–7 (run the green gate, then push + `gh pr create` when green; never auto-merges).
- `/land [pr#]` → step 9: after your approval, squash-merges (`gh pr merge --squash --delete-branch`) if the PR is still open — or just syncs if you already merged — then `git checkout main && git pull --ff-only && git fetch --prune` to ready the next branch. Queries status on demand (no passive notification); run on a `/loop` to poll.
