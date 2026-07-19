---
name: dod
description: Definition-of-done check for a milestone — run the milestone's tests plus the full test suite and confirm everything is green before declaring the milestone complete (constitution Article 3). Use before committing or marking a milestone done.
---

# Definition-of-done check

A milestone is "done" only when **its tests pass AND the full `npm test` suite is green** (constitution Article 3 §3, `docs/testing_guide.md` §6). This skill verifies that gate. **Commit only when green.**

## Steps

1. **Check the project is scaffolded.** If `backend/` / `app/` / the root `package.json` don't exist yet, we're pre-Milestone-0 — there's nothing to run. Say so and stop (run `/scaffold-m0` first).

2. **Run the full suite** from the repo root:
   ```bash
   npm test
   ```
   This runs `cd backend && pytest -q` then `cd app && vitest run`. If you're mid-implementation and want a faster loop, `cd backend && pytest -q -x --lf` re-runs only last failures — but the DoD gate is the **full** `npm test`.

3. **Cross-check the milestone checklist.** Open the matching milestone section in `docs/testing_guide.md` §5 and confirm every ☐ item has a corresponding passing test. Flag any checklist item with no test — that's an unmet acceptance criterion, not a pass.

4. **Security must-cover check (owner's #1 priority).** For everything this milestone touched, run the `docs/security.md` §8 touched→must-cover matrix: if it changed **auth, permissions/a new route, create/PUT, a public route, uploads, money/offers, or WebSockets**, confirm the corresponding negative test exists and passes (invalid-token 401, wrong-identity 403/IDOR, mass-assignment ignored, schema-leak, path traversal, illegal-transition 409, spoofed-sender rejected). A milestone with a missing negative test is **not done**, even if the positive tests are green — flag the gap.

5. **Report the result plainly:**
   - **Green + checklist complete** → the milestone is done; proceed to open the PR (step 6).
   - **Any failure** → show the failing test output. Do not describe the milestone as done, and do **not** open a PR. Point at the specific failing scenario.

6. **When green + checklist complete, hand off to the branch review — do NOT open the PR yet.** The review happens **on the branch, before any PR exists** — a PR means "vetted, ready for a human." It's **inline-first**: the orchestrator reviews the diff itself (architecture + the `docs/security.md` §8 matrix + confirming the negative tests), reusing warm context. Run `python scripts/check_appsec_trigger.py main` first — it reads the diff and names what needs independent eyes, and the milestone list is only a floor beneath it (M3 proved the list can be wrong). On the **security-critical milestones** (M1/M2/M3/M5/M7/M8/M10) **or any milestone the trigger fires on**, *additionally* spawn a single diff-scoped `appsec-engineer` agent, **passing `model` explicitly — `model: "sonnet"`, or `model: "opus"` for M5.** (The agent's frontmatter defaults to opus; omit the parameter and the review pass silently runs on Opus.) See `docs/git_strategy.md` § Branch review. **After fixing any blocking finding, run one bounded re-verification round**: `SendMessage` the *same* reviewing agent the fix diff and ask only whether it closes the finding, whether it breaks a legitimate flow, and whether the new test's coverage is sound. Continue that agent rather than spawning a fresh one — it still holds the context, so the round is cheap. One round only; if it still objects, escalate to the human. So on green: commit any final work with a Conventional Commit message, run the review, fix any blocking finding, and re-run `/dod`.

   **Refresh the three status surfaces on the branch — `docs/progress.md`, `docs/milestones.md`, AND `CLAUDE.md`'s Project-status line** — once the review is clean:
   - `progress.md`'s **Milestone status** (this milestone → shipped, pending merge), **▶ NEXT ACTION** (the next milestone's `/start-milestone`/`/run-milestone` command — or the next mid-milestone step, if this PR doesn't close the milestone), and **Carryover notes**.
   - `docs/milestones.md` § Progress tracker — tick this milestone's box (`- [ ] **M<N>**` → `- [x] **M<N>**`), if this PR completes it.
   - **`CLAUDE.md`'s `## Project status:` line** — bump it to the milestone just shipped + what's next, and keep it in *dated-snapshot-that-points-at-the-tracker* form (so it degrades gracefully if it ever slips). **This is here because it was the gap:** `CLAUDE.md`'s status was maintained by nobody and drifted stale for two milestones (fixed 2026-07-18) — it loads every session, so a confident stale claim there misleads. Folding it into this same trigger is what stops the drift.

   Commit all three together (`docs: update progress.md + tick M<N> + CLAUDE.md status — <milestone> shipped`). This is the only reliable trigger point: branch protection blocks direct commits to `main`, and no local hook can observe a GitHub merge event, so baking these edits into the PR's own commits is what makes `main`'s copy correct the instant it merges. (`/checkpoint` still exists for manual saves mid-milestone.)

   **Only after the review is clean** do you `git push -u origin <branch>` and `gh pr create --base main` (title/body summarizing the milestone, the FRs, the `/dod` result, the security-matrix outcome, and the review outcome). If you're on `main`, stop and tell the user to run `/start-milestone` first. If `gh` isn't installed yet, push the branch and give the user the PR-compare URL instead. **Do not merge** — the human approves and squash-merges via `/close-feature` (`gh pr merge --squash --delete-branch`). `/run-milestone` automates this whole sequence including the review gate.

7. Never edit tests to make them pass. If a test is wrong, fix the spec/test deliberately and say so — the tests are the acceptance criteria.
