# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`** (manual, mid-milestone)
> and automatically at each milestone's close (**`/dod`** step 6, pre-PR commit);
> reconstructed and verified by **`/resume`** against git + tests. **Git is the
> source of truth for what's _done_** (a merged PR = a finished milestone); this
> file is the human-readable "you are here + ▶ next". Full design:
> `docs/session_recovery.md`.

**Milestone status:** M0–M2 ✅ merged. **App-shell (`pre-003`)** built, `/dod` green, PR open — awaiting human approval.
**In flight:** branch `feat/pre-003-app-shell` — 3-slice build complete (router+guards, global-401 listener, nav+logout), inline review only (not security-critical, no appsec pass), PR opened.
**Open PRs:** app-shell (see the PR).

## ▶ NEXT ACTION
Review the app-shell PR, then **"close the feature"** (`/close-feature <pr#>`) to squash-merge + sync `main`. Then M3:
**`/run-milestone admin-curation --pause-after-spec`**

## Carryover notes
- **App-shell shipped:** `/login`, `/`, `/my-listings`, `/sell` routed and guarded; the already-authed-visitor-at-`/login` redirect; the global-401 (`auth:unauthorized`) listener; a nav bar with logout. Replaced the M0 health page + its test. 15 frontend tests total (was 11).
- **Numbering convention (2026-07-18):** a foundation milestone inserted mid-sequence is `pre-NNN-<slug>` and claims no number, so the M-numbers **and** the M3–M12 spec numbers are unchanged (M3 = spec 003). Recorded in the constitution amendment log + `/new-spec`.
- **M2 decisions to remember:** owner-scoped routes return **404** (not 403); document serving is **owner-only** (buyer NDA access is M5); a `ListingDocument` table (not the JSON blob); money via a `Money` TypeDecorator (lossless Decimal); the upload-DoS was fixed with a streamed size cap + a Content-Length middleware.
- **M3 is security-critical** (admin curation → `require_admin`, the publish transition): gets the independent appsec pass.
- **Standing facts:** refresh tokens deferred to deploy-hardening (`security.md` §9); account lifecycle (password reset, email verification) owned by **M8** (now security-critical); the security-critical list is **M1/M2/M5/M7/M8/M10**. Implement slice-by-slice (Build order in `plan.md`; the red tests are the status, no checkboxes). This file self-refreshes at each milestone close (`/dod` step 6).
