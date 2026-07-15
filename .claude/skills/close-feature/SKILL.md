---
name: close-feature
description: Close out a milestone's feature after its PR is approved — query the PR's status, squash-merge it (if still open) or detect an already-done merge, then sync local main so the next branch can be cut. Run after approving a milestone PR, or say "close the feature".
---

# Close the feature (merge + sync)

Closes out a milestone: once its PR is approved, squash-merge it (if not already merged) and sync local `main` so we're ready for the next `/start-milestone`. Per the constitution, **the human approves the merge** — only proceed when the PR is approved or the user explicitly says to close the feature.

> There is no passive notification — this **queries** PR status on demand (when you invoke `/close-feature` or say "close the feature"). For active watching, run it on a loop (`/loop 3m /close-feature <pr#>`), which polls and closes it once it's approved.

## Steps

1. **Locate `gh`.** If `gh` isn't on PATH, call it by full path: `/c/Program Files/GitHub CLI/gh.exe`.

2. **Identify the PR.** Use `$ARGUMENTS` as the PR number if given; otherwise the PR for the current branch:
   `gh pr view [<n>] --json number,state,mergeable,reviewDecision,headRefName,title`.

3. **Read the status** — `state` (OPEN | MERGED | CLOSED), `reviewDecision` (APPROVED | REVIEW_REQUIRED | CHANGES_REQUESTED), `mergeable` (MERGEABLE | CONFLICTING).

4. **Decide:**
   - **OPEN + MERGEABLE + (APPROVED, or the user explicitly said to close the feature)** → `gh pr merge <n> --squash --delete-branch`.
   - **OPEN + CONFLICTING** → stop; do **not** merge. The branch is behind an updated `main` — run the **conflict-recovery loop** (§ below) on the branch, then retry.
   - **OPEN + CHANGES_REQUESTED, or not approved and no explicit go-ahead** → stop. Tell the user it needs approval first; never merge an unreviewed/blocked PR.
   - **Already MERGED** (they merged in the browser) → skip the merge; go straight to sync.
   - **CLOSED (not merged)** → stop; report.

5. **Sync local `main`:** `git checkout main && git pull --ff-only && git fetch --prune` (the last prunes the deleted remote branch ref). Confirm the working tree is clean and local `HEAD` == `origin/main`.

6. **Report:** the merged commit now on `main`, the branch deleted, and that we're ready for the next `/start-milestone`.

## Conflict recovery (a second PR gone stale)

When two PRs are open at once, the moment the first squash-merges the second is based on an **older `main`**; if they touched the same lines GitHub marks it `CONFLICTING`, and step 4 stops here. Resolve it on the **branch**, before merging:

1. **Sync the branch onto the new main:** `git checkout <branch> && git fetch origin && git merge origin/main` (or `git rebase origin/main`).
2. **Resolve the conflict markers** — reconcile *both* sides' intent (each PR's spec + commits). A conflict in a **security-sensitive file** (`permissions.py`, auth, status state machines, response models) is new security surface — a bad merge silently drops a guard.
3. **Commit + push** the resolution.
4. **Re-run the gate — a resolved conflict is new, unreviewed code:** `/dod` (tests + the `docs/security.md` §8 matrix) must pass **and** the `tech-lead` + `appsec-engineer` review re-runs on the merged result (mandatory for any security-touching file). Never merge a hand-resolved conflict blind.
5. **Then** `/close-feature <pr#>` — now `MERGEABLE`. Full detail: `docs/git_strategy.md` § Two open PRs.

Never force-merge a PR with `CHANGES_REQUESTED` or conflicts. The `appsec-engineer` security must-cover matrix and the `tech-lead` diff review happen **on the branch, before the PR is opened** (a PR = agent-vetted, ready for a human) — see `/run-milestone`, `/dod`, and `docs/git_strategy.md`.
