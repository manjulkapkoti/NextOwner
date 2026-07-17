# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`** (manual, mid-milestone)
> and automatically at each milestone's close (**`/dod`** step 6, pre-PR commit);
> reconstructed and verified by **`/resume`** against git + tests. **Git is the
> source of truth for what's _done_** (a merged PR = a finished milestone); this
> file is the human-readable "you are here + ▶ next". Full design:
> `docs/session_recovery.md`.

**Milestone status:** M0 shipped ✅ · M1 (`auth-roles`) not started.
**In flight:** none — `main` is clean and in sync with `origin`; no milestone branch open. CI PR (#14, green-gate enforcement) merged ✅.
**Open PRs:** none.

## ▶ NEXT ACTION
Start M1:
**`/run-milestone auth-roles --pause-after-spec`**

## Carryover notes
- M1 is **security-critical** → inline review **+** one diff-scoped `appsec` agent (Sonnet). See `docs/git_strategy.md` § Branch review.
- **M1 scope = the gap-review fold-ins** (`docs/milestones.md` § Scope fold-ins): **refresh-token decision** (FR-1), both-roles path, minimal profiles, `tos_accepted_at`, settings module owns `DATABASE_URL`, rate-limit behind a swappable backend, curate `requirements.txt`, **Google OAuth excluded** (FR-1, post-MVP), and **delete the throwaway `/api/sandbox`** (unauthenticated write) before real data. (memory: `m0-followups-for-m1`)
- **Account lifecycle (password reset + email verification) moved M1 → M8 on 2026-07-17** — it was M1's only heavy item and M8 builds the email channel it needs. **M8 is now security-critical** (list: M1/M2/M5/M7/**M8**/M10). Trade-off accepted: no self-serve password reset until M8 — fine while 100% local with no real users.
- **Implement slice by slice (2026-07-17):** `plan.md` now carries a **Build order** — one trust boundary per slice, one commit each. **The red test list is the status; `plan.md` has no checkboxes** and never should (status files drift; `/resume` trusts git + tests).
- Root `test:api` is cross-platform (`scripts/test-api.mjs`, landed in the CI PR #14). Branch protection **applied 2026-07-16** (repo made public): `main` requires a PR + both green checks + an up-to-date branch, admins included.
- Review is **inline-first** to conserve context/usage; the `/dod` forbidden-path tests are the always-on security floor.
- M0 is ticked in `docs/milestones.md`.
- **This file now self-refreshes at each milestone's close** (`/dod` step 6 / `/run-milestone`, committed on the feature branch before the PR opens) — see `docs/session_recovery.md`. `/checkpoint` still covers manual mid-milestone saves.
