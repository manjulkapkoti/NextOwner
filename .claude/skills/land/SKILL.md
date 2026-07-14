---
name: land
description: Land a milestone's PR after it's approved — query its status, squash-merge it (if still open) or detect an already-done merge, then sync local main so the next branch can be cut. Run after approving a milestone PR, or say "land it".
---

# Land the PR (merge + sync)

Closes out a milestone: once its PR is approved, squash-merge it (if not already merged) and sync local `main` so we're ready for the next `/start-milestone`. Per the constitution, **the human approves the merge** — only proceed when the PR is approved or the user explicitly says to land it.

> There is no passive notification — this **queries** PR status on demand (when you invoke `/land` or say "land it"). For active watching, run it on a loop (`/loop 3m /land <pr#>`), which polls and lands once it's approved.

## Steps

1. **Locate `gh`.** If `gh` isn't on PATH, call it by full path: `/c/Program Files/GitHub CLI/gh.exe`.

2. **Identify the PR.** Use `$ARGUMENTS` as the PR number if given; otherwise the PR for the current branch:
   `gh pr view [<n>] --json number,state,mergeable,reviewDecision,headRefName,title`.

3. **Read the status** — `state` (OPEN | MERGED | CLOSED), `reviewDecision` (APPROVED | REVIEW_REQUIRED | CHANGES_REQUESTED), `mergeable` (MERGEABLE | CONFLICTING).

4. **Decide:**
   - **OPEN + MERGEABLE + (APPROVED, or the user explicitly said "land it")** → `gh pr merge <n> --squash --delete-branch`.
   - **OPEN + CONFLICTING** → stop. Report the conflict; do not merge.
   - **OPEN + CHANGES_REQUESTED, or not approved and no explicit go-ahead** → stop. Tell the user it needs approval first; never merge an unreviewed/blocked PR.
   - **Already MERGED** (they merged in the browser) → skip the merge; go straight to sync.
   - **CLOSED (not merged)** → stop; report.

5. **Sync local `main`:** `git checkout main && git pull --ff-only && git fetch --prune` (the last prunes the deleted remote branch ref). Confirm the working tree is clean and local `HEAD` == `origin/main`.

6. **Report:** the merged commit now on `main`, the branch deleted, and that we're ready for the next `/start-milestone`.

Never force-merge a PR with `CHANGES_REQUESTED` or conflicts. The security must-cover matrix (`appsec-engineer`) and the `tech-lead` diff review happen on the PR *before* this step — see `/dod` and `docs/git_strategy.md`.
