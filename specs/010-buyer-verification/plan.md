# Plan 010 — M10: Buyer verification

> Implementation plan for [`spec.md`](./spec.md). Schema, endpoints, gates, and — at the end — the **Build order**, the ordered slices the milestone is actually worked in.

---

## Schema deltas (`backend/app/models.py`)

**`User` — three new columns** (M10), same class as `email_verified_at` (M8): a timestamped status, not a bare bool, because the state machine has four values, not two.

| Column | Type | Note |
|---|---|---|
| `verification_status` | `str`, default `"unverified"` | `unverified \| pending \| verified \| rejected` — the state machine (spec D1). Server-controlled; never accepted from `ProfileUpdate` or any client body (S1). |
| `verification_reviewed_at` | `datetime \| None` | Stamped on every admin decision (approve/reject/revoke); `None` while `unverified`/`pending`. |
| `verification_reason` | `str \| None` | The **current** decision's reason (rejection or revocation note). Overwritten on each admin decision — this is exactly the value `BuyerVerificationEvent` exists to preserve historically (D6). |

**`BuyerVerificationDocument`** — a buyer's uploaded proof-of-funds file (D5). Same shape as `ListingDocument`, keyed by `user_id` instead of `listing_id`:

| Column | Type | Note |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK `user.id`, indexed | **Server-derived** from the JWT — never from the body. |
| `storage_key` | str | Returned by `StorageBackend.save(user.id, data, suffix)` — `user.id` passed into the same positional slot M2 passes `listing_id` into (D5); the interface is agnostic to which entity "owns" the key. |
| `original_filename` | str | Display only — never used to build a path (M2's rule, reused verbatim). |
| `content_type` | str | One of the M2 whitelist (`ALLOWED_UPLOAD_TYPES`). |
| `size_bytes` | int | |
| `uploaded_at` | datetime | |

**`BuyerVerificationEvent`** — audit row, justified per constitution Article 2 #5 (spec D6). Shape mirrors `listingevent`:

| Column | Type | Note |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK `user.id`, indexed | The buyer whose status changed. |
| `actor_id` | FK `user.id` | The admin who acted (buyer's own upload is not audited here — the document row is its own record of that event; only admin *decisions* need a history, since only decisions overwrite `verification_reason`). |
| `action` | str | `"approved" \| "rejected"` |
| `from_status` | str | `pending \| verified` (the only two legal `from_status` values for a decision, per D1/X4) |
| `to_status` | str | `verified \| rejected` |
| `reason` | `str \| None` | Copied at write time — this is what the row preserves that `User.verification_reason` alone would lose on the next decision. |
| `created_at` | datetime | |

**`Listing` upload quota — no schema change**, a config + query-time check only (D8): `max_documents_per_owner` and `max_total_upload_bytes_per_owner` in `config.py`, checked by counting/summing existing rows before insert on both `ListingDocument` (retrofit) and `BuyerVerificationDocument` (new).

**New `config.py` settings** (three, all with the `Settings` class's existing style — a literal default plus a comment naming what it bounds):

| Setting | Default | Bounds |
|---|---|---|
| `max_documents_per_owner` | `20` | Document *count* per owning entity — per listing for `ListingDocument`, per user for `BuyerVerificationDocument`. Deliberately generous (D11): a DoS control, not a workflow limit. |
| `max_total_upload_bytes_per_owner` | `50 * 1024 * 1024` (50 MB) | Cumulative stored bytes per owning entity. Complements the existing per-file `max_upload_bytes` (10 MB), which a 20-file owner could otherwise multiply by 20. |
| `verification_reason_max_chars` | `1000` | The admin-authored rejection reason (X6) — free text that is stored *and echoed to the buyer*, so it is capped at the boundary like `offer_contingencies_max_chars`. |

## Endpoints

| Method + path | Permission gate | Effect |
|---|---|---|
| `POST /api/verification/documents` | `get_current_user` (D4 — no role gate) | Validates file (M2 rules, D5) + quota (D8); creates `BuyerVerificationDocument`; sets `verification_status` to `pending` from `unverified`/`rejected`; 409 if currently `verified` (D3); writes no event row for the upload itself (D6's `actor_id` note) |
| `GET /api/verification` | `get_current_user` | Caller's own `verification_status`, `verification_reviewed_at`, `verification_reason`, document metadata list (S9 — no `storage_key`) |
| `GET /api/verification/documents/{document_id}` | **`get_owned_or_admin_verification_document`** | Streams the file bytes + `content_type`; 404 for not-owner-and-not-admin (S4, matching spec 002's 404-for-not-yours choice). **Reuses M2 `download_document`'s response hardening verbatim** (S10): `Content-Disposition: attachment` with the name run through `os.path.basename` + quote/CR/LF strip + 200-char cap. D5's "narrower reuse of the same seam" covers *serving* as well as *storing* — a `.pdf`-suffixed filename can carry `"`/CRLF past the extension whitelist, so the header is an injection surface, and `attachment` is what keeps a buyer-supplied file from rendering same-origin. Worth factoring the four sanitizing lines out of `listings.py` into one helper rather than copying them, so the two routes cannot drift. |
| `GET /api/admin/verifications` | `require_admin` | Queue of submissions (default: `pending`; V3) with buyer profile fields + document metadata |
| `POST /api/admin/verifications/{user_id}/approve` | `require_admin` | `pending → verified`; 409 from any other `from_status` (X3); writes `BuyerVerificationEvent` |
| `POST /api/admin/verifications/{user_id}/reject` | `require_admin` | `{pending, verified} → rejected` (D1 — doubles as deny and revoke); `reason` required and length-capped via a `VerificationRejectRequest` body model — `reason: str = Field(min_length=1, max_length=settings.verification_reason_max_chars)`, so absent → 422 (X2) and over-long → 422 (X6); 409 from `unverified`/`rejected` (X4); writes `BuyerVerificationEvent`. The model carries **only** `reason`, so `{"reason": "x", "to_status": "verified"}` has no field to assign from — the same structural control S1 pins on the profile route |
| `POST /api/listings/{id}/documents` *(existing M2 route, modified)* | `get_owned_listing` *(unchanged)* | **Adds** the D8 quota check ahead of the existing content-type/size checks; no other behavior change |

No route accepts `verification_status`, `verification_reviewed_at`, or `verification_reason` as request-body fields anywhere — the only bodies in this milestone are the upload's `UploadFile` and the reject endpoint's `{reason: str}`. Mass-assignment of the status fields is impossible by schema, the same class of control `ListingCreate`/`ListingUpdate` already use for `status`/`owner_id`.

## Permission gates (`backend/app/permissions.py`)

**`get_owned_or_admin_verification_document`** — new dependency:

```python
def get_owned_or_admin_verification_document(
    document_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BuyerVerificationDocument:
    """Trust boundary: may this caller see this proof-of-funds file? (M10, spec S4/S5)

    Two legitimate viewers — the uploader and an admin reviewing it — everyone
    else gets the same 404 a nonexistent document would, so the route is not
    an existence oracle (mirrors get_owned_listing's document-download shape
    from M2, and spec 002's "404 over 403" choice for owner-scoped routes).
    """
    doc = session.get(BuyerVerificationDocument, document_id)
    if doc is None:
        raise NotFound("Document not found")
    if doc.user_id != user.id and not user.is_admin:
        raise NotFound("Document not found")
    return doc
```

No new gate for `POST /verification/documents` or `GET /verification` — both operate on the caller's own row(s) via `user.id` from `get_current_user`, the same pattern `PUT /profile` already uses. `require_admin` (existing, M3) covers the three admin routes unchanged — it re-reads `is_admin` from the DB per request, so a role change after token issuance is honored immediately (the property that makes S2/S3 airtight, not just tested).

## Frontend (`app/src/`)

- **`app/src/stores/verificationStore.ts`** — MobX store: `status`, `reason`, `documents`, `loading`, `error`; `upload(file)` calls `POST /verification/documents` and refetches; mirrors `listingStore`'s upload-then-refetch shape from M2.
- **`app/src/components/VerificationStatus.tsx`** — the buyer's own status page: empty/loading/error triad, current badge (`unverified`/`pending`/`verified`/`rejected` with the reason shown for `rejected`), an upload form gated on `status !== "verified"` (mirrors D3's server-side 409 — the button is simply hidden/disabled when already verified, not just left to fail).
- **`app/src/components/VerifiedBadge.tsx`** — a small chip, added wherever `BuyerProfile` is rendered — today that is `AccessRequestQueue.tsx` / `PersonRow.tsx` (M5) — completing FR-14's promise in the UI, not just the API.
- **`app/src/components/AdminVerificationQueue.tsx`** — mirrors `AdminQueue.tsx` (M3's curation queue): list of pending submissions, buyer profile fields, document links (via the gated download route), approve/reject actions (reject opens a reason field, same pattern M3's reject-with-reason form already established).
- **`App.tsx`** — new routes `/verification` (`RequireAuth`) and `/admin/verifications` (`RequireAdmin`, mirroring `/admin/listings`).
- **`NavBar.tsx`** — one new link, "Verification," alongside the profile/watchlist links; the admin nav gains "Verifications" alongside "Curation queue."

The route guards are UX only, per the project's standing pattern — `get_current_user`/`require_admin`/`get_owned_or_admin_verification_document` are the real boundary.

## Response models (`backend/app/schemas.py`)

**`VerificationRead`** — returned by `GET /verification`:

```python
class VerificationDocumentRead(SQLModel):
    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    # No storage_key (S9) — internal, never exposed.

class VerificationRead(SQLModel):
    verification_status: str
    verification_reviewed_at: datetime | None
    verification_reason: str | None
    documents: list[VerificationDocumentRead]
```

**`AdminVerificationQueueRead`** — returned by `GET /admin/verifications` (admin-only, so email is fine here — the same reasoning `AdminListingRead` (M3) already applies to seller identity):

```python
class AdminVerificationQueueRead(SQLModel):
    user_id: int
    email: str
    display_name: str | None
    budget: Decimal | None
    target_industries: str | None
    experience: str | None
    verification_status: str
    documents: list[VerificationDocumentRead]

    # Money serializes as an exact string, never a float — the same
    # `field_serializer` BuyerProfile._ser_budget and ListingRead._ser_money
    # already apply. Called out because the first draft of this model omitted it,
    # which left V3 unable to know whether to expect "250000.00" or 250000.0.
    @field_serializer("budget", when_used="json")
    def _ser_budget(self, value: Decimal | None) -> str | None:
        return None if value is None else str(value)
```

**`UserRead`** (existing, M1) — two additions, mirroring the `email_verified_at` → `email_verified` pattern exactly:

```python
    verification_status: str
    verification_reviewed_at: datetime | None

    @computed_field
    @property
    def verified(self) -> bool:
        return self.verification_status == "verified"
```

**`BuyerProfile`** (existing, M5) — same two additions. Its docstring's "No verification field either (spec 005 D5) ... M10 owns surfacing the badge here" is retired by this change — the field now exists, is server-derived, and is the direct completion of FR-14.

**No public model gains these fields.** `ListingPublic`/`ListingRead` are unaffected; verification is a *person* attribute surfaced only on the caller's own profile (`UserRead`) and to a seller who already has a `BuyerProfile` view of that specific buyer (M5's access-request list) — never on any anonymous or cross-user surface.

## Errors (`docs/error_handling.md`)

| Raised | Status + code |
|---|---|
| `UnsupportedMediaType("Only PDF, PNG, or JPEG documents are allowed")` | 415 — reused verbatim from M2 (V10) |
| `PayloadTooLarge("File exceeds the maximum upload size")` | 413 `file_too_large` — reused verbatim from M2 (V11) |
| `PayloadTooLarge("Document quota exceeded")`, `code="upload_quota_exceeded"` | 413 — new, D8 (V12, V13), raised on both the verification route and the retrofitted M2 route |
| `Conflict("Already verified")`, `code="already_verified"` | 409 — `POST /verification/documents` while `status == "verified"` (D3, V7) |
| `InvalidTransition("Nothing pending to approve")` | 409 — `approve` from any `from_status != "pending"` (X3) |
| `InvalidTransition("Cannot reject from this status")` | 409 — `reject` from `unverified`/`rejected` (X4) |
| `NotFound("Document not found")` | 404 — via `get_owned_or_admin_verification_document` (S4) |
| `Forbidden(...)` | 403 — `require_admin` on all three admin routes for a non-admin caller (S2, S3) |

The 422 paths (X1: missing file part, X2: missing `reason`, X6: over-long `reason`) and the 500-safety path (X5) fall through to the handlers M1 already built — no new exception-handling code, only new tests, same as M9's routers. X6 needs no new error class either: the cap is a `Field(max_length=…)` on the request model, so Pydantic produces the 422.

## Analytics events

**None planned.** No acceptance criterion requires one, and the standing rule (reaffirmed at M8/M9) is to emit nothing untested. If a future milestone wants `verification_submitted`/`verification_decided` events, props are limited to `{user_id, status}` (data_protection.md §2) — not part of this milestone.

## Data protection (`docs/data_protection.md`)

- **New PII: the proof-of-funds document itself is this milestone's most sensitive artifact.** Held by us, not a vendor, for MVP — an explicit, recorded deviation from §4's "vendor holds the document" ideal (spec D9), because F11 ships **manual** review with no vendor to hand it to. Mitigated: same permission-gated, never-statically-served path as M2 (§0's confidentiality half), admin-**or**-uploader access only, no server-side parsing of contents, and the *profile-facing* fields (`verification_status`, `verification_reviewed_at`) carry only the outcome, never the file — the one part of §4's letter honored regardless of the document-storage deviation.
- **New person-referencing tables — erasure behavior (D10):**
  - `BuyerVerificationDocument` — **cascades (hard-delete)** on user erasure: row deleted, underlying file deleted via `storage.delete(key)`. Matches §3's own example ("uploaded files → delete from `uploads/`") and carries no evidentiary value once its owner is gone.
  - `BuyerVerificationEvent` — **audit-exempt, kept.** Ids + status strings + reason text only, no document content, no free-text buyer PII beyond what an admin typed in a rejection reason (operational, not identity data) — anonymizing the referenced `user_id`/`actor_id` rows elsewhere does not need to touch these rows, per §3's "audit rows are immutable and exempt."
  - `User.verification_status`/`verification_reviewed_at`/`verification_reason` — ordinary columns on the already-erasure-ready `User` table (M1); anonymize in place with the rest of the row, no special handling needed.
- **`AdminVerificationQueueRead` includes `email`** — deliberately, admin-only surface (`require_admin`), same class as `AdminListingRead`'s existing seller-identity fields at M3; never on any buyer- or public-facing model.

## Build order

Five backend slices plus one frontend slice, each ending in one Conventional Commit. **No checkboxes and no status here by design** — the red test list is the status (`cd backend && pytest -q --lf`), and the red count is the progress bar.

1. **Schema (`User` columns, `BuyerVerificationDocument`, `BuyerVerificationEvent`) + `POST /api/verification/documents` + `GET /api/verification`.** → **V1, V2, V6, V7, V10, V11, S1, S7, X1, X5**. *First because nothing else in this milestone is reachable without the ability to create a submission and read it back — the same "add must exist before anything else can be exercised" reasoning as spec 009's slice 1. S1 lands here too: it only needs the new `verification_status` column and the existing `PUT /profile` route, no new endpoint. S7's path-confinement reuse and V10/V11's whitelist/size-cap reuse cost nothing new (D5) — they're regression pins on the M2 code path applied to a new caller.*
2. **Admin queue + approve/reject (`require_admin`, D1's transitions, `BuyerVerificationEvent` writes).** → **V3, V4, V5, V14, X2, X3, X4, X6, S2, S3, S8**. *Second because the state machine's only non-buyer-initiated transitions live here, and D1's "reject doubles as deny and revoke" can't be tested (V14) until both `pending→rejected` (V5) and `verified→rejected` (V14) are reachable from the same endpoint. S2/S3 fall out for free once the routes exist — the negative test is "the same route as V4/V5, called by the wrong identity."*
3. **`get_owned_or_admin_verification_document` + `GET /api/verification/documents/{id}`.** → **S4, S5, S9, S10**. *Depends on slice 1 for a document to fetch and slice 2 for an admin identity to test the "admin can view any" half (S5) meaningfully against a submission that has actually been queued. Kept separate from slice 1 because it is a distinct trust boundary (owner-or-admin, not just owner) — Article 2 #1's "one function per trust boundary" — not because of dependency order alone.*
4. **Badge surfacing: `UserRead` + `BuyerProfile` additions.** → **V8, V9, S11**. *Deliberately after the state machine (slices 1–2) is real — surfacing a field before the status it reflects can actually reach `verified`/`rejected` would make V8/V9 pass vacuously against a column that never changes value in the test. S11 (the badge is not stale after a revoke) belongs here and **only** works here: it needs both the field on `BuyerProfile` and slice 2's `verified → rejected` transition, which is why it is the one criterion in this milestone that no single slice could have carried alone. This slice also retires `BuyerProfile`'s "M10 owns this" docstring note left by spec 005 D5.*
   *Correction against the first draft of this Build order: **S8 moved to slice 2**, where it belongs — it asserts the field set of `GET /api/admin/verifications`, which that slice builds, and could never have gone green here. Recorded rather than silently edited, because M9's docs audit found exactly this class of drift (a slice→test mapping written predictively, before anything ran) and the fix that stuck was re-deriving the mapping from what the code actually does.*
5. **Upload quota (D8): shared config + check, applied to `POST /verification/documents` (new, from slice 1) and retrofitted onto `POST /listings/{id}/documents` (existing, M2).** → **V12, V13**. *Last among backend slices, deliberately: unlike slices 1–4, this one modifies already-shipped M2 code rather than only adding new surface. Sequencing it last means the new milestone's own routes are fully green first, so a regression the retrofit might cause in the M2 suite is isolated and easy to attribute to this specific commit rather than tangled with new-feature debugging.*
6. **Frontend** — `verificationStore.ts`, `VerificationStatus.tsx`, `VerifiedBadge.tsx`, `AdminVerificationQueue.tsx`, the two new routes, two nav links. *Last, per the project's standing order (spec 009's slice 4 precedent): the server gate is the boundary, the client is the view. No acceptance criteria above are frontend-specific, so this slice is scoped to "the six backend routes are reachable and usable," verified by the existing component-test conventions (empty/loading/error triad) rather than new numbered criteria.*

**Independent `appsec-engineer` pass** (constitution Article 3 §3, M10 is on the crown-jewel list) runs diff-scoped after slice 5, before the frontend slice's PR-readiness review — same placement the other crown-jewel milestones use, since the security surface (upload handling, the owner-or-admin gate, the quota retrofit touching M2) is entirely backend.

**If a slice reveals the order was wrong**, fix this section and say so in the commit — the plan is a design artifact, not a prophecy. Never reorder by weakening a test.
