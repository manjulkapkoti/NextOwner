# Plan 009 — M9: Watchlist

> Implementation plan for [`spec.md`](./spec.md). Schema, endpoints, gates, and — at the end — the **Build order**, the ordered slices the milestone is actually worked in.

---

## Schema deltas (`backend/app/models.py`)

**`WatchlistEntry`** — a buyer's (or any user's) favorited listing (M9, FR-12). Named as a row, not the collection, to avoid the ambiguity `SavedSearch`'s naming already resolved the same way.

| Column | Type | Note |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK `user.id`, indexed | **Server-derived** from the JWT — never from the body (there is no body). |
| `listing_id` | FK `listing.id`, indexed | The favorited listing. |
| `created_at` | datetime | `added_at` in API responses — see Response models. |

**Unique constraint on `(user_id, listing_id)`.** This is what makes D1's idempotent add safe under a race (two concurrent `POST`s from the same double-clicked heart icon): the app-level check-then-insert is the common path, and the constraint is the backstop — a caught `IntegrityError` on the insert is treated as "already present," exactly the D1 semantics, not a 409. Mirrors `Offer.uq_offer_one_active_per_pair`'s `sqlite_where`/`postgresql_where` shape used at M7/M8 where the constraint must survive the eventual Postgres swap; here it is a plain unique index (no partial-index condition needed — every row is "active," there's no soft-delete state on this table per D7).

No other columns. No `filters_json`-style blob, no per-user cap column (D6) — this is the simplest caller-owned artifact in the codebase.

## Endpoints

| Method + path | Permission gate | Effect |
|---|---|---|
| `POST /api/watchlist/{listing_id}` | `get_current_user` (plus the D2 live-listing check inline) | 201 on first add; 200 no-op if already present (D1). 404 if the listing is missing or not `live` (D2, applies to the owner too — W13). |
| `GET /api/watchlist` | `get_current_user` | Caller-scoped list, joined to `Listing` filtered to `status == "live"` (D3), newest-`added_at`-first. |
| `DELETE /api/watchlist/{listing_id}` | **`get_owned_watchlist_entry`** | 204. 404 if the caller never watchlisted that `listing_id` (W9) or it doesn't exist at all (W10) — same 404, no oracle. |

No route takes a request body. There is nothing to validate at 422 beyond the path parameter's type (X1) — deliberately the smallest possible attack surface (S4).

## Permission gates (`backend/app/permissions.py`)

**`get_owned_watchlist_entry`** — new dependency, keyed on `listing_id` (D5), not the entry's own surrogate id:

```python
def get_owned_watchlist_entry(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WatchlistEntry:
    """Trust boundary: is this listing on the caller's own watchlist? (M9, spec W9/W10)

    Keyed on listing_id, not the row's own id — mirrors get_owned_saved_search's
    404-for-both shape (missing entirely vs. exists but isn't the caller's),
    for the same reason: a watchlist entry is a private artifact of one account,
    so the two cases must be indistinguishable.
    """
    entry = session.exec(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == user.id,
            WatchlistEntry.listing_id == listing_id,
        )
    ).first()
    if entry is None:
        raise NotFound("Watchlist entry not found")
    return entry
```

`POST`'s D2 existence/liveness check is **not** expressed as a `Depends` gate — it reuses `get_public_listing`'s inline `if listing is None or listing.status != "live": raise NotFound(...)` check directly (same message, same reasoning), since favoriting isn't scoped to an *owned* resource the way delete is; it's scoped to a *visible* one. This keeps the "what may I see" boundary (public visibility) and the "what may I touch" boundary (my own entry) as two distinct, named checks rather than folding both into one dependency that would blur which question it's answering.

## Frontend (`app/src/`)

Mirrors M8's saved-searches shape (a store + a list page), plus one small addition other milestones didn't need — a toggle affordance on the listing surfaces themselves:

- **`app/src/stores/watchlistStore.ts`** — MobX store: `entries`, `loading`, `error`; `add(listingId)` / `remove(listingId)` call the two endpoints and update `entries` optimistically-then-reconciled (mirrors `accessStore.ts`'s shape); `isWatchlisted(listingId)` for the toggle button's state.
- **`app/src/components/Watchlist.tsx`** — the list page (mirrors `SavedSearches.tsx`): empty/loading/error triad (`error_handling.md` §3), each row rendering the same public fields `ListingCard` already renders, with an un-favorite action.
- **`app/src/components/WatchlistButton.tsx`** — a small heart-icon toggle, added to `ListingCard.tsx` and `ListingDetail.tsx`. Calls `watchlistStore.add`/`remove`; a 404 on `remove` (W9's shape — already-removed) is treated as success rather than shown as an error, since D1/the toggle framing means the user-visible state ("not favorited") is already correct.
- **`App.tsx`** — new route `/watchlist`, wrapped in `RequireAuth`, `Container maxWidth="md"`, same shape as the existing `/saved-searches` route.
- **`NavBar.tsx`** — one new nav link, "Watchlist," alongside the existing Saved searches / Notifications links.

The route guard is UX only, per the project's standing pattern — the server's `get_current_user` / `get_owned_watchlist_entry` are the real boundary.

## Response models (`backend/app/schemas.py`)

**`WatchlistEntryRead`** — returned by both `POST` (the created or already-existing entry) and `GET` (a list of these). Deliberately a **standalone model**, not built by inheriting from `ListingPublic` or `ListingRead` — same reasoning `ListingPublic`'s own docstring gives for not subclassing `ListingRead`: inheritance would silently join a private field added to one model onto this one. The duplication is the control.

```python
class WatchlistEntryRead(SQLModel):
    listing_id: int
    added_at: datetime
    type: str
    headline: str
    description: str
    asking_price: Decimal
    ttm_revenue: Decimal
    ttm_profit: Decimal
    mrr: Decimal
    churn_pct: Decimal
    customers: int
    published_at: datetime | None = None
```

Absent by construction, same list `ListingPublic` excludes: `owner_id`, `status`, `company_name`, `website_url`, `detailed_financials` (W11 asserts this directly). `status` is excluded for the same reason `ListingPublic` excludes it — every row returned is already known-`live` by construction of the `GET /watchlist` query (D3), so the field would again be a telling-nothing constant.

## Errors (`docs/error_handling.md`)

| Raised | Status + code |
|---|---|
| `NotFound("Listing not found")` | 404 — `POST` on a missing/non-`live` `listing_id` (D2, W5, W6, W13) |
| `NotFound("Watchlist entry not found")` | 404 — `DELETE` on a `listing_id` the caller never watchlisted (W9, W10), via `get_owned_watchlist_entry` |
| *(none — 200/201 both)* | `POST` on an already-watchlisted `listing_id` (D1, W4) is a success path, not an error |

No `Conflict`/409 anywhere in this router (spec § X's explicit note — no state machine to violate). The 422 path (X1) and the 500-safety path (X2) both fall through to the handlers M1 already built; no new exception-handling code, only new tests.

## Analytics events

**None planned.** No acceptance criterion in spec.md requires one, and the codebase's standing rule (M4, reaffirmed at M8) is to emit nothing untested rather than ship an unverified side channel. If a future milestone adds `watchlist_added` / `watchlist_removed` events, props must be limited to `{listing_id}` — never the caller's identity (`docs/data_protection.md` §2) — but that is not part of this milestone.

## Data protection (`docs/data_protection.md`)

- **No new PII fields.** `WatchlistEntry` holds two foreign-key integers and a timestamp — nothing to anonymize in-place even if the cascade choice below were reconsidered.
- **One new person-referencing table; cascades on erasure (D7).** Same class as `SavedSearch` and unlike `Offer`/`AccessRequest`: a watchlist entry is a convenience with no evidentiary value, so on user erasure the row is hard-deleted rather than anonymized-and-kept. The question `data_protection.md` §3 asks per child table — "does erasure cascade or anonymize" — is answered by whether the row is evidence; it isn't.
- Public `response_model` (`WatchlistEntryRead`) excludes identity and private fields by schema (W11).

## Build order

Three backend slices plus one frontend slice, each ending in one Conventional Commit. **No checkboxes and no status here by design** — the red test list is the status (`cd backend && pytest -q --lf`), and the red count is the progress bar.

1. **`WatchlistEntry` model + `POST /api/watchlist/{listing_id}`.** → **W1, W4, W5, W6, W12, W13**, the `POST`-half of **S3**, **S4**, the `POST`-half of **X1**. *First because add is the only write that creates rows — nothing else can be exercised without it. The unique constraint and the idempotent-insert logic land here, so W4's race-safety claim is testable from this slice on.*
2. **`GET /api/watchlist`** (caller-scoped, joined to `live` listings only). → **W3, W7, W8, W11**, **S1**, the `GET`-half of **S3**. *Depends on slice 1 for data to list. W7/W8's leave-and-return-to-live behavior is the first test that needs two listing-status transitions inside one test, so it comes with its own slice rather than riding along with add.*
3. **`get_owned_watchlist_entry` + `DELETE /api/watchlist/{listing_id}`.** → **W2, W9, W10**, **S2**, the `DELETE`-half of **S3**, the `DELETE`-half of **X1**, **X2**. *Last of the backend trust boundaries — delete is the one place a second user's row must provably survive an attacker's call (S2), which needs both add (slice 1) and list (slice 2) already in place to seed and verify against.*
4. **Frontend** — `watchlistStore.ts`, `Watchlist.tsx`, `WatchlistButton.tsx` wired into `ListingCard`/`ListingDetail`, the `/watchlist` route and nav link. *Last, per the project's standing order: the server gate is the boundary, the client is the view. No acceptance criteria in spec.md are frontend-specific (unlike M8's J-group), so this slice is scoped to "the three backend routes are reachable and usable," verified by the existing component-test conventions (empty/loading/error triad) rather than new numbered criteria.*

**If a slice reveals the order was wrong**, fix this section and say so in the commit — the plan is a design artifact, not a prophecy. Never reorder by weakening a test.
