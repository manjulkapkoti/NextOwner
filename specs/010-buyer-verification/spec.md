# Spec 010 — Buyer verification (manual)

> **Milestone M10** — `docs/design_implementation.md` Part 4 § *Milestone 10 — Manual buyer verification (F11)*.
> **Security-critical** (`docs/milestones.md`'s crown-jewel list M1/M2/M3/M5/M7/M8/M10 — an independent `appsec-engineer` pass is required before this milestone's PR opens, per constitution Article 3 §3).
> This is the codebase's Persona mock: "same states, no vendor. Swapping in real Persona later means replacing one page with their widget plus one webhook endpoint" (`design_implementation.md` Part 4).

## FR references

| FR | What it requires |
|---|---|
| **FR-3** | Buyers complete a profile: acquisition budget, target industries, experience, **optional proof of funds**. This milestone builds the proof-of-funds half. |
| **FR-14** | Sellers can approve/deny access requests and see buyer profile / **verification status** before approving. **Completes the half spec 005 deferred** ("The verification half is (Deferred to M10)" — `requirements.md` FR-14; spec 005 D5). |
| **F11** (`requirements.md` §1) | Basic buyer verification (email + manual proof-of-funds upload) — "manual stand-in for Persona." |
| NFR *Trust & safety* | "Verified-buyer badges" (`requirements.md` §3). |

