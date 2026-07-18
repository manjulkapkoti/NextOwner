# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`** (manual, mid-milestone)
> and automatically at each milestone's close (**`/dod`** step 6, pre-PR commit);
> reconstructed and verified by **`/resume`** against git + tests. **Git is the
> source of truth for what's _done_** (a merged PR = a finished milestone); this
> file is the human-readable "you are here + ▶ next". Full design:
> `docs/session_recovery.md`.

**Milestone status:** M0–M2 ✅ merged. **App-shell (`pre-003`)** ✅ merged (#25), plus the public landing page (#26) and the register page (#27).
**In flight:** branch `feat/pre-003-design-system` — the design-system pass (owner-directed; no spec folder). Done: `theme.ts` implementing the v1 tokens, brand assets + `Wordmark`, and the front-door screens (landing, login, signup, nav) restyled. **Remaining: the dashboard and listing wizard are still on the old styling.** No PR opened yet.
**Open PRs:** none.

## ▶ NEXT ACTION
Finish the design-system pass on `feat/pre-003-design-system`: **restyle the dashboard (`MyListings`) and the listing wizard**, the last two screens still on the old styling. Then `/dod` → inline review → open the PR. Then M3:
**`/run-milestone admin-curation --pause-after-spec`**

## Carryover notes
- **App-shell shipped:** `/login`, `/`, `/my-listings`, `/sell`, `/register` routed and guarded; the already-authed-visitor redirects; the global-401 (`auth:unauthorized`) listener; a nav bar with logout. Replaced the M0 health page + its test. **25 frontend + 65 backend tests.**
- **Design system (in flight):** `app/src/theme.ts` holds every literal value (single source of token truth); `docs/design_system_spec.md` holds the decisions and reasons — one job each, nothing defined twice. Primary is brand blue `#2563EB`; **orange is brand-only, never an action colour**. Semantic colours deviate from the authored v1 spec because its literal values failed its own WCAG AA rule (focus ring measured 1.80:1) — every deviation is recorded with its measurement in § Deviations. Brand artwork lives in `docs/brand/` (no SVG exists, so those PNGs are the masters) and `docs/brand/regenerate-assets.js` rebuilds the app assets from them.
- **Brand voice deferred to M4** (owner's call): positioning is *succession, not transaction*. Scope in `milestones.md` § Scope fold-ins → M4. Navigation labels stay literal regardless.
- **Numbering convention (2026-07-18):** a foundation milestone inserted mid-sequence is `pre-NNN-<slug>` and claims no number, so the M-numbers **and** the M3–M12 spec numbers are unchanged (M3 = spec 003). Recorded in the constitution amendment log + `/new-spec`.
- **M2 decisions to remember:** owner-scoped routes return **404** (not 403); document serving is **owner-only** (buyer NDA access is M5); a `ListingDocument` table (not the JSON blob); money via a `Money` TypeDecorator (lossless Decimal); the upload-DoS was fixed with a streamed size cap + a Content-Length middleware.
- **M3 is security-critical** (admin curation → `require_admin`, the publish transition): gets the independent appsec pass.
- **Standing facts:** refresh tokens deferred to deploy-hardening (`security.md` §9); account lifecycle (password reset, email verification) owned by **M8** (now security-critical); the security-critical list is **M1/M2/M5/M7/M8/M10**. Implement slice-by-slice (Build order in `plan.md`; the red tests are the status, no checkboxes). This file self-refreshes at each milestone close (`/dod` step 6).
