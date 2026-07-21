# Plan 007 — Offers / LOI ⭐

Implementation plan for `spec.md`. Same discipline M5/M6 used: the boundary exists and is
proven by tests before any UI depends on it. This milestone additionally proves the boundary
is **bilateral** — the same three decision endpoints must refuse the caller who has no business
deciding *and* the caller who proposed the very terms in question.

## Schema deltas (`backend/app/models.py`)

**`Offer`** — new table. One row per proposal; a negotiation is a chain of rows linked by
`parent_offer_id`, never a single row mutated in place (spec D1):

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `listing_id` | FK `listing.id`, indexed | |
| `buyer_id` | FK `user.id`, indexed | The negotiation's buyer — from the JWT at root creation, carried unchanged onto every counter in the chain, **never** from the body (A6). |
| `parent_offer_id` | FK `offer.id`, nullable | `null` for the first offer in a thread; set on every row a `counter` creates (C1). |
| `proposed_by_role` | `str` (`"buyer" \| "seller"`) | Who authored **this row's** terms — server-derived from which endpoint created it, never client-set (A6, S3). This is what `require_offer_party`'s decision check reads (D1). |
| `status` | `str`, default `"submitted"` | `submitted → accepted\|declined\|withdrawn\|countered`. All four are terminal for **this row**; `countered` additionally spawns a child row. |
| `price` | `Decimal` via `Money` | Lossless, per the existing M2 `Money` TypeDecorator — never `float` (D6). |
| `structure` | `str` | Free text (D6). |
| `contingencies` | `str \| None` | Free text, optional (D6). |
| `proposed_close_date` | `date` | (D6). |
| `created_at` | `datetime` | |
| `decided_at` | `datetime \| None` | Server-stamped on any decision (accept/decline/withdraw/counter). |
| `decided_by_id` | FK `user.id`, nullable | The deciding party — audit, not exposed on `OfferRead` (mirrors `AccessRequestRead`'s minimalism — spec 005). |

No *plain* unique constraint on `(listing_id, buyer_id)` — unlike `AccessRequest`, many historical
rows per pair are expected and correct. D7's "at most one active" rule is enforced two ways: an
**application-level** pre-check at creation (a query for an existing `submitted` row for the pair)
for a clean 409 on the common case, **backed by a partial unique index** (`WHERE status =
'submitted'`) as the concurrent-create race backstop — a plain constraint would wrongly forbid
terminal rows, but a *partial* index constrains only live offers. *(Corrected during M7's appsec
review: an earlier draft claimed "SQLite has no partial unique index worth the complexity" — that
is factually wrong. SQLite has supported partial indexes since 3.8.0 (2013), and SQLAlchemy exposes
them via `Index(..., unique=True, sqlite_where=..., postgresql_where=...)`; the constraint the check
alone couldn't race-proof is essentially free, so it is now in place — see `models.py` `Offer.__table_args__`.)*

**`OfferEvent`** — new table, a direct mirror of `ListingEvent`/`AccessRequestEvent`, with one
deliberate difference from `AccessRequestEvent` that the plan calls out explicitly:

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `offer_id` | FK `offer.id`, indexed | |
| `actor_id` | FK `user.id` | Server-derived from the JWT. |
| `action` | `str` | `submitted \| accepted \| declined \| withdrawn \| countered \| auto_declined` |
| `from_status` | `str \| None` | `null` only for `action="submitted"` (a row's own creation — the one event this table gets that `AccessRequestEvent` deliberately does not). |
| `to_status` | `str` | |
| `created_at` | `datetime` | |

**Why this table logs creation and `AccessRequestEvent` does not — read the difference, don't
copy the shape blindly.** `AccessRequestEvent` exists *only* to preserve values a later decision
overwrites on the **same row** (`decided_at`/`decided_by_id` — spec 005 D6); a `requested` event
would duplicate `AccessRequest.created_at`, a fact that never moves, so M5 explicitly omits it.
`design_implementation.md`'s M7 prose is explicit that offer creation itself "writes the offer
**plus an `offer_event` audit row**" — a real difference, not an oversight, because `OfferEvent`
here is asked to serve a second job `AccessRequestEvent` never had: it is the **narrative of a
multi-row negotiation thread** (FR-17's "both parties see offer history"), and a thread's first
chapter is "buyer proposed X" — a fact worth a row of its own precisely because a *different* row
(the next one in the chain) is what changes next, unlike `AccessRequest` where the same row's
`decided_at` is what changes. Every subsequent `Offer` row this milestone creates — root or
counter-spawned child — gets its own `action="submitted"` event at the moment it's inserted.

*Erasure note (`data_protection.md`):* both tables reference people but carry no PII of their
own — `structure`/`contingencies` are deal terms, not personal data, the same class
`ListingPrivate.detailed_financials` and `Message.text` already are. Anonymizing a `User` in
place leaves every `Offer`/`OfferEvent` row intact and meaningful — "keep for audit with the
author anonymized," the same treatment `data_protection.md` §3 already names for
offers/access-requests.

**Config** (`backend/app/config.py`):

| Setting | Default | Used by |
|---|---|---|
| `offer_structure_max_chars` | `200` | bounds `structure` |
| `offer_contingencies_max_chars` | `2000` | bounds `contingencies` |

## Endpoints

| Method + path | Permission dependency | Transition |
|---|---|---|
| `POST /api/listings/{listing_id}/offers` | `require_approved_buyer` (new) | — → `submitted` |
| `POST /api/offers/{offer_id}/accept` | `require_offer_party` + decision-rights check | `submitted` → `accepted` **+ listing** `live` → `under_offer` **+ sibling auto-decline** |
| `POST /api/offers/{offer_id}/decline` | `require_offer_party` + decision-rights check | `submitted` → `declined` |
| `POST /api/offers/{offer_id}/counter` | `require_offer_party` + decision-rights check | `submitted` → `countered`, **+ new child row** `submitted` |
| `POST /api/offers/{offer_id}/withdraw` | `require_offer_party` + proposer-rights check | `submitted` → `withdrawn` |
| `GET /api/my/offers` | `get_current_user` (caller-scoped query) | — |
| `GET /api/my/listings/{listing_id}/offers` | `get_owned_listing` *(existing — mirrors spec 005 D7)* | — |

`POST /listings/{id}/offers` deliberately breaks from `design_implementation.md`'s flat
`POST /offers` sketch (spec D3) — same rationale class as spec 005's D7, and the same trade-off
accepted: the build guide's prose is amended with a dated note when this lands, not silently.

## Permission gates (`backend/app/permissions.py`)

Two new pieces, following the exact shape M6's chat boundary established — a shared,
non-`Depends` role function plus a thin REST wrapper, because the bilateral check needs "which
role is the caller" as a value to reason about, not just a pass/fail:

- **`require_approved_buyer`** — "may this caller open an offer on this listing?" (A1–A8, D5).
  Mirrors `create_access_request`'s existing ordering exactly:
  1. Listing missing, or never published and caller isn't the owner → 404 (D5, spec 005 D1).
  2. Caller is the owner → 403 (self-dealing, A4).
  3. No `approved` `AccessRequest` for `(listing, caller)` → 403 `nda_access_required` (A2) — the
     **same query** `require_private_access` runs, deliberately duplicated rather than reused, for
     the same reason `conversation_role_for` duplicates it at M6: this boundary must not be able
     to regress M5's crown-jewel gate by editing it.
  4. `listing.status != "live"` → 409 `listing_not_live` (A3).
  Returns the `Listing`. The D7 "one active offer" check and mass-assignment (A6) are the
  endpoint's own job (schema-level for A6; a query for D7), not the gate's — D7 is a fact about
  *offers*, not about *this listing/buyer pair's* eligibility to negotiate at all.

- **`offer_role_for(session, offer, user) -> Literal["buyer", "seller"] | None`** — the shared
  logic every decision/withdraw endpoint reads, named and shaped after M6's `conversation_role_for`
  on purpose (same problem: two callers need a *role*, not a boolean, and both need to reason
  about it before choosing accept/decline/counter/withdraw's differing rule). Loads the offer's
  listing; owner → `"seller"`. `user.id == offer.buyer_id` → `"buyer"`. Anyone else → `None`.
  **Does not** re-check approved access here — an offer, once it exists, is decided by the two
  parties named on it; approval already gated its *creation* (`require_approved_buyer`), and
  re-deriving it here would let a later revocation silently invalidate a pending offer with no
  criterion asking for that (out of scope — not named by any fold-in or FR).

- **`require_offer_party`** — REST wrapper: loads the `Offer` (`None` → `Forbidden`, never
  `NotFound` — D5 mirrors `require_request_decider`'s uniform-403 reasoning), calls
  `offer_role_for`, raises `Forbidden` on `None`, else returns `(offer, role)`.

- **The bilateral rule lives in the router, not the gate**, exactly as M6 keeps
  `conversation_role_for` a shared primitive and lets each caller decide what to do with the role
  it returns: `accept`/`decline`/`counter` require `role != offer.proposed_by_role` (B4, C6, S8);
  `withdraw` requires `role == offer.proposed_by_role` (D2, D3, S8). One shared role-resolution
  function, two opposite one-line checks built on it — not two gates, so the underlying identity
  question ("is this caller a party to this offer at all?") is answered in exactly one place.

## The atomic accept + sibling auto-decline (`backend/app/routers/offers.py`)

One transaction, mirroring `_transition`'s discipline in `listings.py` (status guard first, so a
409 leaves every row untouched) extended with the sibling side-effect:

1. Re-load the offer's status and its listing's status **inside** the transaction (B8, S6) — a
   409 here means nothing commits, not a half-applied accept.
2. Guard: `offer.status == "submitted"` else 409 `offer_already_decided`; `listing.status ==
   "live"` else 409 `listing_not_live`.
3. Flip `offer.status = "accepted"`, stamp `decided_at`/`decided_by_id`; flip
   `listing.status = "under_offer"`. Write the offer's own `offer_event`
   (`action="accepted"`).
4. **Sibling sweep** (D2): query every **other** `Offer` on this `listing_id` with
   `status == "submitted"`, set each to `"declined"`, write one `offer_event` per row
   (`action="auto_declined"`, `actor_id`=the accepting seller — they caused it, even though they
   did not explicitly decide each one, so the audit records causation honestly rather than
   inventing a system-actor identity nothing else in this codebase has).
5. One `session.commit()` — steps 3–4 are one write, matching `security.md` §1.2's "atomic state
   transitions" rule and the transaction shape M5's `approve_access_request` already established
   for a decision with a second side-effect (there: creating a `Conversation`; here: the sibling
   sweep).

`decline`, `counter`, and `withdraw` do **not** touch the listing or siblings — only `accept`
changes anything outside its own row (plus, for `counter`, the one new child row it creates).

## Response models (`backend/app/schemas.py`)

- **`OfferTerms`** — the shared body shape (`price`, `structure`, `contingencies`,
  `proposed_close_date`), reused by both `OfferCreate` and `OfferCounter` (D6) — no
  `listing_id`/`buyer_id`/`status`/`proposed_by_role` on either: those come from the path, the
  JWT, and the server, never the body (A6).
- **`OfferRead`** — `id`, `listing_id`, `parent_offer_id`, `proposed_by_role`, `status`, `price`,
  `structure`, `contingencies`, `proposed_close_date`, `created_at`, `decided_at`. **No
  `buyer_id`** (the caller of `/my/offers` already knows it's their own — mirrors
  `AccessRequestRead`'s minimalism, spec 005) and **no `decided_by_id`** (not needed by either
  party; "who decided" is implied by role, not a raw id).
- **`OfferWithBuyer`** — `OfferRead` plus a nested `buyer: BuyerProfile` (the **existing** M5
  model, reused as-is — no new profile shape) for the seller's per-listing queue (G1). No
  verification field, same D5 deferral to M10 spec 005 already made.

## Errors (`backend/app/errors.py` — existing classes, new codes)

| Raised | Class | `code` |
|---|---|---|
| No approved access | `Forbidden` | `nda_access_required` *(reused verbatim from M5 — same underlying fact)* |
| Self-dealing (own listing, or wrong side of a decision/withdraw) | `Forbidden` | *(no code — matches `access.py`'s existing plain-`Forbidden` style for self-dealing)* |
| Listing not live | `InvalidTransition` | `listing_not_live` *(named directly in `error_handling.md`'s own worked example)* |
| Duplicate active offer | `Conflict` | `offer_already_active` |
| Illegal decision/withdraw | `InvalidTransition` | `offer_already_decided` *(also named in `error_handling.md`'s worked example)* |

No new `AppError` subclass — the existing five cover every path, the same observation M5 and M6
both recorded.

## Frontend (`app/src/`)

- **`OfferForm.tsx`** (new) — the four `OfferTerms` fields; rendered on the listing detail page
  only when the buyer has approved access **and** no active `submitted` offer (J1, J2).
- **`OfferThread.tsx`** (new) — renders one negotiation's full chain (root → counters → terminal
  decision) in order, with accept/decline/counter/withdraw actions surfaced only on the single
  currently-`submitted` row and only for the party whose turn it is (J3, J4) — the frontend reads
  `proposed_by_role` off that row and compares it to `authStore.user`'s role in this listing,
  mirroring how `ChatWindow.tsx` already compares `sender_id` to the logged-in user (spec 006 J3).
- **`MyOffers.tsx`** (new) — `GET /api/my/offers`, one `OfferThread` per listing.
- **`ListingOffersQueue.tsx`** (new) — the seller's per-listing view, one `OfferThread` per buyer
  plus that buyer's `BuyerProfile` (mirrors `AccessRequestQueue.tsx`'s shape from spec 005).
- **`offerStore.ts`** (MobX, new) — mirrors `accessStore.ts`: request/response state per listing,
  and — matching spec 005's `RequestAccessPanel` lesson — **reads current state from the GET
  endpoints on load**, never from a POST response alone, so a returning buyer sees their pending
  offer's real status after a refresh.
- Routes: `/listings/:id` gains the offer panel; `/my-offers` (buyer); `/my-listings/:id/offers`
  (seller).

## Analytics events

**None.** Still no `track()` wrapper in the codebase (`progress.md` § M4/M5/M6 carryover, restated
each milestone since). An offer's price is exactly the kind of field an analytics call could leak
by accident if the wrapper existed; it doesn't, so there is nothing to be careful with yet.

## Data protection

No new PII field. `Offer`/`OfferEvent` reference people by id only; `structure`/`contingencies`
are user-entered deal terms, the same category `ListingPrivate.detailed_financials` and
`Message.text` already are — minimized by not existing on any schema that doesn't need them, not
by restricting what a user negotiates in their own thread. Erasure behavior: anonymize-in-place
on `User`, keep every `Offer`/`OfferEvent` row (§ Schema deltas above) — same "keep for audit with
the author anonymized" treatment `data_protection.md` §3 already names for offers explicitly.

---

## Build order

Ordered slices — **one trust boundary each**, each turning a named cluster of red tests green,
each one commit. No checkboxes: the red test list is the status (`pytest -q --lf`).

1. **Schema + config.** `Offer`, `OfferEvent`, the two config values. *First because every other
   slice writes or reads these tables* — the same reason M5's and M6's slice 1 were schema-only.
   Turns green: model/column tests only.

2. **Offer creation** + `require_approved_buyer`. *The first trust boundary of the milestone, and
   the one that produces the rows everything downstream decides on* — same ordering logic M5 used
   (NDA-signing before access-requests, access-requests before decisions).
   → **A1–A8**.

3. **The seller's decision on a buyer-proposed offer** — `offer_role_for` + `require_offer_party`
   + `accept`/`decline`, **without** the sibling sweep yet. *Before counter and before siblings,
   because this is the milestone's one genuinely new, security-critical mechanic — the atomic
   offer+listing flip — and it should be provable in isolation before anything is layered on top
   of it.* Each writes its `offer_event` row in the same commit that performs the transition
   (M3/M5's rule: an event written by a different commit than its transition is how an audit
   trail drifts from the code).
   → **B1–B9** (B8's re-check is real here even without siblings: a seller can still pause the
   listing between an offer's creation and its accept attempt).

4. **Sibling auto-decline**, extending the same `accept` transaction from slice 3. *A separate
   slice from 3 on purpose — it is a distinct, separately reviewable business rule bolted onto an
   already-correct, already-tested endpoint, the same way M6 slice 4 added rate-limiting on top of
   an already-authenticated message loop without re-touching the authentication itself.* Verify by
   temporarily removing the sweep and confirming **only** E1–E4 fail, nothing in slice 3's own
   tests does — proof the addition is additive.
   → **E1–E4**.

5. **Counter mechanics** — `counter` on both roles, using the bilateral check `offer_role_for`
   already makes possible. *Sequenced after decisions are proven (slice 3) and after the atomic
   accept is proven twice-reusable is not yet shown — C3 is exactly that proof, applied to a
   counter-spawned row, so counter has to exist before C3 can run.* This slice is what turns
   `countered` from an enum value into tested behavior — the fold-in's whole ask.
   → **C1–C7**.

6. **Withdraw.** *Last of the write paths — the simplest rule (proposer-only, the mirror image of
   slice 3/5's counterparty-only), and one that touches nothing slices 3–5 didn't already prove
   works (the same `require_offer_party` + role comparison, inverted).*
   → **D1–D4**.

7. **The two read queues** — `GET /my/offers`, `GET /my/listings/{id}/offers`. *Read-only and
   lowest-risk, so last among the backend slices, same ordering M5's slice 7 and M6's slice 6
   used* — and the buyer-profile projection needs the shape G1 settles, which only exists once
   offers themselves do.
   → **F1–F3, G1–G4, S1, S2, S4, S5, S7**.

8. **Frontend.** `OfferForm`, `OfferThread`, `MyOffers`, `ListingOffersQueue`, `offerStore`,
   routes. *Last, same reason M5's and M6's UI slices were last: building it against a still-moving
   gate means rebuilding it.*
   → **J1–J5, X4**.

*If a slice reveals this order was wrong, fix the order here and say so in the commit — the plan
is a design artifact, not a prophecy. Never reorder by weakening a test.*
