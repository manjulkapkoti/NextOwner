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

5. **Implement — one slice at a time, in `plan.md`'s Build order.** Not a single big-bang push to green. Work the **Build order** section of `plan.md`: each slice is **one trust boundary**, turns a named cluster of red tests green, and ends in one Conventional Commit (`feat: …`). `backend-engineer` / `frontend-engineer` implement, with `tech-lead` on cross-cutting decisions and `product-designer` on UX.
   - **The red count is the progress bar** — it only goes down (`cd backend && pytest -q --lf` between slices). **Do not track status anywhere else**: no checkboxes in `plan.md`, no side list. The failing tests *are* the queue, which is why `/resume` can rebuild the work from a dead session with no status file. A slice that leaves its cluster red isn't done — don't move on.
   - **If a slice reveals the order was wrong** (a dependency you didn't see at spec time), fix `plan.md`'s Build order and say so in the commit — the plan is a design artifact, not a prophecy. **Never** reorder by weakening a test.
   - The suite stays **red overall** until the last slice — by design (step 4 wrote every test failing). `/dod` in step 6 is the green gate.

6. **Green gate** — run `/dod`: full `npm test` + the security must-cover matrix + the milestone checklist. **If anything fails, STOP** and report — never send red work to review. `/dod` now **only verifies green**; it does not open the PR (the PR comes after the agent review, below).

7. **Review + test — the pre-PR gate (inline-first, to conserve context/usage).** Before any PR exists, review and test the work **on the branch**:
   - **Every milestone — inline (the orchestrator, warm context, cheap):** review the diff for architecture + the constitution's invariants ("API is the only door", public/private split, status state machines, conventions, the milestone's `plan.md`), and run the `docs/security.md` §8 touched→must-cover matrix — confirm the negative tests (401/403/404/409, IDOR, mass-assignment, schema-leak, path-traversal, spoofed-sender) exist and pass. (The `/dod` forbidden-path tests already ran in step 6 — they are the always-on security floor.) **Do this yourself; do NOT spawn a `tech-lead` agent** — the orchestrator covers architecture inline, reusing warm context.
   - **First, ask the diff, not just the list:** run `python scripts/check_appsec_trigger.py main`. It exits 1 and names what fired when the branch touches a permission boundary, a route, a response model, a state transition, an upload path, money or websockets. **The milestone list is a floor; this can only escalate, never excuse.** *This exists because the list was wrong once: M3 was not on it, got the pass by accident, and that pass found a blocking curation bypass — following the list literally would have shipped it.*
   - **Security-critical milestones (or any milestone the trigger fires on) — one independent `appsec-engineer` pass:** on **M1 (auth), M2 (uploads), M5 ⭐ (NDA gate), M7 (offers/money), M8 (password-reset tokens), M10 (verification)**, additionally spawn a **single** `appsec-engineer` agent for cold, independent eyes. **Scope it to the diff** — hand it `git diff main...<branch>` + the relevant §8 rows in the prompt; do NOT let it cold-read the whole repo. Run it **async in the background** so its transcript stays out of the main context. **You MUST pass the model explicitly — `model: "sonnet"` for M1/M2/M7/M10, `model: "opus"` for M5** (the crown jewel). This is a required parameter on the Agent call, not a preference: `appsec-engineer`'s frontmatter defaults to **opus** (correct for its deep threat-modeling work), so **omitting `model` silently runs the review pass on Opus and defeats the usage saving this whole inline-first design exists for** (constitution, 2026-07-15). Every other milestone gets the inline review only — no spawned agents.
   - **Then one bounded re-verification round — send the fix back to the SAME agent, not a fresh one.** After fixing a blocking finding, `SendMessage` the reviewing agent with the fix diff and exactly three questions: *(a)* does this close the finding or is there a variant it misses, *(b)* does the fix introduce anything new — a guard that fires on more states also changes legitimate flows, and *(c)* is the new test's coverage sound or does it give false confidence? **Continue the existing agent** (by id or name) rather than spawning: it already holds the finding, the code and the attack, so the round costs a fraction of a cold spawn.
     **Exactly one round, then stop.** If the agent still objects, that is no longer a review loop — surface it to the human as a decision. An unbounded loop rubber-stamps and burns budget.
     *Why this exists: on M3 the agent found a blocking bypass, the orchestrator fixed it, and **nobody checked the fix**. Fixes are where new bugs enter — the reviewer having found the bug does not mean the patch is right.*
   - **Address every blocking finding on the branch and re-run the tests** — loop until it's clean. If a finding needs a human decision (a spec change, a real risk trade-off), **STOP** and surface it; don't paper over it. Never edit a test just to make it pass.

8. **Open the PR — only after the branch review is clean.** First refresh the **three status surfaces** — `docs/progress.md` (milestone status, ▶ next action, carryover notes), the `docs/milestones.md` § Progress tracker tick, **and `CLAUDE.md`'s `## Project status:` line** — and commit them on the branch (see `/dod` step 6 for exactly what each gets) so they land correct on `main` the instant this PR merges. Then `git push -u origin <branch>`, and `gh pr create --base main`. **The PR body carries only the deliverable** (what shipped, what's in it, tests) — no review narrative, no decisions, no attribution; raise the review outcome + any decisions to the user **in chat** (see memory `pr-presentation-format`). Opening the PR means the work is **vetted and ready for a human**.

9. **STOP for human review.** Report the PR number/URL, what was built, the test + security-matrix summary, and the agent-review outcome. Tell the user to review the PR and say **"close the feature"**. **Do not merge.**

## Guardrails

- **No PR until the branch review is clean** — the orchestrator reviews inline every milestone (architecture + the §8 matrix), plus **one** independent `appsec-engineer` pass on the security-critical milestones (M1/M2/M3/M5/M7/M8/M10) — all **on the branch** (step 7), before the PR is opened. A PR here means "vetted, ready for a human." (Inline-first keeps context/usage low; the `/dod` forbidden-path tests are the always-on security floor.)
- **Never merges** — step 9 always hands off to the human (constitution: the human approves the merge).
- **Never edits a test to make it pass** — if a test is wrong, fix the spec deliberately and say so.
- **Stops immediately** on a dirty tree, a `/dod` failure, an unresolved review finding, or a security-matrix gap — no red or unreviewed PRs.
- **One milestone per run** (the natural unit); it does not chain into the next.
- Runs **in the session** (a long agentic build — many tool calls is expected), not a background or scheduled job.
