# Plan 012 — Deal completion (M12)

> Implementation plan for [`spec.md`](./spec.md). Sections 1–7 describe **what exists when this is done**;
> § Build order describes **the order it gets built in**.

---

## 1. Schema deltas (`backend/app/models.py`)

**`Listing`** — two new nullable columns, written only by `mark-sold` (spec D4):

| Column | Type | Notes |
|---|---|---|
| `sold_at` | `datetime \| None` | UTC, server-stamped. Null for every listing that has not closed. |
| `final_price` | `Decimal \| None` (`sa_type=Money`) | Copied from the accepted offer's `price` at close. `Money` (lossless TEXT), never float — same treatment as every other money field since M2. |

Both absent from `ListingPublic` by construction (spec S11). No index: neither is filtered on by any route
this milestone adds, and a speculative index is a schema claim nothing tests.

**No new tables.** The two audit tables this milestone writes to already exist:

- **`ListingEvent`** gains two `action` values — `sold` and `fell_through`. The column is a free `str`, so this
  is a vocabulary extension, not a migration. `specs/003-admin-curation/plan.md` predicted exactly these two
  names ("extended by M12 for `sold` / `fell_through`"); the comment in `models.py:159`
  (`# approved | rejected (M12 extends)`) is updated to name them (slice 7).
- **`OfferEvent`** gains two `action` values — `completed` and `lapsed`.

**Offer status vocabulary** gains two terminal states, `completed` and `lapsed` (spec D5). No schema change:
`Offer.status` is a `str`. M7's partial unique index is scoped `WHERE status = 'submitted'`, so terminal rows
remain unconstrained and the new states cannot collide with it.

**Data protection** — no new PII, no new person-referencing table; the new columns are business facts about a
listing, and the new event rows are audit-exempt on erasure under the existing rule (spec D11,
`docs/data_protection.md`).

---

## 2. Endpoints

| Method + path | Permission dependency | Transition |
|---|---|---|
| `POST /api/listings/{id}/mark-sold` | `get_owned_listing` | listing `under_offer → sold`; accepted offer `accepted → completed`; stamps `sold_at` + `final_price` |
| `POST /api/listings/{id}/relist` | `get_owned_listing` | listing `under_offer → live`; accepted offer `accepted → lapsed` |

Both live in `backend/app/routers/listings.py` beside `pause`/`resume`/`close`, take **no request body**, and
return `ListingRead` — identical in shape to every other seller lifecycle route, which is the point: they are
the same kind of thing.

**Changed:** `PUT /api/listings/{id}` (`update_listing`) refuses `under_offer` with 409 `listing_under_offer`
(spec D8/S12). This is a guard added to an existing route, not a new route.

### The atomic close (`mark-sold`)

One transaction, compare-and-swap throughout — the shape M7's `accept_offer` established and proved
(`security.md` §6 races; spec C5):

1. `UPDATE listing SET status='sold', sold_at=…, final_price=… WHERE id=? AND status='under_offer'` — rowcount
   ≠ 1 → `InvalidTransition`, nothing written. The read-then-write alternative is a TOCTOU: production hands
   each request its own `Session`, so a status read at dependency time is a snapshot, not a lock.
   **`final_price` is resolved *before* this statement** (step 0 below), so the CAS writes the derived value in
   the same statement that claims the transition.
   *Step 0:* `SELECT` the listing's offer `WHERE status='accepted'`; none → `InvalidTransition(code="no_accepted_offer")`
   before any write (spec C4).
2. `UPDATE offer SET status='completed' WHERE id=? AND status='accepted'` — rowcount ≠ 1 → `session.rollback()`
   then 409, exactly as `accept_offer` rolls its own offer CAS back when the listing flip fails. `decided_at`
   and `decided_by_id` are **not** touched: they record the acceptance, and this transition is not one (A3).
3. `_transition`-style `ListingEvent` + `_record`-style `OfferEvent`, then one `session.commit()`.

`relist` is the same shape with `to='live'` and `lapsed`, minus the price derivation — but it **does** still
require an `accepted` offer to move, so step 0's guard applies to it identically.

*Note on `_transition`:* `listings.py`'s existing helper already does status-guard → set fields → audit, but it
guards with a Python-side `if` rather than a CAS. `mark-sold`/`relist` need the CAS (money path, spec C5), so
they are written explicitly like `accept_offer` rather than routed through `_transition`. `_transition`'s
`set_fields` mechanism (which exists so `published_at` is never stamped on a failed transition) is the same
idea applied to `sold_at`/`final_price`; the rule it encodes is preserved, the implementation is the stronger
one.

