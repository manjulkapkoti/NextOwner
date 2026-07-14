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
   - **Green + checklist complete** → state it's done. Remind the user of "commit only when green," and offer to stage + commit (per-milestone commit gives a known-good checkpoint). Do not commit without the user's go-ahead.
   - **Any failure** → show the failing test output. Do not describe the milestone as done. Point at the specific failing scenario.

6. Never edit tests to make them pass. If a test is wrong, fix the spec/test deliberately and say so — the tests are the acceptance criteria.
