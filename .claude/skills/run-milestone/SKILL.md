---
name: run-milestone
description: Automate the per-milestone build loop end-to-end up to the PR — cut the branch, scope the spec, write failing tests, implement with the agents, run /dod (green gate), then review & test on the branch (inline by the orchestrator by default; one independent appsec-engineer pass on the security-critical milestones), and open the PR once it's clean. Stops at the vetted PR for human review + /close-feature (never merges). Takes the milestone slug; add --pause-after-spec to approve the spec before building.
---

# Run a milestone (automated loop → green PR)

Drives the full per-milestone loop autonomously **up to the PR**, then stops for human review. The merge is never automated — the human reviews the diff and runs `/close-feature`. See `docs/milestones.md` for the milestone list, `docs/git_strategy.md` for the workflow, and `CLAUDE.md` § How we work.

**Argument:** the milestone slug (e.g. `auth-roles`). **Flag** (in `$ARGUMENTS`): `--pause-after-spec` — stop for the user to approve the spec before implementing (recommended for M1 auth and M5 the NDA gate).

## Steps

1. **Preflight.** Confirm a clean working tree on `main`, synced with `origin`. If the tree is dirty or a milestone branch is already checked out, **stop and report** — don't build over a mess.

2. **Branch** — run `/start-milestone <slug>` (cuts `feat/NNN-<slug>` off fresh `main`).

3. **Spec** — run `/new-spec <slug>`: `product-lead` scopes `spec.md` + `plan.md`, including the **Security & abuse** section (`docs/security.md` §7 + §6). Commit (`docs: spec …`).
   - **If `--pause-after-spec`:** stop here, show the acceptance criteria, and ask the user to approve before building. Resume on their go-ahead.

4. **Failing tests first** — `appsec-engineer` writes the permission/forbidden-path tests (401/403/404/409, IDOR, mass-assignment, schema-leak); `backend-engineer` / `frontend-engineer` write their unit/component tests. All derived from the spec's GIVEN/WHEN/THEN, and all must **FAIL**. Commit (`test: failing acceptance tests …`).

5. **Implement** — `backend-engineer` / `frontend-engineer` implement (with `tech-lead` on cross-cutting decisions and `product-designer` on UX) until the tests pass. Commit incrementally (`feat: …`).

6. **Green gate** — run `/dod`: full `npm test` + the security must-cover matrix + the milestone checklist. **If anything fails, STOP** and report — never send red work to review. `/dod` now **only verifies green**; it does not open the PR (the PR comes after the agent review, below).

7. **Review + test — the pre-PR gate (inline-first, to conserve context/usage).** Before any PR exists, review and test the work **on the branch**:
   - **Every milestone — inline (the orchestrator, warm context, cheap):** review the diff for architecture + the constitution's invariants ("API is the only door", public/private split, status state machines, conventions, the milestone's `plan.md`), and run the `docs/security.md` §8 touched→must-cover matrix — confirm the negative tests (401/403/404/409, IDOR, mass-assignment, schema-leak, path-traversal, spoofed-sender) exist and pass. (The `/dod` forbidden-path tests already ran in step 6 — they are the always-on security floor.) **Do this yourself; do NOT spawn a `tech-lead` agent** — the orchestrator covers architecture inline, reusing warm context.
   - **Security-critical milestones only — one independent `appsec-engineer` pass:** on **M1 (auth), M2 (uploads), M5 ⭐ (NDA gate), M7 (offers/money), M10 (verification)**, additionally spawn a **single** `appsec-engineer` agent for cold, independent eyes. **Scope it to the diff** — hand it `git diff main...<branch>` + the relevant §8 rows in the prompt; do NOT let it cold-read the whole repo. Run it **async in the background** so its transcript stays out of the main context. **Model: Sonnet** for M1/M2/M7/M10, **Opus for M5** (the crown jewel). Every other milestone gets the inline review only — no spawned agents.
   - **Address every blocking finding on the branch and re-run the tests** — loop until it's clean. If a finding needs a human decision (a spec change, a real risk trade-off), **STOP** and surface it; don't paper over it. Never edit a test just to make it pass.

8. **Open the PR — only after the branch review is clean.** First refresh `docs/progress.md` (milestone status, ▶ next action, carryover notes) and tick this milestone's box in `docs/milestones.md` § Progress tracker, and commit both on the branch — see `/dod` step 6 — so they land correct on `main` the instant this PR merges. Then `git push -u origin <branch>`, and `gh pr create --base main` (body: FRs, security-matrix result, test summary, **and the review outcome** — the inline review, plus the `appsec-engineer` pass on a security-critical milestone). Opening the PR means the work is **vetted and ready for a human** — that is what a PR signals here.

9. **STOP for human review.** Report the PR number/URL, what was built, the test + security-matrix summary, and the agent-review outcome. Tell the user to review the PR and say **"close the feature"**. **Do not merge.**

## Guardrails

- **No PR until the branch review is clean** — the orchestrator reviews inline every milestone (architecture + the §8 matrix), plus **one** independent `appsec-engineer` pass on the security-critical milestones (M1/M2/M5/M7/M10) — all **on the branch** (step 7), before the PR is opened. A PR here means "vetted, ready for a human." (Inline-first keeps context/usage low; the `/dod` forbidden-path tests are the always-on security floor.)
- **Never merges** — step 9 always hands off to the human (constitution: the human approves the merge).
- **Never edits a test to make it pass** — if a test is wrong, fix the spec deliberately and say so.
- **Stops immediately** on a dirty tree, a `/dod` failure, an unresolved review finding, or a security-matrix gap — no red or unreviewed PRs.
- **One milestone per run** (the natural unit); it does not chain into the next.
- Runs **in the session** (a long agentic build — many tool calls is expected), not a background or scheduled job.