---

## 3. Permission gates

**No new function in `permissions.py`** (spec D2) — the fourth milestone to add none, after M3, M4 and M11.
Both routes depend on the existing `get_owned_listing`, which returns 404 for both "no such listing" and "not
yours" (spec D3, S2–S6).

`require_private_access` is **untouched** and must stay untouched: spec S8 asserts that a `sold` listing's data
room behaves exactly as before. The gate's own docstring already anticipated this milestone — that comment
moves from future to present tense in slice 7.

---

## 4. Response models (`backend/app/schemas.py`)

- **`ListingRead`** (owner's full view) — add `sold_at: datetime | None` and `final_price: Decimal | None`,
  the latter joining `_MONEY_FIELDS` so it serializes as an exact string (A5).
- **`ListingSummary`** (`GET /my/listings` row) — add both, so the dashboard can show the sale without a
  second fetch (A5, F5).
- **`ListingPublic`** — **unchanged**, deliberately. It is a standalone model rather than a subclass precisely
  so that adding a field to `ListingRead` cannot leak it here; spec S11 asserts the absent field set directly.
  Its docstring's "M12 may add a deliberate public 'under offer' flag" is answered with "no" in slice 7 (D10).
- **`OfferRead`** — unchanged. `status` is already a free string, so `completed`/`lapsed` surface with no
  schema change on either party's offer list.

---

## 5. Notifications (`backend/app/notifications.py`)

Two `_TEMPLATES` entries:

```
"offer_completed": "The sale of “{headline}” has been completed",
"offer_lapsed":    "The deal on “{headline}” did not complete — the listing is back on the market",
```

and one new function, **`notify_deal(session, offer, action)`**, sitting beside `notify_offer` and reusing its
`_offer_parties` helper. It is a separate function rather than two more entries in `notify_offer`'s recipient
map because the recipient rule genuinely differs (spec D9): every M7 action resolves from `proposed_by_role`
because either party can propose, while these two are always caused by the seller and always land on the
**buyer** — including when the accepted row was a seller counter (E3). Folding a role-based rule into a
map whose docstring promises a proposer-based one would make the shared function lie about itself. No new
channel: M8's dispatcher picks these rows up like any other notification type.

---

## 6. Frontend (`app/src/`)

- **`components/DealActions.tsx`** *(new)* — the two actions plus their confirmation dialog. Renders only when
  the listing is `under_offer` (F2); shows the final price read-only from the accepted offer (F1); disables
  both while a request is in flight (F7); renders an inline `ApiError` message on 409 (F6). MUI `Dialog`, the
  existing `theme.ts` tokens, and `StatusChip` — no new design vocabulary (`sold` and `under_offer` are already
  in `StatusChip`'s map, added at design-system time).
- **`stores/offerStore.ts`** — `markSold(listingId)` / `relist(listingId)` calling the two POSTs through the
  existing `api()` JWT layer. They live here rather than in a new store because the accepted offer is what both
  actions resolve around, and this store already owns the seller's per-listing offer view.
- **`App.tsx`** — `ListingOffersRoute` renders `<DealActions>` above `<ListingOffersQueue>`; it fetches
  `GET /api/my/listings/{id}` for the status and price. Route-guarded by `RequireAuth` for UX only — the real
  boundary is the server's `get_owned_listing`, as the existing comment on that route already says.
- **`components/MyListings.tsx`** — a `sold` row shows its final sale price beside the chip (F5).

---

## 7. Errors & analytics

**Errors** — reuses `InvalidTransition` (409) with two new machine codes, `no_accepted_offer` and
`listing_under_offer`, and `NotFound` (404) via the existing gate. No new `AppError` subclass: both new
conditions *are* invalid transitions, and a subclass per message would dilute the class.

**Analytics** — `track('deal_marked_sold', { listing_id })` and `track('deal_fell_through', { listing_id })`.
Listing id only: **no price, no buyer id, no seller id** — `security.md` § Audit & logging forbids identity in
analytics, and a sale price in a console event is the same leak class as one in a log line.

---

## Build order

Seven slices, each one trust boundary or one coherent surface, each ending in one Conventional Commit.

1. **`feat:` schema + the owner's read surface.** The two `Listing` columns, `ListingRead` / `ListingSummary`,
   `ListingPublic` untouched. *First because every later slice writes these columns*, and because it turns the
   schema-leak assertions (S11) green before any code can leak anything. Turns green: **A6, S11**.

2. **`fix:` close the edit corridor — refuse `PUT` while `under_offer`.** *Before* either new transition
   exists, so the bait-and-switch hole (spec D8) is never reachable on this branch even mid-milestone. This
   slice is a **bug fix to shipped code**, and is sequenced ahead of the feature that would have made it worse.
   Turns green: **S12, S13**.

3. **`feat:` `POST /listings/{id}/mark-sold`** — the atomic close: price derivation, both CASs, both audit
   rows. The milestone's money path, so it lands alone. Turns green: **A1–A5, C1, C3, C4, C5, D1, D2, S1, S2,
   S4 (mark-sold half), S5, S6, S7 (mark-sold half), S8, S9, S10, S14, S15**.
   *(S8–S10 and S14 are regression assertions that first become **reachable** here — they cannot pass before
   this slice because there is no way to produce a `sold` listing without it. They are red until slice 3 for a
   real reason, not vacuously.)*

4. **`feat:` `POST /listings/{id}/relist`** — the fell-through path, the `lapsed` terminal state, and the
   sibling-untouched guarantee. After `mark-sold` because it is the same transaction shape minus the
   derivation, and because B5/B6 (re-list then re-sell) depend on slice 3 existing. Turns green: **B1–B6, C2,
   D3, D4, D5, S3, S4 (relist half), S7 (relist half)**.

5. **`feat:` notifications for both paths.** Two templates + the role-based recipient branch. After both
   routes, because a notification for a transition that does not exist cannot be tested. Turns green:
   **E1, E2, E3**.

6. **`feat:` the seller's deal actions UI.** `DealActions` + store methods + route wiring + the `MyListings`
   final-price row. Last of the code slices — the backend contract is settled by now, so nothing here is built
   against a moving target. Turns green: **F1–F7**.

7. **`docs:` retire every expired M12 deferral.** Turns no test green — it is the slice the run-milestone
   playbook mandates when a milestone lands a feature earlier specs deferred to it. Run
   `git grep -in "until M12\|M12 \|(once M12\|M7/M12\|later, M12"` across `specs/`, `docs/`, `backend/` and
   `app/`, and fix **every** hit in this one commit — the prose copies are the ones that get missed. Known
   targets, each retired **in place with a dated note**, never silently deleted:
   - `docs/security.md` §7 M12 — the `403` → `404` correction (spec D3), dated.
   - `docs/testing_guide.md` §5 — the "(once M12 lands)" caveat on the golden path; the golden path itself
     stays Phase D (spec § Out of scope).
   - `docs/milestones.md` § Scope fold-ins + the M12 tracker row *(the tracker tick itself belongs to
     `/open-pr`, not here)*.
   - `specs/002-listing-builder/{spec,plan}.md` — "`under_offer`/`sold` are M7/M12".
   - `specs/003-admin-curation/plan.md` — "extended by M12 for `sold` / `fell_through`" → shipped, with the
     actual action names.
   - `specs/004-marketplace-browse/spec.md` D2 + `schemas.py`'s `ListingPublic` docstring — "M12 may add a
     public flag" → **declined**, with the reason (spec D10).
   - `specs/005-nda-gate/spec.md` — the `sold`-listing gate promise → now asserted by S8.
   - `specs/007-offers/spec.md` — "`under_offer → sold` … are M12's" → shipped; and the sibling policy note,
     now honored by spec D6.
   - `specs/009-watchlist/spec.md` D3 — "(later, M12) marked `sold`" → now current behaviour.
   - `specs/011-valuation-calculator/spec.md` — "needs M12's `sold` rows to exist first" → they now do;
     the comps upgrade itself remains `agentic_scope.md` proposal F.
   - `backend/app/models.py:159` and `backend/app/permissions.py:143-144` — future tense → present.

**No checkboxes anywhere in this file, by design.** The red test list is the status
(`cd backend && pytest -q --lf`) and the red count is the progress bar; a ticked box here would be a second
source of truth that lies after the first crash, which is exactly why `/resume` rebuilds from git + tests
alone (constitution Article 3 §1). The suite is **red overall** until slice 6 — that is the queue draining,
not a broken build. No slice removes tests.