**Scope fold-ins** (`docs/milestones.md` § Scope fold-ins → M10), each carried below as criteria: **the badge surfaces on the M1 profile (and in M5's request list)** (V8, V9 below); **a per-listing upload count / total-size quota, extending the M2 upload rules** (`security.md` §6 addendum) — read literally this quota belongs to M2's listing-document uploads, and D8 below explains how this milestone satisfies that wording honestly rather than silently narrowing it to only the new route.

---

## User stories

1. **As a buyer**, I want to upload proof of funds, so that sellers have a reason to trust my access requests beyond my say-so.
2. **As a buyer whose first submission was rejected**, I want to resubmit, so that a fixable mistake (a blurry scan, a stale statement) doesn't lock me out permanently.
3. **As an admin**, I want a review queue for pending verification submissions, so that curation of buyers is as deliberate as curation of listings (F3's sibling process for demand, not just supply).
4. **As an admin**, I want to revoke a verified badge after the fact, so that a buyer who turns out fraudulent doesn't keep the trust signal indefinitely.
5. **As a seller deciding on an access request**, I want to see whether the requesting buyer is verified, so that FR-14's promise — profile **and verification status** before approving — is finally whole.
6. **As a buyer**, I want to see my own verification status on my profile, so that I know what a seller currently sees about me.

---

## Decisions

- **D1 — State machine: `unverified → pending → verified | rejected`, plus `rejected → pending` (resubmit) and `verified → rejected` (admin revoke).** `unverified` is the default (no submission yet); uploading a document is the only buyer-initiated transition, and it always lands on `pending` — from `unverified` (first submission) or from `rejected` (resubmission, story 2). Only an admin can move a `pending` submission to `verified` or `rejected` ("reject" doubles as both "deny" and "revoke": a `pending → rejected` decision reads as *deny*, a `verified → rejected` one reads as *revoke* — same endpoint, same event shape, and story 4's revoke needs no separate route). `verified` is not otherwise terminal — an admin can still revoke it — but a buyer cannot re-trigger review once verified (D3).
- **D2 — No "needs-manual-review" state distinct from `pending`.** `error_handling.md` §5's Persona vocabulary is `pending / failed / needs-manual-review`, but that third state exists in a *hybrid* automated+manual vendor to mean "the automated check couldn't decide, escalate to a human." Here manual review **is** the only mechanism — there is no automated check to escalate from — so a separate state would carry the same meaning as `pending` under a different name. Collapsing them is the honest MVP simplification of the vendor-shaped machine, not a missing state.
- **D3 — Once `verified`, a buyer cannot upload a new document to force re-review.** `POST /verification/documents` while `status == "verified"` → 409. This prevents a verified buyer from churning the queue and matches the "badge means something until an admin actively revokes it" reading of story 4 — the only way out of `verified` is an admin action, not a buyer re-submission.
- **D4 — No role gate on the upload/status routes.** F11 is framed from the buyer's perspective, but — same reasoning as spec 009 D4 for the watchlist — the design doc doesn't ask for an `is_buyer`-only restriction, and a dual buyer+seller account (FR-2) should not be blocked from a feature its buyer half needs. Any authenticated user may submit; the badge is simply irrelevant to a pure-seller account since nothing surfaces it outside `BuyerProfile` (D7) and the caller's own profile.
- **D5 — Documents live in a new `BuyerVerificationDocument` table, keyed by `user_id`, not `listing_id`.** The existing `StorageBackend.save(listing_id, data, suffix)` signature (`backend/app/storage.py`) is reused verbatim with the caller's `user.id` passed in its first positional slot — the parameter names "an owning entity," not specifically a listing (see plan.md). This is a **narrower reuse of the same seam M2 built**, not a new upload pipeline: identical content-type/extension/magic-byte whitelist, identical streamed size cap, identical path confinement.
- **D6 — `BuyerVerificationEvent` audit table, justified per constitution Article 2 #5.** Ask what it preserves that the row itself loses: `User.verification_status`/`verification_reason` hold only the *current* decision, so a rejection reason is silently overwritten the moment a resubmission is approved — exactly the class of loss Article 2 #5 says earns an audit row (the same reasoning `listingevent` used for approve/reject). A future `trust-safety-ops` fraud review needs "was this buyer ever rejected, and why" even after a later approval, which the row alone cannot answer. Shape mirrors `listingevent`: `actor_id`, `action`, `from_status`, `to_status`, `reason`, `timestamp`.
- **D7 — The badge surfaces as both a raw status and a computed boolean, on two response models.** `UserRead` (the caller's own profile, `GET /api/auth/me`) gains `verification_status` + a computed `verified` property, mirroring the existing `email_verified_at` → `email_verified` pattern (`schemas.py`) exactly. `BuyerProfile` (M5's access-request list, `spec 005` D5's deferred field) gains the same pair — this is the literal fold-in bullet "the badge surfaces on the M1 profile (and in M5's request list)" and the FR-14 completion.
- **D8 — The upload-quota fold-in is honored on both surfaces it plausibly means, not narrowed to the new route.** `docs/milestones.md`'s M10 bullet reads "a **per-listing** upload count / total-size quota (extends the M2 upload rules)" — read literally that is M2's `POST /listings/{id}/documents`, which today has no cap on document *count*, only per-file size (`max_upload_bytes`). Silently reinterpreting the bullet as "only the new verification route" would drop a real gap the fold-in explicitly names. This milestone therefore adds one shared quota check (a config pair: `max_documents_per_owner`, `max_total_upload_bytes_per_owner`) and applies it to **both** `POST /listings/{id}/documents` (retrofit, closing M2's gap) **and** `POST /verification/documents` (the new route, keyed by `user_id` instead of `listing_id` — "per-listing" generalizes to "per owning entity," which is what the shared helper actually checks).
- **D9 — Verification documents are held by us, not a vendor — an explicit, recorded deviation from `data_protection.md` §4 for this milestone only.** §4 says "the M10 mock must model [the Persona pattern]: our DB never receives the document, only the outcome." That is correct for a *real* Persona integration, where the vendor's hosted widget receives the file and only a verification result crosses into our DB. F11 and `design_implementation.md` Part 4 both describe something different for the MVP: **manual** review by our own admin ("Admin reviews in `/admin` → sets `verified`") — which is impossible without an admin viewing the actual document somewhere our system controls, because no vendor exists yet to hold it. The two docs disagree on a mechanism, not a goal; §4's underlying goal (minimize our raw-document PII surface) is honored as far as it can be at MVP: the document is stored through the same permission-gated, never-statically-served path M2 already uses (D5), access is admin-**or**-uploader only (S4/S5), no server-side parsing/extraction of its contents happens, and the **profile-facing** surfaces (`UserRead`, `BuyerProfile`) carry only the outcome — `verification_status` + a timestamp — never the file itself, which is the one part of §4's letter this milestone can keep. **Recorded here, not silently resolved,** so a reader of `data_protection.md` isn't misled about what M10 actually does; revisit this decision the moment a real KYC vendor is integrated (post-MVP), at which point the upload route is replaced by the vendor's widget and this deviation is retired, not just the code that caused it.
- **D10 — Erasure: the document cascades (deletes), the event row is exempt-and-kept, the status fields anonymize with the rest of `User`.** Per `data_protection.md` §3's per-child-table question: a `BuyerVerificationDocument` is the single most sensitive PII artifact this milestone introduces (a financial/identity document) and carries no evidentiary value once its owner is gone, so it is **hard-deleted** (row + the underlying file via `storage.delete`) on user erasure — matching §3's own example, "uploaded files → delete from `uploads/`." `BuyerVerificationEvent` rows are **audit-exempt** like every other event table (§3: "ids + minimal data, not PII snapshots" — no document content, no free-text buyer data, just ids/status/reason). `User.verification_status`/`verification_reviewed_at`/`verification_reason` are ordinary columns on the already-erasure-ready `User` row (M1) and anonymize with it — same treatment as `budget`/`target_industries`.

---

## Acceptance criteria

> Each line becomes **exactly one test** (constitution Article 3 §2), written failing first. Group letters: **V** verification core (FR-3/FR-14/F11) · **S** security & abuse (crown jewels — this milestone gets the independent `appsec-engineer` pass) · **X** errors & failure modes.

### V — Verification core

- **V1** — GIVEN an authenticated buyer with no prior submission, WHEN they `POST /api/verification/documents` with a valid PDF, THEN 201 and `GET /api/verification` shows `status: "pending"` with the document listed.
- **V2** — GIVEN an authenticated user with no submission ever, WHEN they `GET /api/verification`, THEN `status: "unverified"` and an empty document list.
- **V3** — GIVEN a `pending` submission, WHEN an admin calls `GET /api/admin/verifications`, THEN it appears in the queue with the buyer's profile fields (display name, budget, target industries, experience) and submitted-document metadata.
- **V4** — GIVEN a `pending` submission, WHEN an admin calls `POST /api/admin/verifications/{user_id}/approve`, THEN the buyer's status becomes `verified`, `verification_reviewed_at` is stamped, and a `BuyerVerificationEvent` row records the transition (D6).
- **V5** — GIVEN a `pending` submission, WHEN an admin calls `POST /api/admin/verifications/{user_id}/reject` with a reason, THEN the buyer's status becomes `rejected`, the reason is stored and returned via `GET /api/verification`, and an event row is written.
- **V6** — GIVEN a `rejected` buyer, WHEN they `POST /api/verification/documents` again, THEN 201 and status returns to `pending` (D1 resubmission).
- **V7** — GIVEN a `verified` buyer, WHEN they `POST /api/verification/documents`, THEN 409 (D3 — no re-triggering review once verified).
- **V8** — GIVEN a `verified` buyer with a pending access request on a seller's listing, WHEN the seller calls `GET /api/my/listings/{listing_id}/access-requests` (M5's list, `AccessRequestWithBuyer`), THEN the entry's `BuyerProfile` shows `verification_status: "verified"` and `verified: true` (completes FR-14 — spec 005 D5's deferred field).
- **V9** — GIVEN a buyer whose own status is `pending`, WHEN they `GET /api/auth/me`, THEN the response includes `verification_status: "pending"` and `verified: false` (D7).
- **V10** — GIVEN a buyer, WHEN they `POST /api/verification/documents` with a `.exe` file (or any type outside PDF/PNG/JPEG), THEN 415 — the M2 whitelist rule reused verbatim (D5).
- **V11** — GIVEN a buyer, WHEN they `POST /api/verification/documents` with a file exceeding `max_upload_bytes`, THEN 413 — the M2 streamed-size-cap rule reused verbatim (D5).
- **V12** — GIVEN a caller (parametrized: a buyer at the verification-document count cap, and a seller at their listing's document count cap) WHEN they upload one more document, THEN 413 `upload_quota_exceeded` (D8 — both surfaces share the quota).
- **V13** — GIVEN a caller (parametrized: buyer verification docs, seller listing docs) whose existing documents are already at the total-size cap, WHEN they upload another (individually within `max_upload_bytes`) document that would push the total over `max_total_upload_bytes_per_owner`, THEN 413 `upload_quota_exceeded` (D8).
- **V14** — GIVEN a `verified` buyer, WHEN an admin calls `POST /api/admin/verifications/{user_id}/reject` with a reason, THEN status moves `verified → rejected` (D1's revoke path — story 4) and a new event row records `from_status: "verified"`.

### S — Security & abuse (`docs/security.md` §7 M10: "buyer cannot self-verify (`verified` ignored/403); only admin flips it; proof-of-funds upload obeys the M2 upload rules")

- **S1** — GIVEN an authenticated buyer, WHEN they `PUT /api/profile` with a body containing `"verification_status": "verified"` (mass-assignment attempt), THEN the field is silently ignored (not a schema field of `ProfileUpdate`) and `GET /api/verification` shows the status unchanged.
- **S2** — GIVEN an authenticated non-admin user, WHEN they call `POST /api/admin/verifications/{user_id}/approve` or `.../reject` directly, THEN 403 for both — no client path to self-verify or verify anyone else (the "ignored/403" security.md wording: ignored at the profile route, 403 at the admin route).
- **S3** — GIVEN an authenticated non-admin user, WHEN they `GET /api/admin/verifications`, THEN 403 — the queue itself is not a buyer-visible surface.
- **S4** — GIVEN buyer A and buyer B both authenticated, WHEN A calls `GET /api/verification/documents/{B's document id}`, THEN 404 — not 403, matching spec 002's chosen existence-oracle-safe shape for owner-scoped routes (`docs/milestones.md` M2 row: "owner-scoped routes return 404 for not-yours").
- **S5** — GIVEN an admin, WHEN they `GET /api/verification/documents/{any user's document id}`, THEN 200 — admin review requires seeing the actual submission (D9).
- **S6** — GIVEN an unauthenticated visitor, WHEN they call any of `POST /verification/documents`, `GET /verification`, `GET /verification/documents/{id}`, `GET /admin/verifications`, `POST /admin/verifications/{id}/approve`, `POST /admin/verifications/{id}/reject`, THEN 401 for all six.
- **S7** — GIVEN a multipart upload whose filename is a path-traversal string (`../../etc/passwd`), WHEN `POST /api/verification/documents`, THEN the stored file stays confined under the verification uploads base — the client filename never reaches the storage path (reuses `storage.py`'s `_resolve_within_base` confinement, same test class as M2's).
- **S8** — GIVEN the `GET /api/admin/verifications` response schema, WHEN inspected, THEN it contains no `password_hash` and no other user's data beyond the fields V3 lists (schema-leak test, same discipline as `ListingPublic`'s absent-field-set assertion at spec 004 S3).
- **S9** — GIVEN the `GET /api/verification` response for the caller, WHEN inspected, THEN document entries expose `id`, `filename`, `content_type`, `size_bytes`, `uploaded_at` only — never the server-generated `storage_key` (an internal path component, not something a client needs or should be able to guess at).

### X — Errors & failure modes (`docs/error_handling.md`)

- **X1** — GIVEN a `POST /api/verification/documents` request with no `file` part in the multipart body, WHEN sent, THEN 422.
- **X2** — GIVEN `POST /api/admin/verifications/{user_id}/reject` with no `reason` field, WHEN sent, THEN 422 — mirrors M3's "reject reason stored" requirement.
- **X3** — GIVEN a user whose status is `unverified` (no pending submission), WHEN an admin calls `POST /api/admin/verifications/{user_id}/approve`, THEN 409 `invalid_transition` — nothing to approve.
- **X4** — GIVEN a user whose status is already `rejected`, WHEN an admin calls `POST /api/admin/verifications/{user_id}/reject` again, THEN 409 `invalid_transition` — `rejected` is not a valid `from_status` for reject (only `pending` and `verified` are, per D1).
- **X5** — GIVEN a forced internal error inside the verification router, WHEN any of its routes is called, THEN the generic 500 contract (`detail`, `request_id`) with no stack trace, SQL, or internal detail (reuses the M1 global handler).

## Errors & failure modes (`docs/error_handling.md`)

- **Validation (422):** X1 (missing file part), X2 (missing rejection reason) — field-level shape, inline errors on the frontend form.
- **Illegal transitions (409):** X3 (approve with nothing pending), X4 (reject an already-rejected user), V7 (upload while already `verified`) — toast + refetch the entity's state on the frontend.
- **500-safety:** X5 — generic contract, no leak.
- **Vendor-shaped failure states:** this milestone's mock vendor states are `pending` (queued for review) and `rejected` (with a reason) — the local equivalents of Persona's `pending`/`failed` in `error_handling.md` §5's table; there is no `needs-manual-review` state distinct from `pending` (D2). A future real Persona swap adds a `kyc_unavailable` (502/503) upstream-failure class per §4's table — out of scope here since there is no live vendor to fail.
- **UI states:** the buyer's verification page and the admin queue both get the standard empty/loading/error triad (`error_handling.md` §3); the upload form shows inline 422s and a 409 banner for the "already verified" case (V7); a 413 (`upload_quota_exceeded` or `file_too_large`) surfaces as a clear "too many/too large" message, not a generic failure.

## Out of scope (deliberately deferred)

- **Real Persona/KYC vendor integration.** This milestone is explicitly the mock (constitution Article 1); D9 records exactly how the mock's document-handling differs from the eventual real integration and why.
- **Seller verification (FR-4).** Already folded into M3 curation ("seller-legitimacy review is folded into curation" — `docs/milestones.md` M3 fold-in); not reopened here.
- **Automatic re-review / expiry of a `verified` badge.** Verification does not expire on a timer; only an explicit admin `reject` (D1's revoke path) removes it. Time-based re-verification is a reasonable post-MVP addition, not part of F11's one-line scope.
- **Buyer-visible admin notes beyond the single `reason` field.** No threaded admin/buyer conversation about a rejection — that's what chat (M6) is for once the buyer has *approved* access to a listing, and verification review is a different relationship (admin, not seller).
- **Notification events for verification decisions.** No `notification` row is emitted when a buyer is approved/rejected/revoked — M8's projection pattern could be extended here later (from `BuyerVerificationEvent`, exactly as M8 projects from `listingevent`), but no acceptance criterion above requires it, and inventing an unrequested notification surface would be the same speculative-schema mistake M3's original fold-in made before M8 corrected it (`docs/milestones.md` M8 fold-in).
- **Bulk admin actions** (approve/reject multiple buyers at once) — single-user endpoints only, consistent with M3's curation queue at its own MVP stage.
