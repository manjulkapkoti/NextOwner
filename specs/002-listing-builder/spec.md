# Spec 002 — Seller Listing Builder + Uploads (M2)

> **Milestone:** M2 — Seller listing builder ([`design_implementation.md`](../../docs/design_implementation.md) Part 4 → *Milestone 2*).
> **Complies with:** [`specs/000-constitution.md`](../000-constitution.md). **Security-critical** (uploads + owner-scoped writes) — the forbidden-path tests are the crown jewels, and this milestone gets an independent appsec pass.
> **Status:** awaiting approval (`--pause-after-spec`).

---

## FR references

| FR | What it requires | This milestone |
|---|---|---|
| **FR-5** | Sellers create listings with structured fields (type, revenue, profit, MRR, churn, asking price, …) | Yes |
| **FR-6** | Listings are anonymous publicly; identifying details hidden until NDA | The **public/private table split** is established here (`Listing` vs `ListingPrivate`). Public *serving* is M4; the NDA *gate* is M5. In M2, private data is **owner-only**. |
| **FR-7** | Listings enter **pending-review**; an admin approves/rejects before publication | The seller-side transition `draft → pending_review` (submit). Admin approve/reject is **M3**. |
| **FR-8** | Sellers can edit, pause, mark under-offer, or close listings | Edit / pause / resume / close here. `under_offer`/`sold` are M7/M12. |
| **FR-9** | Sellers upload supporting documents, stored privately | Yes — multipart upload, owner-only, path-confined. |

