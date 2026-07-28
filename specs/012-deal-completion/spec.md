# Spec 012 — Deal completion (M12)

> **Milestone:** M12 — Deal completion (`docs/design_implementation.md` Part 4, *Milestone 12*; appended by the
> 2026-07-16 gap review). The last numbered milestone: M7 deliberately stopped at `under_offer`, and this
> finishes the listing state machine — `under_offer → sold` (with the final price server-derived from the
> accepted offer) and `under_offer → live` when the deal falls through.
>
> **FR references:** **FR-8** (sellers can edit, pause, mark under-offer, or close listings — the `sold` half
> completes the lifecycle), **FR-17** (both parties see offer history — the accepted offer reaches a truthful
> terminal state on both paths), **FR-21** *(partial)* (admin deal monitoring — this milestone supplies the
> `listing_event` / `offer_event` rows a deal-monitoring view would read; no admin UI here).
> **FR-18** (deal room, APA, escrow) and **FR-20** (closing-fee invoicing) stay **post-MVP** — see § Out of scope.
>
> **Security focus:** `docs/security.md` §7 M12 + §6 (illegal transitions, IDOR, mass assignment, races,
> info leakage). **Scope fold-ins:** `docs/milestones.md` § Scope fold-ins records M12 as *"a new milestone,
> not a fold-in"* — its scope is the table row + Part 4 + `testing_guide.md` §5, all read at spec time.

---

## 1. Why this milestone exists

The close is where the business model lives (the success fee recognizes at close — research synthesis law #6),
and without `sold` rows the future comps corpus (`agentic_scope.md` proposal F) never accumulates. Today a
listing that reaches `under_offer` is stuck there forever: there is no transition out, so a completed sale is
invisible to the platform and a collapsed deal strands the listing off-market with an `accepted` offer that
can never be superseded.

**What makes this milestone different from its neighbours:** it is the first one to add transitions to a state
machine that *already has an audit design*. Article 2 #5's corollary applies directly — *"adding a transition
to a state machine can invalidate an audit design that was correct for the old one"* — so every decision below
re-asks "what does this overwrite?" rather than assuming M3's and M7's answers still hold.

It is also the first milestone since M2 to **re-open a closed question about an existing route**: the edit
guard. See D8, which is a defect this spec found rather than a feature it adds.

---

## 2. Decisions

**D1 — Two transitions, one new listing state.** `under_offer → sold` (terminal) and `under_offer → live`
(re-list). Nothing else moves: `sold` is terminal in both directions — there is no un-sell, and no path from
any other state into `sold`. `sold` already sits in `routers/listings.py`'s `_EDIT_LOCKED` constant, written
at M2 in anticipation; this milestone is what finally makes that constant reachable, and S9 is the test that
proves it was right.

**D2 — No new `permissions.py` function. `get_owned_listing` is the boundary, reused verbatim.**
Both routes are owner-scoped listing transitions — precisely what `submit`, `pause`, `resume` and `close`
already pass through. Inventing a `require_deal_closer` that re-derived "is this the owner" would make the
constitution's *one function per trust boundary* rule mean **less**, not more: the boundary here is not new,
only the transition behind it is. This is the fourth milestone to add no gate (after M3, M4 and M11), and as
at M11 the honest answer is that reusing the existing one is correct.

**D3 — The refusal for a non-owner is `404`, not the `403` `security.md` §7 names.**
`get_owned_listing` returns 404 for both *"doesn't exist"* and *"exists but isn't yours"*, deliberately, so a
listing's existence is never confirmed to a stranger (spec 002 decision, inherited by every seller-only route
since). §7's M12 line says *"anyone else → 403"*, written in 2026-07-16 as generic shorthand for "refused",
before the convention existed. **404 is the stronger property**, so this spec keeps the convention and
**corrects `security.md` §7 in slice 7** with a dated note — a deliberate supersession, recorded, not a silent
deviation. The 401-for-unauthenticated half of §7 is unchanged (S7).

**D4 — The final sale price is a stored column on `Listing`, derived server-side at the moment of sale.**
`final_price` + `sold_at`, both nullable, both written only inside `mark-sold`. The request body **cannot**
influence either (S1) — Article 2 #4. Considered and rejected: deriving the price on read by joining the
`completed` offer. Storing wins for two reasons. (a) The comps corpus wants the sale as a **fact on the
listing**, not as a join whose meaning depends on the offer table's future shape. (b) A re-listed listing can
be sold again — after which "the completed offer" is no longer unique, and a read-time derivation would have
to encode "the most recent one", which is exactly the kind of implied ordering that goes wrong silently. The
column records the answer at the one moment it is unambiguous.

