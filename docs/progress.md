# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`**; reconstructed and
> verified by **`/resume`** against git + tests. **Git is the source of truth for
> what's _done_** (a merged PR = a finished milestone); this file is the
> human-readable "you are here + ▶ next". Full design: `docs/session_recovery.md`.

**Milestone status:** M0 shipped ✅ · M1 (`auth-roles`) not started.
**In flight:** `chore/gap-review-docs` — the end-to-end gap-review docs PR (repo hygiene + roadmap capture: M12 deal completion, M8 → notifications engine, per-milestone scope fold-ins). No milestone branch open.
**Open PRs:** run `gh pr list` (this one, until merged).

## ▶ NEXT ACTION
Merge the gap-review docs PR (review → `/close-feature`), then start M1:
**`/run-milestone auth-roles --pause-after-spec`**

## Carryover notes
- M1 is **security-critical** → inline review **+** one diff-scoped `appsec` agent (Sonnet). See `docs/git_strategy.md` § Branch review.
- **M1 scope now includes the gap-review fold-ins** (`docs/milestones.md` § Scope fold-ins): account lifecycle (password reset, email verification, refresh-token decision), both-roles path, minimal profiles, `tos_accepted_at`, settings module owns `DATABASE_URL`, and **delete the throwaway `/api/sandbox`** (unauthenticated write) before real data. (memory: `m0-followups-for-m1`)
- Make root `test:api` **cross-platform** when CI arrives — CI + branch protection is recommended **before** M1 (gap review, group E).
- Review is **inline-first** to conserve context/usage; the `/dod` forbidden-path tests are the always-on security floor.
- M0 box is now ticked in `docs/milestones.md` (was deferred to "the next branch" — this branch is it).
