# Plan 002 — Seller Listing Builder + Uploads (M2)

> The *how* for [`spec.md`](./spec.md). Schema, endpoints, gates, and the **Build order**.

---

## Schema deltas

`backend/app/models.py` — three new tables. Money is **`Decimal`** (fold-in; supersedes the `float` in design_implementation §3.5).

```python
class Listing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)     # from JWT, never the client
    status: str = Field(default="draft", index=True)             # state machine (below)
    # public / anonymous — safe to show anyone (served at M4)
    type: str
    headline: str
    description: str
    asking_price: Decimal = Field(max_digits=14, decimal_places=2)
    ttm_revenue: Decimal = Field(max_digits=14, decimal_places=2)
    ttm_profit: Decimal = Field(max_digits=14, decimal_places=2)
    mrr: Decimal = Field(max_digits=14, decimal_places=2)
    churn_pct: Decimal = Field(max_digits=6, decimal_places=2)
    customers: int
    created_at: datetime = Field(default_factory=_utcnow)
    published_at: datetime | None = None                          # set by admin at M3

class ListingPrivate(SQLModel, table=True):        # owner-only in M2; NDA-gated at M5
    listing_id: int = Field(foreign_key="listing.id", primary_key=True)
    company_name: str
    website_url: str
    detailed_financials: str | None = None          # JSON string

class ListingDocument(SQLModel, table=True):        # refines the §3.5 document_paths JSON blob
    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    storage_key: str                                # opaque key from the storage port
    original_filename: str                          # display only — NEVER used to build a path
    content_type: str
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=_utcnow)
```

**Status state machine (M2 owns these transitions; all others 409):**
`draft → pending_review` (submit) · `live → pending_review` (edit — anti-bait-and-switch) · `live → paused` (pause) · `paused → live` (resume) · `{draft|pending_review|live|paused} → closed` (close). `live`/`rejected` are admin (M3); `under_offer`/`sold` are M7/M12.

## Endpoints

| Method + path | Gate | Transition / note |
|---|---|---|
| `POST /api/listings` | `get_current_user` | create draft; `owner_id`+`status` server-set |
| `GET /api/my/listings` | `get_current_user` | caller's listings only |
| `GET /api/listings/{id}` | `get_owned_listing` | owner views own full listing (public+private) |
| `PUT /api/listings/{id}` | `get_owned_listing` | edit; `live → pending_review` |
| `POST /api/listings/{id}/submit` | `get_owned_listing` | `draft → pending_review` |
| `POST /api/listings/{id}/pause` \| `/resume` \| `/close` | `get_owned_listing` | lifecycle |
| `POST /api/listings/{id}/documents` | `get_owned_listing` | multipart upload (owner-only) |
| `GET /api/listings/{id}/documents/{doc_id}` | `get_owned_listing` | download; `attachment` (M5 adds buyer access) |

## Permission gates

`backend/app/permissions.py` — **new trust boundary**:
- **`get_owned_listing(listing_id, user, session) -> Listing`** — loads the listing; raises **`NotFound` (404)** if it doesn't exist **or** isn't owned by `user`. One function, both cases indistinguishable (no existence leak). Every `{id}` route in M2 depends on it.

## Storage port (horizontal-scale blocker #2)

`backend/app/storage.py` (new):
- **`StorageBackend`** Protocol: `save(listing_id: int, data: bytes, suffix: str) -> str` (returns an opaque key), `open(key: str) -> bytes`, `delete(key: str)`.
- **`LocalDiskStorageBackend`** — writes to `uploads/{listing_id}/{uuid4}{suffix}`. **Path confinement lives here:** resolve the final absolute path and assert it is inside the configured `uploads/` base (reject `..`, absolute, symlink escape). The routers never touch the filesystem or a client filename.
- Base dir + limits from `settings` (`upload_dir`, `max_upload_bytes`, allowed types).

## Response models

`schemas.py`: `ListingCreate` / `ListingUpdate` (public + private fields; **no** `owner_id`/`status`/`id` — mass-assignment impossible by schema), `ListingRead` (owner's full view), `ListingSummary` (dashboard rows), `DocumentRead`. *(The M4 public `ListingCard` — identity-stripped — is a later milestone; not here.)*

## Errors

`errors.py` gains `UnsupportedMediaType` (415, `unsupported_media_type`) and `PayloadTooLarge` (413, `file_too_large`); handlers already generic. `get_owned_listing` raises `NotFound`; transitions raise `InvalidTransition` (409).

## Frontend

`app/src/`: a MUI **Stepper** wizard (`ListingWizard`) — basics → metrics → story → documents → review — with per-step validation; a `listingStore` (MobX); a `MyListings` dashboard (status chips, empty state); an upload control surfacing 413/415. Money entered as strings, sent as-is (server parses `Decimal`).

## Analytics events

`track("listing_created", { type })` · `track("listing_submitted", {})` · `track("document_uploaded", { content_type })` — **no** company name, filenames, or financials.

## Data protection

`ListingPrivate`/`ListingDocument` are confidential business data (owner-only → M5-gated); files under `uploads/{listing_id}/`; the storage port's `delete` is the hook for the erasure/close delete path.

---

## Build order

**Ordered slices — one trust boundary each.** Each ends with its named tests green and one commit. **No checkboxes; the red test list is the status** (`pytest -q --lf`), the Build order is only the order. Suite is red mid-milestone by design.

| # | Slice | Turns green | Why here |
|---|---|---|---|
| 1 | **Models + settings** — `Listing`/`ListingPrivate`/`ListingDocument` (`Decimal`), upload settings, `.env.example` additions | A7 (Decimal round-trip) | Everything below needs the tables; the money-type test anchors slice 1 |
| 2 | **Storage port** — `StorageBackend` + `LocalDiskStorageBackend`, path confinement in the adapter | G1 | The upload slices depend on it; build the seam before the routes that use it |
| 3 | **`get_owned_listing` gate** + `POST /listings` (create draft) + `GET /my/listings` | A1–A6, F1, F2 | The trust boundary + the first write; `owner_id`/`status` server-set, mass-assignment blocked by schema |
| 4 | **Edit** — `PUT /listings/{id}` (`live → pending_review`) + `GET /listings/{id}` | B1–B4 | Needs the gate (3); B3 is the anti-bait-and-switch transition |
| 5 | **Lifecycle** — `submit` / `pause` / `resume` / `close` with transition validation | C1–C8 | Needs the gate; the state machine in one place |
| 6 | **Upload** — `POST .../documents` (type+size whitelist, server filename, owner-only) | D1–D6 | Needs the storage port (2) + gate (3); the hostile-input slice |
| 7 | **Download** — `GET .../documents/{doc_id}` (owner-only, `attachment`) | E1–E3 | Needs a stored doc (6); traversal-safe via the port |
| 8 | **Frontend** — `ListingWizard` (step validation) + `MyListings` (empty state) | H1, H2 | Needs the API; components unit-tested (integrated flow = Phase-D E2E) |

**If a slice reveals the order is wrong, fix this table and say so in the commit** — the plan is a design artifact, not a prophecy. **Never** reorder by weakening a test.
