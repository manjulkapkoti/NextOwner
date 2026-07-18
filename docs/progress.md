# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`** (manual, mid-milestone)
> and automatically at each milestone's close (**`/dod`** step 6, pre-PR commit);
> reconstructed and verified by **`/resume`** against git + tests. **Git is the
> source of truth for what's _done_** (a merged PR = a finished milestone); this
> file is the human-readable "you are here + ▶ next". Full design:
> `docs/session_recovery.md`.

**Milestone status:** M0–M2 ✅ merged (scaffold · auth · listing builder + uploads). **App-shell (`pre-003`)** — spec + roadmap committed, **paused pre-build, awaiting "go".**
**In flight:** branch `feat/pre-003-app-shell` — spec/plan written and the milestone inserted in the runbook (pre-003 prefix, no renumbering); **no code yet**.
**Open PRs:** none.

## ▶ NEXT ACTION
Build the app-shell milestone — say **"go"** (or `/run-milestone` continues it): failing tests → 3 frontend slices → `/dod` → PR. **Then M3:** `/run-milestone admin-curation --pause-after-spec`.

## Carryover notes
- **App-shell (`pre-003`) scope:** wire the built-but-unwired M1/M2 frontend into a running app — router (`/login`, `/my-listings`, `/sell`), nav + logout, and the global-401 redirect (the `auth:unauthorized` listener `api.ts` already emits). Replaces the M0 health page + its test. Frontend-only, **not** security-critical → no appsec pass.
- **Numbering convention (2026-07-18):** a foundation milestone inserted mid-sequence is `pre-NNN-<slug>` and claims no number, so the M-numbers **and** the M3–M12 spec numbers are unchanged (M3 = spec 003). Recorded in the constitution amendment log + `/new-spec`.
- **M2 decisions to remember:** owner-scoped routes return **404** (not 403); document serving is **owner-only** (buyer NDA access is M5); a `ListingDocument` table (not the JSON blob); money via a `Money` TypeDecorator (lossless Decimal); the upload-DoS was fixed with a streamed size cap + a Content-Length middleware.
- **M3 is security-critical** (admin curation → `require_admin`, the publish transition): gets the independent appsec pass.
- **Standing facts:** refresh tokens deferred to deploy-hardening (`security.md` §9); account lifecycle (password reset, email verification) owned by **M8** (now security-critical); the security-critical list is **M1/M2/M5/M7/M8/M10**. Implement slice-by-slice (Build order in `plan.md`; the red tests are the status, no checkboxes). This file self-refreshes at each milestone close (`/dod` step 6).
