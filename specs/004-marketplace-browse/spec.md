# Spec 004 — Marketplace browse + anonymous cards (M4)

> **Milestone:** M4 — Marketplace browse + anonymous cards
> (`docs/design_implementation.md` Part 4 § *Milestone 4*; `docs/milestones.md` table row + § Scope fold-ins → M4).
> **Binding:** `specs/000-constitution.md`, `docs/security.md` (§6, §7), `docs/error_handling.md`.

This is the milestone where NextOwner gets a **public face**. Every route before
now required a token; M4 ships the first endpoints an anonymous stranger may
call, and the first response model whose job is to *withhold*. The public/private
split (Article 2 #2) stops being a table-layout decision and becomes a wire
format.

---

## FR references

| FR | What M4 satisfies |
|---|---|
| **FR-6** | Listings are anonymous publicly; identifying details hidden until NDA acceptance (M5 opens the gate; M4 builds the anonymous half). |
| **FR-10** | Browse, keyword-search, and filter (type, price range, revenue, profit) listings. *Sorting beyond the default and the "multiple" filter are deferred — see Out of scope.* |
| **F4 / F5** | (`requirements.md` §1) Anonymous public listing card; browse + filter + keyword search. |

FR-8's "state changes propagate to search" is satisfied structurally: browse
reads `listing.status` live, so a pause or close removes a listing from results
on the next request with no propagation step to go stale.

---

## Decisions taken at spec time

**D1 — the public view takes the canonical path; the owner's view moves.**
`GET /api/listings/{id}` was owner-scoped from M2 (404 for non-owners). One path
cannot serve two trust levels, so:

| Path | Who | Model |
|---|---|---|
| `GET /api/listings` | anyone (no auth) | `ListingPublic` — `live` only |
| `GET /api/listings/{id}` | anyone (no auth) | `ListingPublic` — `live` only |
| `GET /api/my/listings` | owner | `ListingSummary` *(unchanged)* |
| `GET /api/my/listings/{id}` | owner | `ListingRead` *(**moved** from `/api/listings/{id}`)* |

The owner's route joins the `/my/` prefix its sibling collection already uses.
**Six M2/M3 tests re-point to the new path with their assertions unchanged** —
this is a route rename carried out as a spec decision, *not* a test weakened to
pass (`/dod` forbids the latter; criterion **H1** pins the distinction by
asserting the old path no longer serves the owner's private fields).

*Note:* `docs/testing_guide.md` §4.2's illustrative M3 snippet reads `status`
from `GET /api/listings/{id}`. That snippet predates this decision and is not a
test in the suite; the real M3 tests read status via `/api/my/listings`. §4.3's
schema-leak snippet — an unauthenticated `GET /api/listings/{id}` — becomes
literally correct for the first time under D1.

**D2 — `status` is not on the public model.** Public browse returns `live` rows
only, so a `status` field would be a constant that tells a caller nothing while
creating a channel for a future state to leak by accident. M12 may add a
deliberate public "under offer" flag; it will be a named field with its own
criterion, not an inherited enum.

**D3 — `/browse` is its own page; `/` stays the landing page.** The marketplace
grid lives at `/browse` (public), listing detail at `/browse/:id` (public). `/`
keeps the landing hero — now in the succession voice — and keeps today's
behavior of sending an already-authed visitor to their dashboard, so `App.test.tsx`
AS6 stands unchanged and AS7 changes only its tagline string.

**D4 — keyword search covers public text only.** `q` matches `headline` and
`description`. It must **not** reach `ListingPrivate` — a search box that
confirms "SecretCo" exists is an identity oracle that defeats FR-6 without ever
rendering the field. Criterion **B8** is that test.

---

## User stories

1. **As an anonymous visitor**, I want to browse live businesses for sale without
   creating an account, so that I can judge whether this marketplace has supply
   worth signing up for.
2. **As a buyer**, I want to filter by type, price range and profit and search by
   keyword, so that I can find the businesses that match my mandate instead of
   reading every listing.
3. **As a buyer**, I want each card to show real operating numbers while the
   identifying details stay locked, so that I can shortlist honestly and know
   exactly what signing the NDA will unlock.
4. **As a seller**, I want my drafts, rejected and paused listings to be
   invisible to the public, so that only work an admin approved represents me.
5. **As a seller**, I want the public front door to describe succession rather
   than a transaction, so that I understand this platform lets me choose who
   carries the business forward.

---

## Acceptance criteria

Each numbered scenario maps to **exactly one test**.

### A — the public browse collection

- **A1** — GIVEN listings in `draft`, `pending_review`, `rejected`, `paused`,
  `closed` and `live`, WHEN anyone calls `GET /api/listings`, THEN only the
  `live` ones are returned.
- **A2** — GIVEN a seller with a `draft` listing, WHEN that seller calls
  `GET /api/listings` **with their own token**, THEN their draft is still absent
  (the public route is public for everyone; the dashboard is `/api/my/listings`).
- **A3** — GIVEN no `Authorization` header at all, WHEN `GET /api/listings` is
  called, THEN it returns 200 (not 401).
- **A4** — GIVEN a live listing whose private row holds `company_name` and
  `website_url`, WHEN `GET /api/listings` is called, THEN no item contains
  `company_name`, `website_url`, `detailed_financials`, or `owner_id`.
- **A5** — GIVEN 5 live listings, WHEN called with `limit=2&offset=2`, THEN
  exactly 2 items are returned and they are the 3rd and 4th of the full ordering.
- **A6** — GIVEN no `limit` parameter, WHEN called, THEN a documented default
  page size is applied rather than the whole table.
- **A7** — GIVEN `limit` above the hard cap, WHEN called, THEN the response is
  422 (an explicit refusal, not a silent clamp that hides the caller's mistake).
- **A8** — GIVEN a live listing with `asking_price` `500000.00`, WHEN called,
  THEN the value is serialized as the string `"500000.00"` (Decimal precision
  exact over the wire, matching `ListingRead`).
- **A9** — GIVEN several live listings published at different times, WHEN
  called, THEN they are ordered newest-published first, deterministically.
- **A10** — GIVEN 5 live listings and `limit=2`, WHEN called, THEN the envelope
  reports a total of 5 (so the UI can paginate).
- **A11** — GIVEN no live listings at all, WHEN called, THEN 200 with an empty
  item list and total 0 (an empty marketplace is not an error).

### B — filters and keyword search

- **B1** — `type=saas` returns only `saas` listings.
- **B2** — `min_price` + `max_price` return only listings inside the inclusive range.
- **B3** — `min_profit` returns only listings at or above that `ttm_profit`.
- **B4** — a **combination** (`type` + price range + `min_profit`) applies every
  clause together — parametrized over several combinations and expected id sets.
- **B5** — `q` matching a word in `headline` returns that listing.
- **B6** — `q` matching a word in `description` returns that listing.
- **B7** — `q` is case-insensitive (`SCHEDULING` finds "scheduling").
- **B8** — **`q` never searches private data:** GIVEN a live listing whose
  `company_name` is "SecretCo" and whose public text does not contain it, WHEN
  `q=SecretCo`, THEN zero results (no identity oracle — D4).
- **B9** — `q` containing SQL metacharacters (`' OR 1=1 --`) returns zero
  results and **not** a 500 — the query is parameterized, never string-built.
- **B10** — `q` containing LIKE wildcards (`%`) is escaped and matches literally,
  so `%` does not return the whole table.
- **B11** — a non-numeric `min_price` is 422 with a field-level detail.
- **B12** — `min_price` greater than `max_price` returns an empty list (a
  contradiction is an empty result, not a server error).
- **B13** — a filter that matches nothing returns 200 + empty list + total 0.

### C — the public listing detail

- **C1** — GIVEN a `live` listing, WHEN `GET /api/listings/{id}` is called with
  no auth, THEN 200 with the public model.
- **C2** — GIVEN a listing in any non-`live` state, WHEN the **owner** calls
  `GET /api/listings/{id}`, THEN 404 — the public route never serves unapproved
  content, not even to the person who wrote it.
- **C3** — GIVEN an id that does not exist, WHEN called, THEN 404 with the same
  body shape as C2 (a non-live listing and a missing one are indistinguishable —
  no existence oracle).
- **C4** — GIVEN a live listing, WHEN called, THEN the body contains no
  `company_name`, `website_url`, `detailed_financials`, or `owner_id`.

### D — the owner's view at its new path

- **D1** — GIVEN a seller's own listing in any state, WHEN they call
  `GET /api/my/listings/{id}`, THEN 200 including `company_name`, `status` and
  `owner_id`.
- **D2** — GIVEN another user's listing, WHEN a non-owner calls
  `GET /api/my/listings/{id}`, THEN 404 (unchanged M2 semantics — not 403).
- **D3** — GIVEN no token, WHEN `GET /api/my/listings/{id}` is called, THEN 401.

### E — seed data

- **E1** — WHEN `seed/seed.py` runs against an empty database, THEN it creates
  at least 30 listings, of which at least 25 are `live` with a `published_at`,
  spanning more than one `type`, and each with a `ListingPrivate` row.
- **E2** — WHEN `seed/seed.py` runs a second time, THEN it does not duplicate
  its listings (re-running a seed script is a normal thing to do).
- **E3** — WHEN seeded listings are fetched via `GET /api/listings`, THEN none
  of them leaks an identity field (the seed goes through the same schema).

### F — frontend

- **F1** — `ListingCard` renders headline, type and public metrics, and renders
  **no** identity field when one is present on the object handed to it.
- **F2** — `BrowseListings` renders a card per item returned by the API.
- **F3** — while the request is in flight, a loading state is shown.
- **F4** — when the API returns zero items, an empty state explains it rather
  than rendering a blank page.
- **F5** — when the API errors, an error state is shown and the app does not
  crash.
- **F6** — changing a filter refetches with the filter in the query string.
- **F7** — the landing page at `/` carries the succession-voice hero copy
  (replaces the AS7 tagline assertion in `App.test.tsx`).
- **F8** — the nav bar offers a **Browse** link to `/browse`, visible whether or
  not the visitor is signed in.
- **F9** — `/browse` renders for a logged-out visitor without redirecting to
  login (it is a public route, not a `RequireAuth` one).

### Security & abuse

*(`docs/security.md` §7 M4 row + §6 edge cases. These are the crown jewels.)*

- **S1 — schema leak, collection.** Covered by **A4**.
- **S2 — schema leak, detail.** Covered by **C4**.
- **S3 — schema leak by construction.** GIVEN the `ListingPublic` model, WHEN
  its field set is inspected, THEN it contains none of `owner_id`,
  `company_name`, `website_url`, `detailed_financials`, `status`. *This asserts
  the control itself, not one of its outputs — a future field added to the
  model is caught here even if no route test happens to cover it.*
- **S4 — only `live` is public.** Covered by **A1** and **C2**.
- **S5 — no enumeration.** Covered by **C3** (missing and non-live are the same
  404).
- **S6 — parameterized filters.** Covered by **B9**; **B10** covers LIKE
  wildcard escaping.
- **S7 — pagination cap (DoS).** Covered by **A7**; **A6** covers the default.
- **S8 — the public route grants nothing extra to an authed caller.** GIVEN an
  admin token, WHEN `GET /api/listings` is called with it, THEN the response is
  byte-identical to the anonymous one (no privileged widening on a public route).
- **S9 — reachability: no seller-controlled path publishes to browse.** GIVEN a
  fresh listing, WHEN every sequence of up to three seller-only actions
  (`submit`, `pause`, `resume`, `close`, `PUT` edit) is walked, THEN the listing
  appears in `GET /api/listings` **only** in states reached via an admin
  approval. *Extends spec 003's E6 reachability test to the newly public
  surface: M3 proved the seller cannot reach `live`; M4 must prove that being
  in browse requires exactly that.*

### Errors & failure modes

*(`docs/error_handling.md` — contract as implemented at M1: a flat
`{detail, code, request_id}` body, generic messages, no internals. Verified
against `backend/tests/test_error_contract.py` G1–G3 rather than quoted from
prose.)*

- **E-1** — a 422 from a bad filter carries a field-level detail identifying the
  offending parameter (**B11** asserts the status; this asserts the shape).
- **E-2** — a forced 500 inside the browse path returns the generic contract
  with a `request_id` and **no** stack trace, SQL, or table name.
- **E-3** — a 404 from `GET /api/listings/{id}` carries `code: "not_found"` and
  a generic message that does not reveal whether the row exists.
- **E-4 (frontend)** — a 422 from the browse request surfaces as a readable
  message rather than a raw error object (**F5** covers the transport error;
  this covers the validation error).

### H — regression guards on the D1 move

- **H1** — GIVEN a seller's own `draft` listing, WHEN they call the **old**
  `GET /api/listings/{id}` with their token, THEN they do **not** receive
  `company_name` (they get 404 per C2). *This is what makes the D1 test
  re-pointing a rename rather than a deletion of coverage: the old path's
  private-field behavior is now asserted gone, not merely untested.*

---

## Out of scope

- **The NDA gate itself (M5).** M4 renders a locked section advertising what is
  gated; nothing unlocks it yet, and no access-request endpoint exists.
- **Sorting controls and the "multiple" filter** (FR-10's remainder) — the
  default newest-first ordering ships; user-selectable sort is deferred with no
  milestone claimed.
- **Saved searches / alerts** (FR-11) — M8.
- **Watchlist / favorites** (FR-12) — M9.
- **Full-text search.** SQL `LIKE` is the MVP mechanism the fold-in specifies;
  a real index is a Postgres-era concern.
- **Paywall.** The locked card section is the future paywall surface; no payment
  code lands here (payments remain unsequenced).
- **Listing images.** Cards are typographic; media upload is not in M2's schema.
