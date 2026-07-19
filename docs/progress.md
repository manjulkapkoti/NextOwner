# Progress — where we are + what's next

> The semantic resume point. Updated by **`/checkpoint`** (manual, mid-milestone)
> and automatically at each milestone's close (**`/dod`** step 6, pre-PR commit);
> reconstructed and verified by **`/resume`** against git + tests. **Git is the
> source of truth for what's _done_** (a merged PR = a finished milestone); this
> file is the human-readable "you are here + ▶ next". Full design:
> `docs/session_recovery.md`.

**Milestone status:** M0–M2 ✅ merged. **App-shell (`pre-003`)** ✅ merged (#25), plus the public landing page (#26) and the register page (#27). **Design system** ✅ merged (#28) — tokens, brand, `StatusChip`, all six screens. **Agentic workflow** ✅ merged (#32) — dependency audit, spec-to-test traceability, browser a11y/layout gates. **M3 admin curation** ✅ shipped.
**In flight:** nothing. **M3 (admin curation)** shipped: the curation queue, approve/reject with a required reason, the `listingevent` audit trail, and the admin UI at `/admin`.
**Open PRs:** none.

## ▶ NEXT ACTION
**M4 — marketplace browse:**
**`/run-milestone marketplace-browse`**

It carries three queued items: the brand voice + landing copy deferred from the design system, `seed/seed.py` (~30 listings), and the first **public** `response_model` (schema-leak risk — the appsec trigger will fire on it).

## Carryover notes
- **App-shell shipped:** `/login`, `/`, `/my-listings`, `/sell`, `/register` routed and guarded; the already-authed-visitor redirects; the global-401 (`auth:unauthorized`) listener; a nav bar with logout. Replaced the M0 health page + its test. **25 frontend + 65 backend tests.**
- **Design system:** `app/src/theme.ts` holds every literal value (single source of token truth); `docs/design_system_spec.md` holds the decisions and reasons — one job each, nothing defined twice. Primary is brand blue `#2563EB`; **orange is brand-only, never an action colour**. Semantic colours deviate from the authored v1 spec because its literal values failed its own WCAG AA rule (focus ring measured 1.80:1) — every deviation is recorded with its measurement in § Deviations. Brand artwork lives in `docs/brand/` (no SVG exists, so those PNGs are the masters) and `docs/brand/regenerate-assets.js` rebuilds the app assets from them.
- **Brand voice deferred to M4** (owner's call): positioning is *succession, not transaction*. Scope in `milestones.md` § Scope fold-ins → M4. Navigation labels stay literal regardless.
- **Numbering convention (2026-07-18):** a foundation milestone inserted mid-sequence is `pre-NNN-<slug>` and claims no number, so the M-numbers **and** the M3–M12 spec numbers are unchanged (M3 = spec 003). Recorded in the constitution amendment log + `/new-spec`.
- **M2 decisions to remember:** owner-scoped routes return **404** (not 403); document serving is **owner-only** (buyer NDA access is M5); a `ListingDocument` table (not the JSON blob); money via a `Money` TypeDecorator (lossless Decimal); the upload-DoS was fixed with a streamed size cap + a Content-Length middleware.
- **M3 is on the security-critical list — resolved 2026-07-19, no longer an open question.** For a while this file asserted M3 was security-critical while the binding list (`M1/M2/M5/M7/M8/M10`) did not include it. That contradiction was real, and it is why M3 received an independent appsec pass — which found a blocking curation bypass. **The list now reads `M1/M2/M3/M5/M7/M8/M10`** (constitution amendment, 2026-07-19), and the list is additionally only a *floor*: `scripts/check_appsec_trigger.py` reads the diff and can escalate any milestone the list never predicted.
- **Status freshness is now CI-enforced** (#32): `scripts/check_status_freshness.py` runs on every push to `main` and fails the build if any of these three surfaces still describes work as in flight. The `/dod` refresh is the first line; that job is the backstop, bound to the merge because the ceremony can be skipped.
- **Standing facts:** refresh tokens deferred to deploy-hardening (`security.md` §9); account lifecycle (password reset, email verification) owned by **M8** (now security-critical); the security-critical list is **M1/M2/M3/M5/M7/M8/M10**. Implement slice-by-slice (Build order in `plan.md`; the red tests are the status, no checkboxes). This file self-refreshes at each milestone close (`/dod` step 6).