**D5 — Two new *offer* terminal states: `completed` (the deal closed) and `lapsed` (it fell through).**
Two questions, answered separately:

*Why must the accepted offer move at all?* Because of an invariant this milestone creates and must protect:
**at most one `accepted` offer per listing at a time.** M7's partial unique index only covers
`status = 'submitted'`, so it does not help here. If a re-listed listing kept its old offer `accepted` and
then sold to someone else, the listing would carry two `accepted` offers and no rule to say which one closed
the deal — and `mark-sold`'s price derivation (D4) would become ambiguous. Moving the offer is what keeps
that derivation total.

*Why not reuse `declined`?* Because the seller **accepted** it. Recording a collapsed deal as "declined"
destroys precisely the distinction the audit rows exist to preserve, and poisons the comps corpus that is
half this milestone's justification: a `declined` offer means "the counterparty said no", a `lapsed` one means
"both parties said yes and it still didn't close". Those are different business facts and a later analysis
that conflates them is wrong. `completed`/`lapsed` are additive terminal states — M7's partial unique index
on `submitted` is unaffected, and every existing status guard is a positive check against a named state, so
no existing route changes behaviour.

**D6 — Re-list does **not** resurrect the siblings that were auto-declined on accept.**
M7's D2 chose auto-decline over leave-pending precisely because it is *"an honest, immediate, auditable no"* —
and M8 notified those buyers that their offer was declined. Un-declining them would retract a decision the
platform already communicated, and would revive priced commitments their authors may no longer stand behind.
A re-listed listing goes back to the market clean; interested buyers submit fresh offers (B4, B5). This is the
"M12 honors the policy M7 decided" instruction in `design_implementation.md` Part 4, and honoring it means
leaving those rows exactly where M7 put them.

**D7 — `published_at` is not restamped on re-list, and re-list does not go through re-review.**
`published_at` records *first* publication (M3) and is not a "currently live since" field. Skipping re-review
is safe by the same invariant `resume` relies on: the content an admin approved is the content that goes back
up — which is true **only because of D8 below.** Without D8 this bullet would be false, which is how D8 was
found.

**D8 — Editing is forbidden while a listing is `under_offer` (409 `listing_under_offer`). ⚠ This is a defect
in shipped code, not a new feature.**
`update_listing` today locks edits only for `_EDIT_LOCKED = {closed, sold}`, and sends a listing back to
`pending_review` only when its status is in `("live", "paused")`. `under_offer` is in neither set — so on
`main`, a seller with a listing under offer can rewrite its headline, description and financials with **no
re-review and no notice to the buyer they are mid-deal with.** That is already a bait-and-switch against the
buyer whose offer was accepted on the old terms. M12 makes it strictly worse: `relist` would then put the
edited, never-re-reviewed listing straight back on the public marketplace — the exact hole M2's
anti-bait-and-switch rule exists to close.

The fix is to refuse the edit, not to re-review it: adding `under_offer` to the re-review trigger would move a
listing to `pending_review` while an accepted offer stands, breaking the deal state to fix a content problem.
A listing under offer has a counterparty relying on its terms; the terms hold until the deal resolves. Note
this is **not** the same as adding `under_offer` to `_EDIT_LOCKED` — that constant means "terminal, cannot
edit *or* re-transition", and `under_offer` must still transition (that is this whole milestone). It is a
separate, narrower guard.

*This is the "corridor between the doors" class the constitution names (Article 3 §2, 2026-07-19): every
individual door here had a negative test, and the corridor `under_offer → edit → relist → live` had none
because no two milestones owned it.*

**D9 — Both paths notify the buyer, and the recipient is role-based, not proposer-based.**
Two `_TEMPLATES` entries (`offer_completed`, `offer_lapsed`) and two entries in `notify_offer`'s recipient
map. Every M7 action resolves its recipient from `proposed_by_role` because either party can propose; these
two do not, because **only the seller can cause them** — the recipient is always the buyer, whether or not
the buyer authored the accepted offer's terms (an accepted seller-counter is still the seller's deal to
close). This is the first offer action whose recipient is fixed by role, and the code says so at the line.
No new machinery: M8's projection carries no private payload, so these rows are as harmless-when-stale as
every other (E3).

