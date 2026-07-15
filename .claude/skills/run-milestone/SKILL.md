---
name: run-milestone
description: Automate the per-milestone build loop end-to-end up to the PR — cut the branch, scope the spec, write failing tests, implement with the agents, run /dod (green gate), then have tech-lead + appsec-engineer review & test on the branch, and open the PR once they sign off. Stops at the agent-vetted PR for human review + /close-feature (never merges). Takes the milestone slug; add --pause-after-spec to approve the spec before building.
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

7. **Agent review + test — the pre-PR gate.** Before any PR exists, the agents review and test the work **on the branch**:
   - `tech-lead` reviews the diff — architecture, the constitution's invariants ("API is the only door", public/private split, status state machines), conventions, and the milestone's `plan.md`.
   - `appsec-engineer` runs the `docs/security.md` §8 touched→must-cover matrix on the diff and confirms the negative tests (401/403/404/409, IDOR, mass-assignment, schema-leak, path-traversal, spoofed-sender) exist and pass; it re-runs the suite.
   - **Address every blocking finding on the branch and re-run the tests** — loop until both agents sign off. If a finding needs a human decision (a spec change, a real risk trade-off), **STOP** and surface it; don't paper over it. Never edit a test just to make it pass.

8. **Open the PR — only after both agents sign off.** `git push -u origin <branch>`, then `gh pr create --base main` (body: FRs, security-matrix result, test summary, **and the `tech-lead` + `appsec-engineer` sign-off**). Opening the PR means the work is **agent-vetted and ready for a human** — that is what a PR signals here.

9. **STOP for human review.** Report the PR number/URL, what was built, the test + security-matrix summary, and the agent-review outcome. Tell the user to review the PR and say **"close the feature"**. **Do not merge.**

## Guardrails

- **No PR until the agents sign off** — `tech-lead` + `appsec-engineer` review and test **on the branch** (step 7), before the PR is opened. A PR here means "agent-vetted, ready for a human."
- **Never merges** — step 9 always hands off to the human (constitution: the human approves the merge).
- **Never edits a test to make it pass** — if a test is wrong, fix the spec deliberately and say so.
- **Stops immediately** on a dirty tree, a `/dod` failure, an unresolved review finding, or a security-matrix gap — no red or unreviewed PRs.
- **One milestone per run** (the natural unit); it does not chain into the next.
- Runs **in the session** (a long agentic build — many tool calls is expected), not a background or scheduled job.
