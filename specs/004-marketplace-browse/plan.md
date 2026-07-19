# Plan 004 — Marketplace browse + anonymous cards (M4)

> Implementation plan for `spec.md`. Sections 1–8 describe *what exists when the
> milestone is done*; **§9 Build order** describes *in what order it gets built*.

---

## 1. Schema deltas

**No table or column changes.** M2's `Listing` / `ListingPrivate` split already
holds exactly the right shape: everything on `Listing` is publishable,
everything identifying is on `ListingPrivate`. M4 is the milestone that proves
that split was designed correctly — it ships a public surface without a
migration.

One **index** is added (no column added, no meaning changed):

| Table | Index | Status |
|---|---|---|
| `listing` | `status` | already indexed at M2 — every browse query filters on it |
| `listing` | `published_at` | **added at M4** — the default ordering column (A9), sorted on by every anonymous request |

`ListingEvent`, `ListingDocument`, `User` — untouched.

## 2. Endpoints

| Method + path | Permission dependency | Response model | Transition |
|---|---|---|---|
| `GET /api/listings` | **none** — public | `ListingPage` (envelope of `ListingPublic`) | none (read) |
| `GET /api/listings/{id}` | **none** — public | `ListingPublic` | none (read) |
| `GET /api/my/listings/{id}` | `get_owned_listing` | `ListingRead` | none (read) — **moved** from `/api/listings/{id}` (spec D1) |
| `GET /api/my/listings` | `get_current_user` | `list[ListingSummary]` | unchanged (M2) |

Query parameters on `GET /api/listings`, all optional, all validated at the
boundary by a Pydantic dependency (`ListingQuery`):

| Param | Type | Bounds |
|---|---|---|
| `q` | `str` | `max_length=100`; LIKE metacharacters escaped |
| `type` | `str` | `max_length=40` |
| `min_price` / `max_price` | `Decimal` | `ge=0`, `max_digits=14` |
| `min_profit` | `Decimal` | `max_digits=14` (may be negative) |
| `limit` | `int` | `ge=1, le=50`, default `20` — **out of range is 422 (A7)** |
| `offset` | `int` | `ge=0`, default `0` |

The `le=50` ceiling is the DoS control (S7). It lives on the schema, so an
over-limit request is refused by Pydantic *before* a query is built.

## 3. Permission gates

M4 adds **no new gate** — it adds the first routes that deliberately have none.
That is a security statement, so it is written down rather than left implicit:

- `GET /api/listings` and `GET /api/listings/{id}` are **unauthenticated by
  design**. Their protection is not a permission check but a **schema plus a
  `WHERE status = 'live'` clause** — the two controls asserted by S3 and S4.
- Because there is no gate, the response model *is* the boundary. `ListingPublic`
  must therefore never be built by copying fields off a joined private row; the
  helper that constructs it takes a `Listing` only, so `ListingPrivate` is not
  even in scope at the call site.
- `get_owned_listing` (M2) is reused unchanged for the moved owner route — same
  404-not-403 semantics, same no-enumeration property.

## 4. Response models (`backend/app/schemas.py`)

```
ListingPublic   id, type, headline, description,
                asking_price, ttm_revenue, ttm_profit, mrr, churn_pct,
                customers, published_at
                # absent by construction: owner_id, status, company_name,
                # website_url, detailed_financials  (S3)

ListingPage     items: list[ListingPublic]
                total: int
                limit: int
                offset: int
```

`ListingPublic` is written as a **standalone model, not a subclass of
`ListingRead`**. Subclassing would mean a private field added to the owner's
view silently joins the public one — the inheritance direction that makes
`AdminListingRead` correct (it *should* inherit everything) is exactly wrong
here. The duplication is the control.

Money fields serialize through the same `field_serializer` idiom as
`ListingRead`, so `"500000.00"` is a string on the wire (A8).

## 5. Frontend (`app/src/`)

| File | Role |
|---|---|
| `components/ListingCard.tsx` | anonymous card — public metrics + a locked section advertising what the NDA unlocks (F1) |
| `components/ListingCard.test.tsx` | the frontend schema-leak twin (F1) |
| `components/BrowseListings.tsx` | grid + filter sidebar + search box + pagination (F2–F6) |
| `components/BrowseListings.test.tsx` | loading / empty / error / refetch (F2–F6) |
| `components/ListingDetail.tsx` | `/browse/:id` public detail |
| `lib/api.ts` | add public GETs — must send **no** `Authorization` header |
| `components/NavBar.tsx` | Browse link (F8) |
| `App.tsx` | public `/browse` and `/browse/:id` routes (F9) + landing copy (F7) |

`lib/api.ts` note: the existing helper attaches the JWT when present. The public
calls use a path that does not, so an expired token cannot make anonymous browse
emit a global 401 and bounce a logged-out visitor to login.

