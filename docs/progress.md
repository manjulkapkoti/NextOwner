# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`**; reconstructed and
> verified by **`/resume`** against git + tests. **Git is the source of truth for
> what's _done_** (a merged PR = a finished milestone); this file is the
> human-readable "you are here + ▶ next". Full design: `docs/session_recovery.md`.

**Milestone status:** M0 shipped ✅ · M1 (`auth-roles`) not started.
**In flight:** `chore/session-recovery` (session-recovery tooling — this PR). No milestone branch open.
**Open PRs:** run `gh pr list` (this one, until merged).

## ▶ NEXT ACTION
Start M1: **`/run-milestone auth-roles --pause-after-spec`**
(and tick the M0 box in `docs/milestones.md` on that branch).

## Carryover notes
- M1 is **security-critical** → inline review **+** one diff-scoped `appsec` agent (Sonnet). See `docs/git_strategy.md` § Branch review.
- M0 follow-ups to fold into M1: **delete the throwaway `/api/sandbox`** (unauthenticated write) before real data; make root `test:api` **cross-platform** when CI arrives. (memory: `m0-followups-for-m1`)
- Review is **inline-first** to conserve context/usage; the `/dod` forbidden-path tests are the always-on security floor.
