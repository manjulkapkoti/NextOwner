# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`** (manual, mid-milestone)
> and automatically at each milestone's close (**`/dod`** step 6, pre-PR commit);
> reconstructed and verified by **`/resume`** against git + tests. **Git is the
> source of truth for what's _done_** (a merged PR = a finished milestone); this
> file is the human-readable "you are here + ▶ next". Full design:
> `docs/session_recovery.md`.

**Milestone status:** M0 ✅ · M1 (`auth-roles`) ✅ merged · **M2 (`listing-builder`) built, reviewed, PR open — awaiting human approval.**
**In flight:** branch `feat/002-listing-builder` — 8-slice build complete, `/dod` green (backend 65, frontend 11), inline + independent appsec review done (1 blocker — upload DoS — fixed on the branch), PR opened.
**Open PRs:** M2 listing-builder (see the PR).

## ▶ NEXT ACTION
Review the M2 PR, then **"close the feature"** (`/close-feature <pr#>`) to squash-merge + sync `main`. Then M3:
**`/run-milestone admin-curation --pause-after-spec`**

## Carryover notes
- **M2 decisions to know:** owner-scoped routes return **404** (not 403) for not-yours; document serving is **owner-only** (buyer NDA access is M5); a `ListingDocument` table replaced the JSON `document_paths` sketch; money via a `Money` TypeDecorator (lossless Decimal).
- **Still deferred (M1 finding #6 + M2):** the frontend has tested components but **no assembled app shell** — no router, `App.tsx` is still the M0 health page. The login flow and listing wizard aren't reachable in a running app yet. Owner: whenever the app-shell milestone is scoped (candidate: fold into M4 browse, or a small dedicated slice).
- **M3 is security-critical** (admin curation → `require_admin`, publish transition): gets the independent appsec pass.
- Refresh deferred to deploy-hardening; account lifecycle (password reset, email verification) owned by M8; security-critical list is M1/M2/M5/M7/M8/M10.

## Carryover notes
- M1 is **security-critical** → inline review **+** one diff-scoped `appsec` agent (Sonnet). See `docs/git_strategy.md` § Branch review.
- **M1 scope = the gap-review fold-ins** (`docs/milestones.md` § Scope fold-ins): **refresh-token decision** (FR-1), both-roles path, minimal profiles, `tos_accepted_at`, settings module owns `DATABASE_URL`, rate-limit behind a swappable backend, curate `requirements.txt`, **Google OAuth excluded** (FR-1, post-MVP), and **delete the throwaway `/api/sandbox`** (unauthenticated write) before real data. (memory: `m0-followups-for-m1`)
- **Account lifecycle (password reset + email verification) moved M1 → M8 on 2026-07-17** — it was M1's only heavy item and M8 builds the email channel it needs. **M8 is now security-critical** (list: M1/M2/M5/M7/**M8**/M10). Trade-off accepted: no self-serve password reset until M8 — fine while 100% local with no real users.
- **Implement slice by slice (2026-07-17):** `plan.md` now carries a **Build order** — one trust boundary per slice, one commit each. **The red test list is the status; `plan.md` has no checkboxes** and never should (status files drift; `/resume` trusts git + tests).
- Root `test:api` is cross-platform (`scripts/test-api.mjs`, landed in the CI PR #14). Branch protection **applied 2026-07-16** (repo made public): `main` requires a PR + both green checks + an up-to-date branch, admins included.
- Review is **inline-first** to conserve context/usage; the `/dod` forbidden-path tests are the always-on security floor.
- M0 is ticked in `docs/milestones.md`.
- **This file now self-refreshes at each milestone's close** (`/dod` step 6 / `/run-milestone`, committed on the feature branch before the PR opens) — see `docs/session_recovery.md`. `/checkpoint` still covers manual mid-milestone saves.
