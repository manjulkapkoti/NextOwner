---
name: start-milestone
description: Start a new milestone by cutting a fresh feature branch off main (branch → PR → merge workflow). Run at the very start of each milestone, before /new-spec. Takes the milestone slug, e.g. /start-milestone auth-roles.
---

# Start a milestone (cut the feature branch)

Every milestone's work happens on its own feature branch off `main` and lands via a PR — **never commit to `main` directly** (constitution Article 3 §3; `CLAUDE.md` § Git workflow). This skill sets up that branch.

## Steps

1. **Refuse to start on a dirty tree.** Run `git status --short`. If there are uncommitted changes, stop and tell the user to commit/stash them first — starting a milestone must begin from a clean state.

2. **Sync `main`.** `git checkout main && git pull` so the branch is cut from the latest.

3. **Name the branch.** From `$ARGUMENTS` (the milestone slug, e.g. `auth-roles`), determine the milestone number `NNN` (match the next `specs/NNN-*` in build order) and the type (`feat` by default; `fix`/`chore` if the user says so). Branch name: `feat/NNN-slug` (e.g. `feat/001-auth-roles`). If `$ARGUMENTS` is empty, ask which milestone.

4. **Create + switch to the branch:** `git checkout -b feat/NNN-slug`. Confirm with `git branch --show-current`.

5. **Hand off:** tell the user the branch is ready and the next step is `/new-spec <slug>` (or `product-lead` scoping) → write failing tests → implement → `/dod` (green gate) → branch review (inline; + an independent `appsec-engineer` pass on the security-critical milestones M1/M2/M5/M7/M8/M10) → open the PR once it's clean (a PR = vetted, ready for a human).

Do not write specs or code in this skill — it only prepares the branch.
