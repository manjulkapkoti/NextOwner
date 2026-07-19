# Plan 005 — Platform NDA + access gate ⭐

Implementation plan for `spec.md`. Backend-first: the gate exists and is proven by tests
before any UI can depend on it.

## Schema deltas (`backend/app/models.py`)

**`User`** — two columns, both retained legal record (same class as `tos_accepted_at`):

| Column | Type | Notes |
|---|---|---|
| `nda_signed_at` | `datetime \| None` | Stamped once. Never re-stamped (A2). |
| `nda_version` | `str \| None` | Frozen at signature from server config (D4). |

**`AccessRequest`** — new table, the per-listing trust record:

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `listing_id` | FK `listing.id`, indexed | |
| `buyer_id` | FK `user.id`, indexed | **From the JWT, never the body** (B4). |
| `status` | `str`, default `"requested"` | State machine — `requested → approved\|denied`, `approved → revoked`. |
| `created_at` | `datetime` | |
| `decided_at` | `datetime \| None` | Server-stamped on any decision. |
| `decided_by_id` | FK `user.id`, nullable | The deciding seller — audit. |

**Unique constraint on `(listing_id, buyer_id)`** — FR-13's "one per buyer-listing pair", and
what makes B3's 409 a database guarantee rather than a check someone can forget. Declared via
`__table_args__ = (UniqueConstraint(...),)`.

*Erasure note (`data_protection.md`):* `AccessRequest` references a person but stores no PII
of its own — anonymizing a `User` in place leaves these rows intact and meaningless, which is
the intended behaviour. No new PII field is introduced by this milestone.

**Config** (`backend/app/config.py`): `nda_version: str = "1.0"` — server-owned, so the client
can never influence what was signed.

## Endpoints

| Method + path | Permission dependency | Transition |
|---|---|---|
| `POST /api/auth/nda` | `get_current_user` | stamps `nda_signed_at` if null (idempotent) |
| `POST /api/listings/{id}/access-request` | `get_current_user` + `require_signed_nda` | — → `requested` |
| `POST /api/access-requests/{id}/approve` | `require_request_decider` | `requested` → `approved` |
| `POST /api/access-requests/{id}/deny` | `require_request_decider` | `requested` → `denied` |
| `POST /api/access-requests/{id}/revoke` | `require_request_decider` | `approved` → `revoked` |
| `GET /api/listings/{id}/private` | **`require_private_access`** ⭐ | — |
| `GET /api/listings/{id}/documents/{doc_id}` | **`require_private_access`** (was `get_owned_listing`) | — |
| `GET /api/my/access-requests` | `get_current_user` (caller-scoped) | — |
| `GET /api/access-requests?listing_id=` | `get_owned_listing` via the query param | — |

## Permission gates (`backend/app/permissions.py`)

Three new functions — **one per trust boundary**, matching the file's existing shape:

- **`require_signed_nda`** — "has this user signed the platform NDA?" → 403 `nda_not_signed`.
  Separate from `require_private_access` on purpose: the signature is a *property of the user*,
  the approval is a *property of the pair*. Fusing them would make B2 and D3 the same code path
  and one bug would take out both.
- **`require_request_decider`** — "may this caller decide this request?" Loads the request,
  loads **its** listing, and compares `listing.owner_id` to the caller (S1 — the IDOR fix is
  that the row is authorized through its listing, not fetched by id). Admin is **not**
  special-cased (C8).
- **`require_private_access`** ⭐ — **the gate.** Resolution order matters and is itself the
  security property:
  1. Listing missing → 404.
  2. Caller is the owner → allow (D1).
  3. An `approved` request for `(listing, caller)` → allow (D2, D9 — listing status is *not*
     consulted here, so approval survives pause/close).
  4. Otherwise: `published_at is null` → **404** (D8, never-published stays secret);
     else **403** `nda_access_required` (D3–D6).

  Steps 3 and 4 are the whole milestone. Everything else in this plan exists to give them
  something to check.

## Response models (`backend/app/schemas.py`)

