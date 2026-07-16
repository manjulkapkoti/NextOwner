# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`**; reconstructed and
> verified by **`/resume`** against git + tests. **Git is the source of truth for
> what's _done_** (a merged PR = a finished milestone); this file is the
> human-readable "you are here + ▶ next". Full design: `docs/session_recovery.md`.

**Milestone status:** M0 shipped ✅ · M1 (`auth-roles`) not started.
**In flight:** `chore/ci` — CI + green-gate enforcement (GitHub Actions on every PR; cross-platform `test:api`). Gap-review docs PR #13 merged ✅. No milestone branch open.
**Open PRs:** run `gh pr list` (this one, until merged).

## ▶ NEXT ACTION
Merge the CI PR (review → `/close-feature`), then start M1:
**`/run-milestone auth-roles --pause-after-spec`**

## Carryover notes
- M1 is **security-critical** → inline review **+** one diff-scoped `appsec` agent (Sonnet). See `docs/git_strategy.md` § Branch review.
- **M1 scope now includes the gap-review fold-ins** (`docs/milestones.md` § Scope fold-ins): account lifecycle (password reset, email verification, refresh-token decision), both-roles path, minimal profiles, `tos_accepted_at`, settings module owns `DATABASE_URL`, and **delete the throwaway `/api/sandbox`** (unauthenticated write) before real data. (memory: `m0-followups-for-m1`)
- ~~Make root `test:api` cross-platform when CI arrives~~ **done in the CI PR** (`scripts/test-api.mjs`). Branch protection **applied 2026-07-16** (repo made public): `main` requires a PR + both green checks + an up-to-date branch, admins included.
- Review is **inline-first** to conserve context/usage; the `/dod` forbidden-path tests are the always-on security floor.
- M0 box is now ticked in `docs/milestones.md` (was deferred to "the next branch" — this branch is it).