**Scope fold-ins (`milestones.md` § Scope fold-ins → M2), all in:** money is **`Decimal`** never `float`; listing lifecycle (`pause`/`close`, and **editing a `live` listing sends it back to `pending_review`**); **`GET /my/listings`**; **uploads behind a storage port** (`save`/`open` — horizontal-scale blocker #2).

---

## Decisions (baked into this spec)

- **Owner-scoped endpoints return `404`, not `403`, for a listing you don't own.** A draft is unpublished; `403` would confirm it exists. `404`-for-both (absent or not-yours) leaks nothing. (The testing checklist explicitly leaves this choice to the spec.)
- **`ListingDocument` table instead of a `document_paths` JSON blob** — refines the §3.5 sketch (as the Decimal fold-in refines `float`). One row per file supports per-document download-by-id and the M5 gate cleanly.
- **Allowed upload types (MVP):** `application/pdf`, `image/png`, `image/jpeg`; **max 10 MB**. Enforced by content-type **and** extension.
- **Document serving is owner-only in M2.** Buyer access via the NDA gate is **M5** — noted in the plan so M5 layers on, not rewrites.

---

## User stories

1. **As a seller,** I want to build a listing through a multi-step form with structured financial fields, so that buyers get comparable, searchable data.
2. **As a seller,** I want my listing to start as a private draft that only I can see or edit, so that nothing half-finished is exposed.
3. **As a seller,** I want to submit my listing for review, so that curation can approve it before it goes live.
4. **As a seller,** I want to pause, resume, or close my listing, so that I control its availability.
5. **As a seller,** I want to upload supporting documents (P&L, screenshots) that stay private, so that a vetted buyer can later see proof.
6. **As a seller,** I want a dashboard of my own listings, so that I can manage them.
7. **As the platform,** I want every listing write and every upload scoped to its owner and validated as hostile, so that no one can touch another seller's listing or smuggle a malicious file.

---

## Acceptance criteria

**Each = exactly one test, written failing first.** Paths omit `/api` for readability; test code always includes it.

### A. Create a draft
- **A1** — GIVEN an authenticated seller, WHEN `POST /listings` with valid fields, THEN **201**, `status="draft"`, `owner_id` = the caller.
- **A2** — GIVEN the create body also contains `"owner_id": <someone else>`, WHEN posted, THEN it's **ignored** — the stored `owner_id` is the caller (mass-assignment).
- **A3** — GIVEN the create body contains `"status": "live"`, WHEN posted, THEN it's **ignored** — the listing is `draft` (no self-publishing).
- **A4** — GIVEN `asking_price <= 0`, WHEN posted, THEN **422**.
- **A5** — GIVEN a required structured field is missing, WHEN posted, THEN **422**.
- **A6** — GIVEN no token, WHEN `POST /listings`, THEN **401**.
- **A7** — GIVEN a listing created with `asking_price` `1234567.89`, WHEN read back from the DB, THEN it is an exact **`Decimal`** — no float rounding (money is `Decimal`, fold-in).

### B. Edit
- **B1** — GIVEN a seller's own draft, WHEN `PUT /listings/{id}` with new values, THEN **200** and the fields update.
- **B2** — GIVEN a listing owned by someone else, WHEN `PUT /listings/{id}`, THEN **404** (owner-scoped; no existence leak).
- **B3** — GIVEN a seller's own **`live`** listing, WHEN they `PUT` an edit, THEN it returns to **`pending_review`** (no bait-and-switch behind curation — fold-in).
- **B4** — GIVEN a `PUT` body with `"owner_id"`/`"status"`, WHEN sent, THEN both are **ignored** (mass-assignment on edit).

### C. Lifecycle transitions
- **C1** — GIVEN a seller's own draft, WHEN `POST /listings/{id}/submit`, THEN **200**, `status="pending_review"`.
- **C2** — GIVEN a listing already `pending_review`, WHEN submitted again, THEN **409** (illegal transition).
- **C3** — GIVEN someone else's listing, WHEN `POST .../submit`, THEN **404**.
- **C4** — GIVEN a seller's own `live` listing, WHEN `POST .../pause`, THEN `status="paused"`.
- **C5** — GIVEN a `paused` listing, WHEN `POST .../resume`, THEN `status="live"` (no re-review — pausing isn't a content change).
- **C6** — GIVEN a `draft`, WHEN `POST .../pause`, THEN **409** (a draft isn't live).
- **C7** — GIVEN any seller endpoint, WHEN a seller tries to reach `status="live"` directly, THEN there is **no path** — submit only reaches `pending_review`. (Publication is admin-only, M3.)
- **C8** — GIVEN a seller's own listing, WHEN `POST .../close`, THEN `status="closed"`.

### D. Uploads (hostile input — `security.md` §2)
- **D1** — GIVEN a seller's own listing, WHEN they upload a valid PDF to `POST /listings/{id}/documents`, THEN **201**, a `ListingDocument` row exists, and the file is stored under `uploads/{listing_id}/` with a **server-generated** name.
- **D2** — GIVEN someone else's listing, WHEN uploading to it, THEN **404** (owner-scoped).
- **D3** — GIVEN a disallowed type (e.g. `text/html` / `.exe`), WHEN uploaded, THEN **415** — content-type **and** extension are whitelisted.
- **D4** — GIVEN a file over the max size, WHEN uploaded, THEN **413**.
- **D5** — GIVEN a client filename of `../../../etc/passwd`, WHEN uploaded, THEN the stored path stays **inside `uploads/{listing_id}/`** (the client name is never used in the path; traversal is neutralized).
- **D6** — GIVEN no token, WHEN uploading, THEN **401**.
- **D7** *(added from appsec review)* — GIVEN a whitelisted content-type (`application/pdf`) but bytes that aren't a PDF, WHEN uploaded, THEN **415** — the content is checked against its declared type (magic bytes), so a whitelisted header can't smuggle a different file.

> **Upload DoS (fixed on the branch from the appsec review):** the size cap is enforced by **streaming** the read and aborting the moment it exceeds `max_upload_bytes` (never buffering an over-limit file), plus a **Content-Length request-body cap** that rejects an over-cap body *before* it's parsed to disk. D4 exercises the streaming abort; the middleware is the pre-parse guard (a reverse proxy is the production backstop for chunked/absent-length bodies — `security.md` §9).

### E. Download (owner-only in M2)
- **E1** — GIVEN a seller's own document, WHEN `GET /listings/{id}/documents/{doc_id}`, THEN **200** with `Content-Disposition: attachment` (never inline).
- **E2** — GIVEN a document on someone else's listing, WHEN requested, THEN **404** (buyer NDA-gated access is M5).
- **E3** — GIVEN a traversal or absolute path pushed through the download identifier, WHEN requested, THEN it **cannot** escape `uploads/` (404/400, no file outside the tree served).

### F. Dashboard
- **F1** — GIVEN a seller with drafts and a live listing, WHEN `GET /my/listings`, THEN it returns **only their own** listings, drafts included.
- **F2** — GIVEN two sellers, WHEN one calls `GET /my/listings`, THEN the other's listings never appear.

### G. Storage port (structural — horizontal-scale blocker #2)
- **G1** — GIVEN the upload storage, WHEN inspected, THEN it is behind a **`StorageBackend`** interface with a `save`/`open` contract and a `LocalDiskStorageBackend` default — so an object-storage swap is a config change, not a rewrite. **Path confinement lives in the adapter.**

### H. Frontend
- **H1** — GIVEN the listing wizard, WHEN the seller enters `asking_price <= 0` (or leaves a required field empty), THEN an **inline validation error** shows and the step can't advance.
- **H2** — GIVEN a logged-in seller, WHEN the my-listings view renders, THEN it lists their listings with status, and shows an **empty state** when there are none.

---

## Security & abuse

*(From `security.md` §7 M2 + §2 uploads + §6 file-attacks. Crown jewels — written first.)*

| Threat (§6) | Covered by |
|---|---|
| **Mass assignment** — `owner_id` / `status` on create or edit | A2, A3, B4 |
| **No self-publish** — seller reaching `live` without admin | A3, C7 |
| **IDOR** — writing/reading/uploading to another's listing | B2, C3, D2, E2, F2 |
| **Illegal state transition** — submit non-draft, pause a draft | C2, C6 |
| **Path traversal** — client filename `../../…`, absolute paths, encoded traversal | D5, E3 |
| **Malicious upload** — wrong/spoofed type, oversized | D3, D4 |
| **Info leakage** — serving a doc inline as HTML | E1 (`Content-Disposition: attachment`) |

**Not negotiable in implementation:** `owner_id` and `status` always server-derived · owner-scoped load (`404` for not-yours) on every `{id}` route · upload type+size whitelist · **server-generated stored filename**, final path resolved and asserted inside `uploads/` **in the storage adapter** · documents served only through the owner check, `attachment` disposition, never inline/executable · money is `Decimal`.

---

## Errors & failure modes

*(From `error_handling.md`. M2 reuses the M1 contract; new codes below.)*

| Path | Status | `code` | Test |
|---|---|---|---|
| Invalid/missing listing fields, price ≤ 0 | 422 | field-level | A4, A5 |
| Listing not found / not owner | 404 | `not_found` | B2, C3, D2, E2 |
| Illegal transition (submit non-draft, pause draft) | 409 | `invalid_transition` | C2, C6 |
| Disallowed upload type | 415 | `unsupported_media_type` | D3 |
| Oversized upload | 413 | `file_too_large` | D4 |
| Unauthenticated | 401 | `unauthorized` | A6, D6 |

**Frontend:** wizard step validation (inline, can't advance on error — H1); my-listings empty/loading/error states (H2); upload progress + reject message on 413/415.

---

## Data protection

- **`ListingPrivate` + `ListingDocument` hold confidential business data** (company name, URL, financials, uploaded files) — owner-only now, NDA-gated at M5. Never on a public `response_model`.
- **Uploaded files live under `uploads/{listing_id}/`** with server-generated names; on listing erasure/close the delete path removes them (`data_protection.md` §5 — design the delete path; wired fully with the erasure flow later).
- No new PII on the *user*; listing/company data is business data, still access-controlled.

## Out of scope (deferred)

- **Buyer access to private data / documents** — the NDA gate is **M5**. M2 is owner-only.
- **Admin approve/reject** (`pending_review → live`/`rejected`) — **M3**.
- **`under_offer` / `sold`** transitions — M7 / M12.
- **Public browse of live listings** — M4.
- **Malware scanning / archive-bomb defense** — post-MVP (`security.md` §6 notes it).
- **Owner walkthrough `video_url`** — optional Baton field, not adopted (deferred).