- **`ListingPrivateRead`** — `company_name`, `website_url`, `detailed_financials`. Standalone,
  **not** a subclass of `ListingRead` (the M4 lesson: a standalone model means a field added to
  the owner's view cannot silently join a gated one — spec 004 D2).
- **`AccessRequestRead`** — id, listing_id, status, created_at, decided_at. **No buyer email**
  (S3).
- **`AccessRequestWithBuyer`** — the seller's queue: the above plus a nested buyer **profile**
  (display name, budget, target industries, experience, verification status) and explicitly
  **not** email (G3). Verification status is a placeholder field until M10 fills it.
- `ListingPublic` (M4) is **unchanged** — S4 asserts M5 did not widen it.

## Errors (`backend/app/errors.py` — existing classes, new codes)

| Raised | Class | `code` |
|---|---|---|
| NDA not signed | `Forbidden` | `nda_not_signed` |
| Gate denies | `Forbidden` | `nda_access_required` *(already named in `error_handling.md` §7)* |
| Duplicate request | `Conflict` | `access_request_exists` |
| Illegal decision | `InvalidTransition` | `invalid_access_transition` |

No new `AppError` subclass is needed — the existing ones cover every path, which is the sign
the error contract was designed right at M1.

## Frontend (`app/src/`)

- **`NdaModal.tsx`** — click-wrap: the NDA text, a checkbox, a confirm button. Signing and
  requesting are **one user action** (J1) even though they are two API calls.
- **`RequestAccessPanel.tsx`** — the four states on listing detail: locked / pending / approved
  / denied, driven by the gate's machine code rather than by guessing (J2, J3, X4).
- **`PrivateSection.tsx`** — renders `ListingPrivateRead` + the document list once unlocked.
- **`AccessRequestQueue.tsx`** — the seller's list with profile + approve/deny/revoke (J4).
- **`accessStore.ts`** (MobX) — request state; must **not** treat a 403 as a global-401 (J5).
- Routes: `/listings/:id` gains the private section; `/my-listings/:id/requests` for the queue.

## Analytics events

**None.** There is still no `track()` wrapper in the codebase (`progress.md` § M4 carryover),
and this is the *last* milestone on which to introduce an untested side channel — an analytics
call in the gate is a path where a private field can leave the building. When `track()` lands,
its first test is that it rejects private fields.

## Data protection

No new PII. `AccessRequest` is person-referencing but PII-free (see § Schema deltas). The
seller's queue deliberately exposes a **profile, not contact details** (G3) — the seller learns
enough to decide and nothing more, which is the same minimization principle the public/private
split applies to listings.

---

## Build order

Ordered slices — **one trust boundary each**, each turning a named cluster of red tests green,
each one commit. No checkboxes: the red test list is the status (`pytest -q --lf`).

1. **Schema + config.** `AccessRequest`, the two `User` columns, the unique constraint,
   `nda_version` in config. *First because every other slice writes or reads this table.*
   Turns green: the model/constraint tests only.

2. **NDA signing** — `POST /api/auth/nda`. *Before access requests, because requesting checks
   the signature; building it the other way means B2 has nothing to assert against.*
   → **A1–A4**.

3. **Access-request creation** + `require_signed_nda`. *The first trust boundary of the
   milestone, and the one that creates the rows everything downstream decides on.*
   → **B1–B7**.

4. **Seller decisions** + `require_request_decider` — approve / deny / revoke. *Before the
   gate, because the gate reads the terminal state this slice produces; without it, D2–D5
   could only be tested by writing rows directly, which would test the fixture rather than the
   product.*
   → **C1–C8, S1, S5, X1, X2**.

5. **`require_private_access` + `GET /api/listings/{id}/private`** ⭐ *The milestone. Everything
   above exists to make this checkable.*
   → **D1–D10, S2, S6, S7, S8, X3**.

6. **Re-gate document downloads** — swap `get_owned_listing` for `require_private_access` on
   the download route. *A separate slice from #5 on purpose: it proves the gate is **one
   function reused**, not a second implementation. If this slice needs new logic, the gate was
   built wrong.* Watch M2's `test_listing_download.py` — both its tests must still pass
   **unedited** (E5).
   → **E1–E5**.

7. **The two list endpoints** — buyer's `/api/my/access-requests`, seller's queue with the
   buyer profile. *Read-only and lowest-risk, so they come after the writes are proven; the
   seller's queue also needs the profile shape settled by then.*
   → **F1–F3, G1–G3, S3, S4**.

8. **Frontend** — modal, panel, private section, seller queue, store. *Last, because a UI built
   against a gate that is still moving gets rebuilt.*
   → **J1–J5, X4**.

*If a slice reveals this order was wrong, fix the order here and say so in the commit — the
plan is a design artifact, not a prophecy. Never reorder by weakening a test.*
