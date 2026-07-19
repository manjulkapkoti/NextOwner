# Plan 003 — M3: Admin curation

Implementation plan for `spec.md`. Schema, endpoints, components, and the **Build order**.

---

## Schema delta

### New: `listing_event` (append-only audit)

*Physical table name is `listingevent`* — SQLModel's default, matching the existing `listingdocument` and `listingprivate`. `listing_event` is how the docs and the fold-in refer to it; one naming convention per database beats a readable exception.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `listing_id` | int FK → `listing.id`, indexed | |
| `actor_id` | int FK → `user.id` | **server-derived from the JWT**, never from the body |
| `action` | str | `approved` \| `rejected` (extended by M12 for `sold` / `fell_through`) |
| `from_status` | str | what it was — makes the row self-contained without replaying history |
| `to_status` | str | what it became |
| `reason` | str \| None | required for `rejected`, absent for `approved` |
| `created_at` | datetime | server clock |

**Append-only by discipline, not by constraint** — nothing in the codebase updates or deletes a row, and D4 asserts both rows survive a second decision. SQLite gives no cheap enforcement; Postgres later can add a trigger if it earns it.

### Changed: `Listing`

No new columns. `published_at` already exists and was always documented as *"set by admin at M3"* — this is the milestone that sets it.

**The rejection reason is not duplicated onto `Listing`.** It lives on the event row, and the owner's read derives the latest one. One home per fact — a `listing.rejection_reason` column would be a second copy that goes stale the moment a listing is rejected twice.

---

## Endpoints

| Method | Path | Guard | Transition |
|---|---|---|---|
| `GET` | `/api/admin/listings` | `require_admin` | — (optional `?status=` filter) |
| `POST` | `/api/listings/{id}/approve` | `require_admin` | `pending_review` → `live`, stamps `published_at` |
| `POST` | `/api/listings/{id}/reject` | `require_admin` | `pending_review` → `rejected`, requires `reason` |

Both transitions reuse the existing `_transition()` helper in `routers/listings.py`, which already raises `InvalidTransition` (409) — the state machine stays in one place rather than growing a second implementation in an admin router.

**Schemas:** `RejectRequest { reason: str = Field(min_length=1, max_length=1000) }`; `AdminListingRead` (queue rows, includes private company detail per A5); `ListingEventRead` for the owner's rejection reason.

---

## Components

- **`app/src/components/AdminQueue.tsx`** — the queue table, approve/reject actions, reject-reason dialog.
- **`app/src/App.tsx`** — an `/admin` route behind a `RequireAdmin` guard.
- **`app/src/components/RequireAdmin.tsx`** — mirrors `RequireAuth`, additionally checking `is_admin`. Client-side gate is UX only; A3 is the boundary.
- **`StatusChip`** is reused as-is — this is the milestone it was built one milestone early for.

---

## Build order

Each slice is **one trust boundary**, turns a named cluster of red tests green, and ends in one commit.

**1 — `listing_event` model + the audit writer.**
The table, plus a single `record_event()` helper that every transition calls. No endpoint yet. Turns green: D1's structure (asserted via a direct call), nothing else.
*Trust boundary: none — this is the substrate the rest is audited by, and it goes first so no endpoint can be written without a way to log it.*

**2 — `GET /api/admin/listings` behind `require_admin`.**
The read boundary, and the cheapest place to prove `require_admin` works before any state can change.
Turns green: **A1–A5**.

**3 — `POST /listings/{id}/approve`.**
The write boundary that matters most. Reuses `_transition()`; stamps `published_at`; writes the audit row.
Turns green: **B1–B5, D1, D3**.

**4 — `POST /listings/{id}/reject`.**
Same boundary, plus untrusted input (`reason`) validated at the edge.
Turns green: **C1–C5, D2, D4**.

**5 — The owner sees the reason.**
Derive the latest rejection reason on the owner's listing read.
Turns green: **C6**.

**6 — Seal the seller paths.**
Assert no seller-reachable route sets `live`. Expected to be green already from M2's design — if any of these fail, that is a live vulnerability and the slice becomes a fix, not a test.
Turns green: **E1–E4**.

**7 — Admin UI.**
`/admin` route, `RequireAdmin`, the queue, the reject dialog.
Turns green: **F1–F3**.

*Slice 6 sits after the endpoints deliberately: E3 asserts approve-as-owner → 403, which cannot be tested until approve exists.*

---

## Notes for the build

- **`require_admin` already exists** (`permissions.py`) and already re-reads from the DB. This milestone is its first real consumer — verify that property rather than assuming it.
- **No new transition logic.** If a slice wants to write `listing.status = ...` outside `_transition()`, stop: that is the state machine leaking out of its one home.
- **The reason is rendered to a seller.** React escapes by default; do not reach for `dangerouslySetInnerHTML`.
- **New CI gates now apply**: every criterion above must be cited by a test (`scripts/check_spec_coverage.py`), and the admin UI must pass the axe and layout specs.

## Finding from the M3 inline review — deferred, not fixed here

`update_listing` (`routers/listings.py`, the "editing a live listing sends it back through curation" line) writes `listing.status` **directly, outside `_transition()`** — the exact thing this plan's own note forbids. It is pre-existing M2 code, and it is **safe in direction**: it can only move a listing *away* from `live`, never toward it, so it is not a path to self-publishing and not a blocker for M3.

It matters now for a reason it did not before: an audit trail exists as of this milestone, and this transition leaves no row in it. A seller can take a listing out of the public marketplace and nothing records that it happened.

**Not fixed in M3** — routing it through `_transition()` means reconciling that helper's commit with `update_listing`'s own, which is real surgery on M2's edit path and outside this milestone's scope. **Recommended for the next milestone that touches the seller lifecycle**, together with the decision about whether seller-driven transitions should be audited at all (M3 deliberately audits only curation decisions).

## Fast-follow from the security review (non-blocking)

**`GET /api/admin/listings` has no pagination or cap.** Acceptable now — the route is `require_admin`-gated so it is not reachable by an untrusted party, and volume is trivial before M4's seed data. **Add a limit/offset or a hard ceiling when M4's ~30 seeded listings land**, which is the first point the queue could return a meaningful number of rows.

**No test asserts a non-admin can never receive an `AdminListingRead`-shaped body.** Implicitly covered — `test_a3`/`test_a4` return 403/401 before serialization ever happens — but if this "admin sees private data" pattern is repeated before M5, it deserves an explicit schema-leak test of its own.