**No MobX store.** Browse state lives in `useState` inside `BrowseListings`,
with the filters in the URL query string. This screen owns its data and nothing
else reads it — the same call `MyListings` made. A store earns its place at M9,
when the watchlist becomes a second consumer of listing state. *(An earlier
draft of this plan listed a `stores/browseStore.ts`; it was never built, and
naming a file that does not exist is the drift this section now avoids.)*

## 6. Errors

| Condition | Raised | Status / code |
|---|---|---|
| bad filter value, `limit` out of range | Pydantic | 422 `validation_error` |
| listing not `live`, or missing | `NotFound` | 404 `not_found` |
| unexpected failure in the browse path | handler in `main.py` | 500 generic + `request_id` (E-2) |

Frontend states: `loading` (skeleton cards), `empty` ("No listings match these
filters" + a clear-filters action), `error` (retry). A 422 renders its
field-level message beside the offending control (E-4).

## 7. Analytics events

**M4 emits none, and that is deliberate.** The constitution (Article 4) names a
local `track(event, props)` wrapper, but **no such wrapper exists in the
codebase yet** — and this spec has no acceptance criterion covering analytics,
so there is no test that would hold an event honest. Shipping events here would
mean building an untested side channel on the milestone that first exposes
public data, which is the wrong milestone to do it on.

When the wrapper does land, browse is its obvious first consumer, and the
constraint is recorded now so it is not rediscovered later: **props carry no
identity fields and no listing-private data** (`security.md` § Audit & logging).
A search event may carry the query *length*, never the query text; a filter
event may carry the filter *keys*, never their values — a price band is a
buyer's private signal, not a public fact.

*(An earlier draft of this section listed four events as though they shipped.
They did not. The security review caught it: "nothing to leak since nothing was
emitted" — true, and exactly why an unbuilt claim in a plan is still a defect.)*

## 8. Data protection

**No new PII, no new person-referencing table** (`docs/data_protection.md`).
M4's contribution is subtractive: it defines the projection of listing data that
may be shown to an unauthenticated stranger. Two consequences worth recording:

- A seller's `owner_id` never crosses the public boundary, so browse creates no
  new link between a person and a business.
- `seed/seed.py` generates **fictional** companies and does not create users
  beyond the seed sellers it owns; it must not be pointed at production data.

## 9. Build order

Each slice is one trust boundary or one coherent surface, turns a named cluster
of red tests green, and ends in one Conventional Commit.

**Slice 1 — `ListingPublic` + the public collection, including pagination.**
Turns green: **A1–A11, S3, S8**.
First because it establishes the boundary everything else in this milestone sits
behind. The model comes before any route that could return it, so there is never
a commit in which a public route exists without the schema that constrains it.
*Pagination sits here rather than in slice 2, where an earlier draft of this
section put it: A10/A11 assert the response envelope, and the envelope cannot
exist without `limit`/`offset`. Recorded because the slice-1 commit already said
so and this section did not.*

**Slice 2 — filters and keyword search.**
Turns green: **B1–B15, S6, E-1**.
Second because filters narrow a result set the previous slice already proved
safe — building them first would mean tuning a query whose output shape is not
yet pinned. LIKE escaping lands here with its tests.

**Slice 3 — the public detail + the owner-route move (spec D1).**
Turns green: **C1–C4, D1–D3, S5, S9, S10, H1, E-3**.
Third because it is the only slice that *moves* an existing route: doing it
after the public collection means the new owner path is added and the three
M2/M3 call sites re-pointed in a single reviewable commit, rather than being
tangled with new-feature work. The commit message states the rename explicitly.

**Slice 4 — `seed/seed.py`.**
Turns green: **E1–E5** (E4/E5, the write guards, were added during the branch
review — see spec.md § E).
Fourth because a seed script is only meaningful once the read paths it feeds
exist — and having real data on hand makes the frontend slices far easier to
build against.

**Slice 5 — frontend browse.**
Turns green: **F1–F6, F8, F9, F11, S11**.
Fifth because it consumes the API the previous slices settled. `ListingCard`
and its leak test come before the grid: the card is where the anonymity promise
is kept on the client.

**Slice 6 — brand voice + landing copy.**
Turns green: **F7, F10**.
Last because it is the only slice with no dependency on anything else in the
milestone, and because it rewrites a string asserted by an existing app-shell
test (`App.test.tsx` AS7) — isolating it keeps that edit from being confused
with the browse work. Also adds the voice section to
`docs/design_system_spec.md` so M8's emails inherit it. **Binding constraint
from the fold-in: navigation labels stay literal** ("Browse", "My listings") —
the story lives in headlines and prose only.

*No slice removes tests.* The D1 route move in slice 3 **re-points** three
existing call sites to `/api/my/listings/{id}` with their assertions unchanged, and
adds **H1** to assert the old path's private-field behavior is gone — so
coverage moves rather than shrinks.