**D10 — No public "under offer" or "sold" flag. Spec 004's open musing is closed as "no".**
`ListingPublic`'s docstring says *"M12 may add a deliberate public 'under offer' flag"*. This spec declines.
Browse returns `live` rows only, so a sold listing simply leaves the marketplace — the desired behaviour is
already the default. Adding `status` back to the public schema would re-open the leak channel M4 closed by
construction, in exchange for a signal nobody has asked for. Recorded here so the musing stops being an open
question, and the docstring is corrected in slice 7.

**D11 — Erasure & data protection: nothing new is personal.** `final_price` and `sold_at` are business facts
about a listing, not PII, and are absent from every public schema (G1). The two new `offer_event` /
`listing_event` actions carry ids, status strings and a timestamp — audit-exempt on erasure under the existing
rule (`docs/data_protection.md`), same as every event row since M3. No new PII field, no new person-referencing
table.

---

## 3. User stories

1. **As a seller** whose deal has closed, I want to mark my listing sold, so that the platform records the
   sale at its true price and my listing leaves the market.
2. **As a seller** whose deal fell through, I want to put my listing back on the market in one click, so that
   a collapsed deal doesn't cost me my listing.
3. **As the buyer** whose offer was accepted, I want to be told when the seller closes or abandons the deal,
   so that I am never silently dropped from a negotiation I am party to.
4. **As the buyer** who signed an NDA and was approved, I want my access to a sold listing's data room to keep
   working, so that a status change doesn't silently revoke what I was granted.
5. **As the platform**, I want every close and collapse to leave an audit row with the price and the states it
   overwrote, so that the deal history is reconstructable and a future comps corpus has something true to read.

---

## 4. Acceptance criteria

> Each numbered criterion becomes **exactly one test** (constitution Article 3 §2). Backend tests live in
> `backend/tests/test_deal_completion.py` (A–E) and `backend/tests/test_deal_completion_security.py` (S);
> frontend in `app/src/components/DealActions.test.tsx` (F).

### A — Marking a deal sold (FR-8, D1, D4)

- **A1** GIVEN the seller of an `under_offer` listing, WHEN they `POST /api/listings/{id}/mark-sold`, THEN
  200, the listing's `status` is `"sold"`, and `sold_at` is stamped with a UTC timestamp.
- **A2** GIVEN an `under_offer` listing whose accepted offer's price is `123456.78` and whose `asking_price`
  is a different value, WHEN the seller marks it sold, THEN the recorded `final_price` equals the **accepted
  offer's** price exactly, to the cent — never the asking price (D4, Article 2 #4).
- **A3** GIVEN the same listing, WHEN the seller marks it sold, THEN the accepted offer's `status` becomes
  `"completed"` and its `decided_at` is preserved from the original acceptance (the close does not rewrite
  when the offer was accepted).
