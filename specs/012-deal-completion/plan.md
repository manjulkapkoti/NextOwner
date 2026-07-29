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
  (`# approved | rejected (M12 extends)`) is updated to name them (slice 5).
- **`OfferEvent`** gains two `action` values — `completed` and `lapsed`.

**Offer status vocabulary** gains two terminal states, `completed` and `lapsed` (spec D5). No schema change:
`Offer.status` is a `str`. M7's partial unique index is scoped `WHERE status = 'submitted'`, so terminal rows
remain unconstrained and the new states cannot collide with it.

**Data protection** — no new PII, no new person-referencing table; the new columns are business facts about a
listing, and the new event rows are audit-exempt on erasure under the existing rule (spec D12,
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

**Changed — two guards on existing M2 routes, not new routes:**
- `PUT /api/listings/{id}` (`update_listing`) refuses `under_offer` → 409 `listing_under_offer` (spec D8/S12/S13).
- `POST /api/listings/{id}/documents` (`upload_document`) refuses `_EDIT_LOCKED` (`closed`/`sold`) → 409 (S14).
  Added late, after the independent appsec pass; `under_offer` deliberately stays open (S16). Note this also
  newly blocks uploads on **`closed`**, which M12 did not scope and no criterion covers — accepted as benign
  (`closed` is terminal, no route accepts it as a from-state, so no seller can be stranded), and recorded
  here rather than left to be discovered.

### The atomic close (`mark-sold`)

One transaction, compare-and-swap throughout — the shape M7's `accept_offer` established and proved
(`security.md` §6 races; spec C5):

1. **Status check first**, Python-side: not `under_offer` → `InvalidTransition` (`invalid_transition`). This
   decides only *which* 409 the caller gets — the CAS in step 2 is the real guard. Ordering it first is what
   makes the two machine codes mean different things: without it, `mark-sold` on a `live` listing would be
   reported as a missing accepted offer, which is true but useless (spec C1 vs C4).
2. **Claim the contended row:** `UPDATE listing SET status='sold' WHERE id=? AND status='under_offer'` —
   rowcount ≠ 1 → `session.rollback()` then `InvalidTransition`. The read-then-write alternative is a TOCTOU:
   production hands each request its own `Session`, so the status read in step 1 is a snapshot, not a lock.
3. `SELECT … WHERE status='accepted' ORDER BY id`; none → `session.rollback()` +
   `InvalidTransition(code="no_accepted_offer")` (spec C4). The `ORDER BY` is not cosmetic: if the
   at-most-one-`accepted` invariant is ever broken by a later milestone, the recorded sale price must degrade
   *deterministically* rather than arbitrarily.
4. `UPDATE offer SET status='completed' WHERE id=? AND status='accepted'` — rowcount ≠ 1 → `session.rollback()`
   then 409, exactly as `accept_offer` rolls its own offer CAS back when the listing flip fails. `decided_at`
   and `decided_by_id` are **not** touched: they record the acceptance, and this transition is not one (A3).
5. The derived sale fields: `UPDATE listing SET sold_at=…, final_price=…` — same transaction as step 2.
6. `ListingEvent` + `OfferEvent`, `notify_deal`, then one `session.commit()`.

> **The order of steps 2 and 3 was reversed after the independent appsec pass (2026-07-29), and the reason is
> the whole value of this section.** The original read the offer first and CAS'd the listing second — and
> because a losing request's `SELECT` reads *committed* state, it always found no `accepted` offer and was
> refused by `no_accepted_offer` **before reaching the rowcount guard at all**. The guard was dead code: C5
> passed with both rowcount checks deleted. The guards were never wrong, they were unreachable. Claiming the
> contended row first makes the guard both the actual refusal and a testable one, and C5 now pins the machine
> code (`invalid_transition`) rather than merely "was refused". Sabotage-verified: deleting the guard turns C5
> red. The cost is that the derived price moves to its own statement (step 5) instead of riding along with the
> claim — atomicity is unchanged, because it was always the single commit and the rollbacks doing that work,
> never the packing of columns into one statement.

`relist` is the same shape with `to='live'` and `lapsed`, minus step 5 — but it **does** still require an
`accepted` offer to move, so step 3's guard applies to it identically. Both routes run through one shared
`_resolve_deal` helper parameterized by the two status strings, the two audit action names, and an optional
price-derivation callback.

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
moves from future to present tense in slice 5.

---

## 4. Response models (`backend/app/schemas.py`)

- **`ListingRead`** (owner's full view) — add `sold_at: datetime | None` and `final_price: Decimal | None`,
  the latter joining `_MONEY_FIELDS` so it serializes as an exact string (A5).
- **`ListingSummary`** (`GET /my/listings` row) — add both, so the dashboard can show the sale without a
  second fetch (A5, F5).
- **`ListingPublic`** — **unchanged**, deliberately. It is a standalone model rather than a subclass precisely
  so that adding a field to `ListingRead` cannot leak it here; spec S11 asserts the absent field set directly.
  Its docstring's "M12 may add a deliberate public 'under offer' flag" is answered with "no" in slice 5 (D10).
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

Five slices, each one trust boundary or one coherent surface, each ending in one Conventional Commit.
*(Planned as seven; slices 3-5 merged into one during the build — see the note under slice 3. The numbering
below is the shipped one, renumbered 2026-07-29 after the docs audit found the count and the list disagreed.)*

1. **`feat:` schema + the owner's read surface.** The two `Listing` columns, `ListingRead` / `ListingSummary`,
   `ListingPublic` untouched. *First because every later slice writes these columns*, and because it turns the
   schema-leak assertions (S11) green before any code can leak anything. Turns green: **A6, S11**.

2. **`fix:` close the edit corridor — refuse `PUT` while `under_offer`.** *Before* either new transition
   exists, so the bait-and-switch hole (spec D8) is never reachable on this branch even mid-milestone. This
   slice is a **bug fix to shipped code**, and is sequenced ahead of the feature that would have made it worse.
   Turns green: **S12, S13**.

3. **`feat:` both deal resolutions + their notifications.** `POST /listings/{id}/mark-sold` and
   `POST /listings/{id}/relist` over one shared `_resolve_deal` transaction (CAS the listing, CAS the accepted
   offer, two audit rows, `notify_deal`, one commit), plus the two templates. Turns green: **A1–A5, B1–B6,
   C1–C5, D1–D5, E1–E3, S1–S10, S13, S14, S15**.
   *(S8–S10 and S14 are regression assertions that first become **reachable** here — nothing can produce a
   `sold` listing before this slice, so they were red for a real reason, not vacuously.)*

   > **Merged from three slices to one during the build, deliberately.** The plan had these as slice 3
   > (`mark-sold`), slice 4 (`relist`) and slice 5 (notifications). The dependency it missed: the two routes
   > are the *same transaction* differing only in two status strings and whether a price is derived, and the
   > notification call lives inside that shared helper. Landing them separately would have meant either
   > writing the transaction twice and deleting one copy, or shipping a helper with an unreachable branch and
   > no test covering it — both worse than one honest commit. The plan is a design artifact, not a prophecy
   > (`/run-milestone` step 5); this records what the design turned out to be.
   >
   > One real defect fell out of building it, and is worth keeping: the first version looked up the accepted
   > offer **before** checking the listing's status, so a `live` listing's `mark-sold` was refused as
   > `no_accepted_offer` instead of `invalid_transition`. C1's parameterization over all seven other states
   > caught it. The ordering rule `_transition`'s docstring already stated — *the status check comes first* —
   > is the reason the two 409s carry different machine codes at all.

4. **`feat:` the seller's deal actions UI.** `DealActions` + store methods + route wiring + the `MyListings`
   final-price row. Last of the code slices — the backend contract is settled by now, so nothing here is built
   against a moving target. Turns green: **F1–F8**.

5. **`docs:` retire every expired M12 deferral.** Turns no test green — it is the slice the run-milestone
   playbook mandates when a milestone lands a feature earlier specs deferred to it. Run
   `git grep -in "M12"` — **the bare token, case-insensitive, with no alternation** — across `specs/`, `docs/`,
   `backend/` and `app/`, and read every hit. Fix them all in this one commit; the prose copies are the ones
   that get missed.
   > **The narrower five-alternative grep this line used to prescribe is what let two deferrals through**
   > (`M7 / M12.` — spaces around the slash; `owned by **M12**;` — punctuation, no trailing space), both caught
   > by the independent docs audit rather than by the sweep. A pattern list encodes the phrasings you thought
   > of; the bare token encodes none. Noise is cheaper than a missed claim, and the audit's own method — the
   > bare token plus a second sweep for future-tense phrasing *near the feature words* but without the token
   > ("once the sold transition exists") — is the one to copy. Known
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
alone (constitution Article 3 §1). The suite is **red overall** until slice 4 — that is the queue draining,
not a broken build. No slice removes tests.