- **A4** GIVEN a listing sold via a seller-proposed **counter** that the buyer accepted, WHEN the seller marks
  it sold, THEN `final_price` is that counter's price — the derivation follows the accepted row, not the
  original buyer-proposed root of the thread (D4, M7 D1's chain).
- **A5** GIVEN a sold listing, WHEN its owner fetches `GET /api/my/listings/{id}` and `GET /api/my/listings`,
  THEN both carry `final_price` and `sold_at` with the recorded values.
- **A6** GIVEN a listing that has never been sold, WHEN its owner fetches it, THEN `final_price` and `sold_at`
  are both `null` (the columns default empty and are written only by `mark-sold`).

### B — The deal fell through: re-list (FR-8, D1, D6, D7)

- **B1** GIVEN the seller of an `under_offer` listing, WHEN they `POST /api/listings/{id}/relist`, THEN 200
  and the listing's `status` is back to `"live"`.
- **B2** GIVEN the same listing, WHEN it is re-listed, THEN the accepted offer's `status` becomes `"lapsed"`
  (D5) — not `declined`, not left `accepted`.
- **B3** GIVEN a re-listed listing, WHEN an anonymous visitor calls `GET /api/listings`, THEN it appears in
  public browse again, and `published_at` is **unchanged** from its original publication (D7).
- **B4** GIVEN a listing whose accept auto-declined two sibling offers (M7 E1), WHEN the seller re-lists it,
  THEN both siblings are still `"declined"` and no `offer_event` row was written for them — re-list never
  revives a decision (D6).
- **B5** GIVEN a re-listed listing, WHEN a different approved buyer submits an offer and the seller accepts
  it, THEN the listing is `under_offer` again and **exactly one** offer on that listing has status
  `"accepted"` — the at-most-one-accepted invariant D5 exists to protect.
- **B6** GIVEN a re-listed-then-resold listing, WHEN the seller marks it sold, THEN `final_price` is the
  **second** accepted offer's price and `sold_at` reflects the second close.

### C — Illegal transitions and atomicity (409, `security.md` §6)

- **C1** GIVEN a listing in any state other than `under_offer` (`draft`, `pending_review`, `live`, `paused`,
  `closed`, `rejected`, `sold`), WHEN its owner calls `mark-sold`, THEN 409 `invalid_transition` for every one
  of them *(one parameterized test)*.
- **C2** GIVEN a listing in any state other than `under_offer` (same list), WHEN its owner calls `relist`,
  THEN 409 `invalid_transition` for every one — including `sold`, so there is no un-sell *(one parameterized
  test)*.
- **C3** GIVEN an `under_offer` listing, WHEN a `mark-sold` is refused with 409 (because a concurrent request
  already moved it), THEN the listing's status, the offer's status, `final_price`, `sold_at` and the two event
  tables are **all** untouched — a refused attempt writes nothing (the rule `_transition` and `_record`
  already keep: the log records what happened, not what was tried).
- **C4** GIVEN an `under_offer` listing whose accepted offer has been force-set to a terminal state (a data
  anomaly reachable only by seeding), WHEN the seller calls `mark-sold`, THEN 409 `no_accepted_offer`, the
  listing stays `under_offer`, and the response is the generic error contract — never a 500 and never a
  `NoneType` traceback.
- **C5** GIVEN two concurrent `mark-sold` requests on the same `under_offer` listing, WHEN both run, THEN
  exactly one returns 200 and the other 409, exactly one `listing_event` and one `offer_event` row exist, and
  `final_price` is written once (compare-and-swap, mirroring M7's accept — `security.md` §6 races).

### D — Audit rows (Article 2 #5, FR-21)

> *What does each transition overwrite?* `mark-sold` overwrites `listing.status` (losing `under_offer`) and
> `offer.status` (losing `accepted`); `relist` overwrites the same two. Both losses are recoverable only from
> an event row, so both event rows earn their place. `final_price`/`sold_at` are **written once and never
> overwritten**, so they need no audit row of their own — recording them would be a copy, not a preservation.

- **D1** GIVEN a successful `mark-sold`, THEN a `ListingEvent` exists with `action="sold"`,
  `from_status="under_offer"`, `to_status="sold"`, and `actor_id` = the seller's id taken from the JWT.
- **D2** GIVEN a successful `mark-sold`, THEN an `OfferEvent` exists for the accepted offer with
  `action="completed"`, `from_status="accepted"`, `to_status="completed"`, `actor_id` = the seller.
- **D3** GIVEN a successful `relist`, THEN a `ListingEvent` exists with `action="fell_through"`,
  `from_status="under_offer"`, `to_status="live"` (the action name `specs/003-admin-curation/plan.md`
  predicted for this milestone).
- **D4** GIVEN a successful `relist`, THEN an `OfferEvent` exists with `action="lapsed"`,
  `from_status="accepted"`, `to_status="lapsed"`.
- **D5** GIVEN a `relist` refused with 409 (wrong state) and a `mark-sold` refused with 404 (wrong caller),
  THEN neither event table gained a row.

### E — Notifications (M8 projection, D9)

- **E1** GIVEN a successful `mark-sold`, THEN the buyer on the accepted offer has one unread notification of
  type `offer_completed`, and the seller who performed the action has none.
- **E2** GIVEN a successful `relist`, THEN the buyer on the (now `lapsed`) offer has one notification of type
  `offer_lapsed`, and the buyers whose siblings were auto-declined at accept time receive **nothing new** —
  their negotiation ended at M7's accept (D6).
- **E3** GIVEN a deal closed on a listing whose accepted offer was a **seller-proposed counter**, WHEN the
  seller marks it sold, THEN the notification still goes to the **buyer** — the recipient is fixed by role,
  not by `proposed_by_role` (D9).

### F — Frontend (the seller's deal actions)

- **F1** GIVEN the seller viewing their `under_offer` listing's offers page, THEN a "Mark as sold" and a
  "Deal fell through" action are rendered, together with the price that will be recorded, shown **read-only**
  and taken from the accepted offer (never an editable input — D4 at the UI layer).
- **F2** GIVEN a listing in any other status (`live`, `sold`, `paused`), THEN neither action is rendered.
- **F3** GIVEN the seller clicking "Mark as sold", THEN a confirmation dialog appears naming the price and
  stating that the action is final, and **no request is sent** until it is confirmed.
- **F4** GIVEN that dialog, WHEN the seller cancels, THEN no request is sent and the listing is unchanged.
- **F5** GIVEN a confirmed "Mark as sold", WHEN the request succeeds, THEN the page shows the `Sold` status
  chip, the recorded final price, and neither action any longer.
- **F6** GIVEN a confirmed action that the server refuses with 409, THEN the inline error contract message is
  rendered (`docs/error_handling.md`) and the page does not crash or lose the offers list.
- **F7** GIVEN a request in flight, THEN the confirmation dialog's confirm and cancel actions are both
  disabled, and a second click on the confirm sends no second request.
  > *Amended during the build (2026-07-28).* This originally read "both actions are disabled" — the wrong noun
  > for a modal confirm flow. While the request is in flight the dialog is open, and MUI's modal already makes
  > the two trigger buttons behind it inert and `aria-hidden`, so asserting on *them* tests the modal rather
  > than the guard. The property the criterion protects — **no double submit** — is unchanged and is pinned by
  > the exactly-one-`fetch` assertion; only the element it addresses moved. Recorded rather than silently
  > edited, per `/run-milestone`'s "fix the spec deliberately and say so".

---

## 5. Security & abuse

> `docs/security.md` §7 (M12) + §6. Every criterion here is a **forbidden-path** test, written before the
> happy path (`testing_guide.md` §1 — the crown jewels).

- **S1 — Mass assignment.** GIVEN the seller of an `under_offer` listing, WHEN they `POST .../mark-sold` with
  a body of `{"final_price": "1.00", "sold_at": "1999-01-01T00:00:00Z", "status": "live", "owner_id": 999}`,
  THEN 200 and every one of those fields is ignored: `final_price` is the accepted offer's price, `sold_at` is
  server-now, `status` is `sold`, `owner_id` is unchanged (Article 2 #4; §6 mass assignment).
- **S2 — IDOR, mark-sold.** GIVEN a second seller with their own listings, WHEN they call `mark-sold` on
  someone else's `under_offer` listing, THEN **404** (D3) and the target listing is untouched.
- **S3 — IDOR, relist.** GIVEN the same stranger, WHEN they call `relist` on another seller's listing,
  THEN 404 and the listing is untouched.
- **S4 — The counterparty cannot close or unwind the deal.** GIVEN the buyer whose offer was accepted, WHEN
  they call `mark-sold` or `relist` on that listing, THEN 404 for both — being party to the deal grants no
  rights over the seller's listing (§6 self-dealing).
- **S5 — Admin does not widen here.** GIVEN an admin who does not own the listing, WHEN they call either
  route, THEN 404. Unlike M10's verification gate, `is_admin` grants nothing on this boundary: curation is the
  admin's, closing a deal is the seller's. *(Asserted explicitly because M10 established the opposite
  precedent for a different gate, and an unstated rule is the one that drifts.)*
- **S6 — Enumeration.** GIVEN a listing id that does not exist at all, WHEN a caller invokes either route,
  THEN the status code and response body are **byte-identical** to S2's "exists but isn't yours" refusal.
- **S7 — Unauthenticated.** GIVEN no `Authorization` header, WHEN either route is called, THEN 401 — and with
  a tampered/expired token, 401 (§6 token attacks).
- **S8 — The NDA gate is not weakened by a terminal state.** GIVEN a `sold` listing, THEN an approved buyer
  still reads `GET /api/listings/{id}/private` with 200, a signed-NDA-but-unapproved buyer still gets 403, and
  a revoked buyer still gets 403 — the gate is the access request, not the listing's status
  (`permissions.py`'s own comment; `testing_guide.md` §5 M12; spec 005 D9).
- **S9 — Document downloads on a sold listing.** GIVEN a `sold` listing with a document, THEN the approved
  buyer downloads it (200) and a stranger does not (403) — the terminal state changes neither answer.
- **S10 — A sold listing leaves the public surface entirely.** GIVEN a `sold` listing, WHEN an anonymous
  visitor calls `GET /api/listings` and `GET /api/listings/{id}`, THEN it is absent from the page and the
  detail route returns 404 — identical to any other non-`live` listing, so `sold` is not a new existence
  oracle (D10).
- **S11 — Schema leak.** GIVEN the public browse and detail responses for any listing, THEN `final_price`,
  `sold_at` and `status` are absent from `ListingPublic` **by schema** — asserted against the model's field
  set, not just against one response body (spec 004 S3's pattern, D10).
- **S12 — Edits are refused while under offer.** ⚠ GIVEN the seller of an `under_offer` listing, WHEN they
  `PUT /api/listings/{id}` changing the headline and financials, THEN 409 `listing_under_offer` and **no field
  changed** — closing the corridor D8 describes.
- **S13 — The corridor itself, end to end.** GIVEN an `under_offer` listing, WHEN the seller attempts
  `edit → relist → GET /api/listings/{id}`, THEN the content an anonymous visitor sees after the re-list is
  byte-identical to the content the admin approved — a reachability test over the *sequence*, asserting the
  invariant rather than the endpoint (Article 3 §2, 2026-07-19).
- **S14 — A sold listing is frozen.** GIVEN a `sold` listing, WHEN its owner attempts `PUT`, `submit`,
  `pause`, `resume` or `close`, THEN 409 for every one — `_EDIT_LOCKED`'s `sold` entry, written at M2 and
  unreachable until now, finally proven correct *(one parameterized test)*.
- **S15 — 500-safety.** GIVEN a forced internal failure inside `mark-sold` (monkeypatched commit), WHEN the
  seller calls it, THEN the response is the generic error contract — no stack trace, no SQL, no table or
  column name — and the listing is left `under_offer` (§6 info leakage; `error_handling.md`).

---

## 6. Errors & failure modes

| Condition | Code | `code` | Surface |
|---|---|---|---|
| No / invalid / expired token | 401 | `unauthorized` | both routes (S7) |
| Not the owner, or no such listing | 404 | `not_found` | both routes (S2–S6) |
| Listing not `under_offer` | 409 | `invalid_transition` | both routes (C1, C2) |
| No `accepted` offer on an `under_offer` listing | 409 | `no_accepted_offer` | `mark-sold` (C4) |
| Edit attempted while `under_offer` | 409 | `listing_under_offer` | `PUT /api/listings/{id}` (S12) |
| Lost the compare-and-swap race | 409 | `invalid_transition` | `mark-sold`, `relist` (C5) |
| Internal failure | 500 | generic contract | both routes (S15) |

Neither route takes a request body, so there is no 422 path of its own — a body sent anyway is ignored
(S1), which is the stronger property and the one worth testing. **Frontend states:** loading/disabled while
in flight (F7), inline 409 rendering (F6), and no optimistic status update — the chip changes only on the
server's response, because an optimistic `sold` that the server refused would be a lie about money.

**Mocked-vendor failure modes** (escrow decline / dispute, `error_handling.md` §5) are **not** touched — no
vendor is involved on either path. See § Out of scope.

---

## 7. Out of scope

- **The optional extensions `design_implementation.md` marks "fine to defer":** the invoice artifact on
  completion (L2), the asset-transfer checklist state machine (L3), and mocked escrow states
  (`initiated → funded → released`). These are **FR-18** (deal room) and **FR-20** (closing-fee invoicing),
  both explicitly post-MVP in `requirements.md`. Deferring them is a re-affirmation of an existing decision,
  not a new one.
- **A public "under offer" / "sold" flag** — declined outright, see D10.
- **A buyer-side "the deal closed" screen.** The buyer is notified (E1–E3) through M8's existing inbox; no new
  buyer surface is built. The notification is the deliverable.
- **Admin deal-monitoring UI** (FR-21's dashboard half). This milestone writes the event rows such a view
  would read; building the view is not in the table row and would be an unscoped admin surface.
- **The Playwright E2E golden path extended to "sold"** (`testing_guide.md` §5). The golden-path script is
  **Phase D** work and does not exist yet; M12 lands the `sold` transition it will need. What M12 *does* do is
  retire the "(once M12 lands)" caveat in that checklist, so the line stops deferring to a milestone that has
  shipped (slice 7).
