# Spec 007 — Offers / LOI ⭐

> **Milestone M7** — `docs/design_implementation.md` Part 4 § *Milestone 7 — Offers / LOI (F8)*.
> The project's **first money surface** and its **first bilateral state machine**: every
> earlier state machine (`listing.status`, `access_request.status`) had one decider. An offer
> has two — a buyer proposes, and whoever did **not** propose the current terms decides.
> Security-critical (`docs/milestones.md` M1/M2/M3/M5/**M7**/M8/M10) — money + state-machine
> surface, per `docs/progress.md`'s ▶ NEXT ACTION note.

## FR references

| FR | What it requires |
|---|---|
| **FR-17** | Buyers can submit a structured offer/LOI (price, structure, contingencies, close date); sellers can accept, decline, or counter; both parties see offer history. |
| **F8** (MVP scope) | Simple offer/LOI form (structured terms, accept/decline) — "proves deal intent end-to-end." |
| **FR-13 / FR-14** (prerequisite, not re-satisfied here) | An offer requires the buyer already hold **approved** access (M5) — this spec consumes that gate, it does not re-decide it. |
| Constitution Article 2 #5 | "Audit what matters: offers and access decisions get timestamped event rows." |

**Scope fold-ins** (`docs/milestones.md` § Scope fold-ins → M7), each carried below as criteria:
counter-offer model (a new linked offer row vs. status mutation — decided in D1); sibling-offers
policy on accept (decided in D2, honored later by M12 on re-list); `GET /my/offers` (buyer) and
offers-per-listing (seller); offer **events**. Offer **expiry** is explicitly deferred — see
§ Out of scope.

---

## User stories

1. **As a buyer with approved access**, I want to submit a structured offer with a price and
   terms, so the seller can evaluate my interest in something concrete rather than a chat message.
2. **As a seller**, I want to accept an offer and have my listing marked "under offer"
   immediately, so I stop fielding competing offers while I move toward a deal.
3. **As a seller**, I want to decline an offer I'm not interested in, so the buyer knows to move on.
4. **As a seller**, I want to counter an offer with different terms, so we can negotiate toward
   something both sides accept, instead of a binary yes/no.
5. **As a buyer**, I want to respond to a seller's counter — accept, decline, or counter back —
   so the negotiation can actually converge instead of dead-ending the moment the seller replies.
6. **As a buyer**, I want to withdraw my own pending offer, so I'm not stuck committed to terms
   I no longer want to offer while waiting on a decision.
7. **As a seller**, I want every other pending offer on my listing to resolve automatically the
   moment I accept one, so I'm not left managing offers I have no intention of pursuing.
8. **As either party**, I want to see the full history of offers and counters in a negotiation,
   so I understand how the current terms were arrived at.

---

## Decisions

Recorded here for the same reason M5's and M6's were: an implementation choice with a real
alternative deserves a written reason, not just a diff. Flagged for owner sanity-check before
the failing tests are written — nothing here is a technical detail, each is a product policy.

**D1 — Counter-offer model: a new linked `Offer` row; decision rights follow the proposer, not
a fixed role.**
The fold-in names two options — "a new linked offer row vs. status mutation" — and demands one,
because today `countered` is behavior-free. A **status mutation** (storing the counter's terms
as extra nullable columns on the same row) was rejected: it conflates the buyer's original ask
and the seller's counter-ask in one row, exactly what this codebase's audit conventions avoid
(`security.md` § Audit & logging's own rule, learned at M5's D6 — "adding a transition can
invalidate an audit design that was correct for the old one"), and it silently loses a second
counter's terms the moment a third arrives. A **new linked row** (`parent_offer_id`) keeps every
historical proposal immutable and gives FR-17's "both parties see offer history" a direct,
literal answer: read every row in the chain.

That still leaves a real question the fold-in doesn't answer: **who may act on the counter's new
row?** Every binding doc (`design_implementation.md`, `security.md` §7, `testing_guide.md`,
`progress.md`) says "seller-only decisions" — but every one of them was written before this spec
existed to decide the counter-response mechanism, and all of them are describing the buyer's
**initial** offer (the documented, tested, money-moving path where the atomic accept lives).
None of them scope what happens when the seller is the one who just proposed terms. Two options:
**(a)** keep decisions permanently seller-only, and make the buyer's only response to a counter a
brand-new, unlinked `POST .../offers` call; **(b)** decision rights belong to **whoever did not
propose the current `submitted` row** — for a buyer-proposed offer that's the seller (matching
every doc's literal wording, unchanged), for a seller-proposed counter that's the buyer.

**(b) is what this spec implements.** (a) throws away the very chain D1 just decided to build —
the buyer would have to retype full terms after every counter, for no security benefit, since
"the counterparty of the proposer" is no more complex a check than `require_request_decider`
already is. `proposed_by_role` (`"buyer" | "seller"`, server-derived, never client-set) records
who authored a row's terms; the decision endpoints (`accept`/`decline`/`counter`) are usable only
by the *other* role. This is what makes `countered` behavior-full rather than decorative, and it
does not contradict any binding doc — none of them discuss the counter-response case at all.

**D2 — Sibling-offer policy: auto-decline, not leave-pending.**
The fold-in names the same two options it always does for this question: "auto-decline with
notification vs. leave pending." **Auto-decline** is chosen. Leave-pending was rejected because
it is dishonest, not merely simpler: the moment one offer is accepted the listing leaves `live`
(D1's accept transaction), so every other buyer's `submitted` offer is already unactionable — a
future accept attempt on it would 409 against the listing-status guard with no explanation ever
given to the buyer who placed it. Auto-decline gives every other party an honest, immediate,
auditable "no," in the **same transaction** as the accept, and leaves the `offer_event` row
(`action="auto_declined"`) that M8 is expected to notify from — the same relationship M3's
`listingevent` and M5's `accessrequestevent` already have to M8 (`milestones.md` § Scope
fold-ins → M8). M12 is told directly to honor this policy on re-list (`design_implementation.md`
M12: *"sibling offers follow the policy M7 decided"*).

**D3 — Offer creation is nested under the listing, not the flat `POST /offers` the build guide
sketches.** `design_implementation.md`'s Milestone 7 prose reads `POST /offers`; this spec ships
**`POST /listings/{id}/offers`** instead — the same class of deviation M5's D7 made from the
build guide's `GET /access-requests?listing_id=…`, and for the identical reason: putting the
listing id **in the path** lets a `Depends()`-based permission function key on it directly
(exactly how `require_private_access(listing_id: int, …)` and `require_signed_nda` already work),
rather than moving that lookup into the handler by hand. Decision and withdrawal routes stay flat
on the offer id (`POST /offers/{id}/accept`), unchanged from the build guide and matching the
existing `POST /access-requests/{id}/approve` shape exactly.

**D4 — `withdrawn` is a real, buyer-reachable state, not left decorative.**
Not named in `design_implementation.md`'s M7 prose (which lists only accept/decline/counter), but
already present in the project's own reference schema
(`docs/research/supabase_alternative.md`: `status in ('submitted','accepted','declined',
'countered','withdrawn')`) — this spec wires up a state that schema already anticipated rather
than inventing one. Scope is narrow and symmetric with D1: **only the current proposer of the
live `submitted` row may withdraw it** — the seller cannot withdraw the buyer's offer (that is
what `decline` is for), and the buyer cannot withdraw the seller's counter (that is what
`decline` is for, from the buyer's side).

**D5 — Existence-disclosure mirrors M5, not M2.** A listing that has never been published still
protects its existence: a non-owner probing `POST /listings/{id}/offers` on such a listing gets
**404**, identical to spec 005's D1. An offer id, like an access-request id (spec 005's
`require_request_decider`), carries no comparable secret — a missing or foreign offer id on any
decision/withdraw route gets a **uniform 403**, never distinguishing "doesn't exist" from
"exists but isn't yours."

**D6 — Structured terms are FR-17's own vocabulary, reused verbatim.** `price` (`Decimal` via the
existing `Money` type — never `float`, never a new money representation), `structure` (free text
— "all cash," "70/30 seller financing," etc.), `contingencies` (free text, optional), and
`proposed_close_date` (a date). The same four fields are the body of both offer creation and a
counter — symmetry that makes `OfferCreate`/`OfferCounter` the same shape under two names.

**D7 — At most one *active* (`submitted`) offer per `(listing, buyer)` at a time.** Unlike
`AccessRequest`'s permanent unique constraint (a decided pair is terminal forever), an offer
negotiation must allow many **historical** rows per pair — that is the whole point of the D1
chain. What it must not allow is two *concurrent* live proposals from the same buyer on the same
listing, which would make "the" offer an ambiguous phrase. Enforced as an application-level check
at creation (not a DB constraint, since old terminal rows must coexist with the schema), refusing
a second concurrent submission with `409 offer_already_active`.

---

## Acceptance criteria

Each GIVEN/WHEN/THEN below becomes **exactly one test** (constitution Article 3 §2).

### A — Creating an offer (FR-17, D3, D6, D7)

- **A1** GIVEN an approved buyer and a `live` listing, WHEN they `POST /api/listings/{id}/offers` with `price`, `structure`, `contingencies`, `proposed_close_date`, THEN 201; the offer exists with `status="submitted"`, `buyer_id` from the JWT, `proposed_by_role="buyer"`, `parent_offer_id` null; and an `offer_event` row exists (`action="submitted"`, `from_status=null`, `to_status="submitted"`).
- **A2** GIVEN a buyer with no access request, or one that is `requested`, `denied`, or `revoked`, WHEN they attempt to create an offer, THEN 403 `nda_access_required` — the same fact `require_private_access` already gates, surfaced the same way.
- **A3** GIVEN an approved buyer and a listing that is `draft`, `pending_review`, `paused`, `under_offer`, `rejected`, or `closed`, WHEN they attempt to create an offer, THEN 409 `listing_not_live`.
- **A4** GIVEN the listing's own owner, WHEN they attempt to create an offer on it, THEN 403 (self-dealing — they already have the data room; an offer on your own listing is meaningless).
- **A5** GIVEN a listing that has **never been published**, WHEN a non-owner attempts to create an offer, THEN 404 — identical to a listing that does not exist (D5).
- **A6** GIVEN a signed, approved buyer, WHEN they submit `status:"accepted"`, someone else's `buyer_id`, `proposed_by_role:"seller"`, and a forged `decided_at` in the body, THEN all are ignored — the row is `submitted`, owned by the caller, proposed by "buyer", undecided.
- **A7** GIVEN a buyer who already has a `submitted` offer on this listing, WHEN they attempt to create a second, independent offer on the same listing, THEN 409 `offer_already_active` (D7).
- **A8** GIVEN no credentials, WHEN `POST /api/listings/{id}/offers` is called, THEN 401.

### B — The seller's decision on a buyer-proposed offer ⭐ (FR-17, the atomic money path)

- **B1** GIVEN the listing's seller and a `submitted` offer proposed by the buyer, WHEN they `POST /api/offers/{id}/accept`, THEN 200; **both** `offer.status="accepted"` **and** `listing.status="under_offer"` are true — asserted together, the transaction test (`security.md` §7 M7, `testing_guide.md` §5 M7).
- **B2** GIVEN the same setup, WHEN they `POST /api/offers/{id}/decline`, THEN 200, `offer.status="declined"` (terminal); the listing is **unaffected** — still `live`.
- **B3** GIVEN a user who is neither the listing's owner nor the offer's buyer, WHEN they call accept/decline/counter/withdraw on it, THEN 403.
- **B4** GIVEN the buyer who proposed the offer, WHEN they attempt to accept, decline, or counter their **own** buyer-proposed offer, THEN 403 — decision rights belong to the counterparty, never the proposer (D1).
- **B5** GIVEN an offer already `accepted`, `declined`, `withdrawn`, or `countered`, WHEN any decision action is retried, THEN 409 `offer_already_decided`.
- **B6** GIVEN an admin who does not own the listing, WHEN they attempt to accept or decline, THEN 403 — admin is not special-cased on this boundary, exactly as `require_request_decider` refuses to special-case it (mirrors spec 005 C8).
- **B7** GIVEN the seller accepts, WHEN the audit table is read, THEN an `offer_event` row exists: `actor_id`=the seller, `action="accepted"`, `from_status="submitted"`, `to_status="accepted"`.
- **B8** GIVEN the listing's status has moved away from `live` between the offer's creation and the accept attempt (paused by the seller, or already flipped `under_offer` by a different offer's accept), WHEN accept is called, THEN 409 — the listing's current status is re-checked **inside** the accept transaction, not trusted from when the offer was created (`security.md` §6 race conditions).
- **B9** GIVEN no credentials, WHEN any decision or withdraw route is called, THEN 401.

### C — Counter-offer mechanics ⭐ (D1 — the fold-in's crown jewel)

- **C1** GIVEN the seller and a `submitted` buyer-proposed offer, WHEN they `POST /api/offers/{id}/counter` with new `price`/`structure`/`contingencies`/`proposed_close_date`, THEN 200; the original offer's status becomes `countered` (terminal); a **new** offer row exists with `parent_offer_id`=the original's id, `proposed_by_role="seller"`, `status="submitted"`, the seller's proposed terms, the same `listing_id`/`buyer_id`.
- **C2** GIVEN that counter exists, WHEN either party fetches the negotiation (the buyer's `GET /my/offers`, or the seller's `GET /my/listings/{id}/offers`), THEN **both** the original (`countered`) row and the new counter row appear — full history, nothing hidden (FR-17, user story 8).
- **C3** GIVEN the buyer, WHEN they `accept` the seller's counter (by its own id), THEN 200; that offer's status becomes `accepted` **and** the listing's becomes `under_offer` — proving `accept`'s atomic behavior is identical regardless of which party proposed the winning terms.
- **C4** GIVEN the buyer, WHEN they `decline` the seller's counter, THEN 200, status=`declined` (terminal) — the negotiation ends; no further row is created.
- **C5** GIVEN the buyer, WHEN they `counter` the seller's counter with new terms, THEN 200; the seller's counter row becomes `countered`; a **third** offer row is created with `parent_offer_id`=the seller's counter's id, `proposed_by_role="buyer"` — the chain extends past one round.
- **C6** GIVEN the seller, WHEN they attempt to accept, decline, or counter their **own** counter row (still `submitted`, awaiting the buyer), THEN 403 — the bilateral half of B4: decision rights on a seller-proposed row belong to the buyer, never the seller who proposed it.
- **C7** GIVEN a counter is made, WHEN the `offer_event` table is read, THEN it shows **two** rows: the original's `action="countered"` transition, and the new row's `action="submitted"` creation — the log records both halves of one action.

### D — Withdraw (D4)

- **D1** GIVEN the buyer and their own `submitted` (buyer-proposed) offer, WHEN they `POST /api/offers/{id}/withdraw`, THEN 200, `status="withdrawn"` (terminal).
- **D2** GIVEN the seller, WHEN they attempt to withdraw the buyer's `submitted` offer, THEN 403 — withdraw belongs to the proposer, the opposite rule from accept/decline/counter.
- **D3** GIVEN the buyer, WHEN they attempt to withdraw the seller's `submitted` counter (which the buyer did not propose), THEN 403 — symmetric to D2.
- **D4** GIVEN an already-decided offer, WHEN withdraw is attempted, THEN 409 `offer_already_decided`.

### E — The sibling-offer policy on accept (D2 — the fold-in's other crown jewel)

- **E1** GIVEN a listing with `submitted` offers from two independent buyers, WHEN the seller accepts buyer A's offer, THEN buyer B's offer is **auto-declined in the same transaction**: `status="declined"`, and an `offer_event` row exists with `action="auto_declined"`, `actor_id`=the accepting seller, `from_status="submitted"`, `to_status="declined"`.
- **E2** GIVEN a third buyer whose negotiation currently sits as a **seller-proposed counter** awaiting their response (`submitted`, `proposed_by_role="seller"`), WHEN a different buyer's offer is accepted, THEN this counter row is **also** auto-declined — the policy applies to every `submitted` row on the listing, regardless of who proposed it.
- **E3** GIVEN a buyer's offer that is already terminal (`declined`/`withdrawn`/`countered`) before the accept happens, WHEN the accept transaction runs, THEN that row is untouched — auto-decline only ever reaches rows currently `submitted`.
- **E4** GIVEN the accepted buyer's own prior history (e.g. an earlier `countered` row in their own chain), WHEN the accept happens, THEN that historical row is untouched — sibling policy resolves live offers, it never rewrites history.

### F — The buyer's own offers (`GET /api/my/offers`)

- **F1** GIVEN a buyer with offer threads on two listings, WHEN they fetch, THEN every row across both threads is returned (full history, FR-17).
- **F2** GIVEN two buyers with offers, WHEN buyer A fetches, THEN buyer B's rows never appear (caller-scoped in the query).
- **F3** GIVEN no credentials, WHEN `GET /api/my/offers` is called, THEN 401.

### G — The seller's queue (`GET /api/my/listings/{id}/offers`)

- **G1** GIVEN a seller with a listing that has offer threads from two buyers, WHEN they fetch that listing's offers, THEN both buyers' full threads are returned, each carrying the buyer's **profile** (mirrors spec 005's `BuyerProfile` — no verification status, same D5 deferral to M10).
- **G2** GIVEN a user who does not own that listing, WHEN they fetch its offers, THEN **404** — guarded by the existing `get_owned_listing`, so a draft's existence stays hidden exactly as spec 005's G2 already established.
- **G3** GIVEN a buyer's offer, WHEN the seller's queue response is inspected, THEN it carries **no buyer email** — a profile, not contact details (PII minimization, mirrors spec 005 G3).
- **G4** GIVEN no credentials, WHEN `GET /api/my/listings/{id}/offers` is called, THEN 401.

### Security & abuse

Derived from `docs/security.md` §7 (M7) + §6. These are the crown jewels.

- **S1** — *IDOR on decision routes.* GIVEN an offer belonging to neither the caller's own listing nor the caller's own buyer thread, WHEN acted on by guessing its id, THEN 403 — authorized through the offer's listing/buyer, never merely fetched by id (mirrors spec 005 S1).
- **S2** — *Schema leak.* GIVEN `OfferRead`/`OfferWithBuyer`, WHEN inspected, THEN neither can contain the counterparty's email or password hash **by schema**.
- **S3** — *Mass assignment on decision/counter bodies.* GIVEN the seller, WHEN they counter while sending a forged `decided_at`, `proposed_by_role`, or `buyer_id` in the body, THEN the server derives all three; none are read from the request.
- **S4** — *Token attacks reach the offer gates too.* GIVEN an expired or tampered token, WHEN any offer route is called, THEN 401 — never 403 (identity resolves first, mirrors spec 005 S6 / spec 006 S3).
- **S5** — *Enumeration.* GIVEN a sequence of offer ids the caller does not own, WHEN each is probed on a decision route, THEN the response is uniform and reveals no existence signal (D5).
- **S6** — *Race condition, explicit.* GIVEN two concurrent `accept` calls on two different `submitted` offers for the same listing, WHEN both commit, THEN exactly one succeeds (`200`, `under_offer`) and the other's listing-status re-check inside its own transaction fails it with `409` — never two accepted offers on one listing (`security.md` §6, extends B8).
- **S7** — *No leak on denial.* GIVEN any 403 from an offer gate, WHEN the body is inspected, THEN it carries the generic contract + machine code — no counterparty identity, no SQL, no stack.
- **S8** — *Self-dealing is symmetric and total.* GIVEN any `submitted` offer, WHEN its proposer attempts accept/decline/counter (B4/C6) **or** its counterparty attempts withdraw (D2/D3), THEN both are refused — decision rights and withdrawal rights are strict, disjoint opposites, never overlapping for the same row.

### Errors & failure modes

Per `docs/error_handling.md` (§1 contract: `{detail, code, request_id}`).

- **X1** — *422.* GIVEN a malformed offer/counter body (negative or missing `price`, missing `proposed_close_date`, wrong types), WHEN posted, THEN 422 with field-level detail.
- **X2** — *409 carries a machine code.* GIVEN `offer_already_decided`, `offer_already_active`, or `listing_not_live`, WHEN any fires, THEN the body's `code` is exactly that stable slug — the UI branches on it (error_handling.md §1's own worked example already names `offer_already_decided` and `listing_not_live`).
- **X3** — *500-safety.* Not a new numbered criterion, the same call M6 made: the generic catch-all handler (`main.py`) is already exercised by the `/_debug/boom` route from M1 and reused by every milestone since — an offer-specific forced error would test the same handler again, not new behavior. Recorded as a decision, not a gap.
- **X4** — *Frontend states.* GIVEN the offer panel, WHEN it is loading / no-offer-yet / `submitted` (mine) / awaiting-my-decision (a counter addressed to me) / `accepted` / `declined` / `withdrawn` / errored, THEN each renders distinctly and none crashes the page.

### Frontend (FR-17, F8)

- **J1** GIVEN a buyer with approved access and no active offer, WHEN they open the listing, THEN a "Make an offer" form is available.
- **J2** GIVEN a buyer with an active `submitted` offer on this listing, WHEN they view it, THEN the form is replaced by that offer's current status — never a duplicate form (mirrors D7).
- **J3** GIVEN the seller's offers view for one listing, WHEN it renders, THEN each buyer's thread renders as a chronological history (root offer → counters → final decision) with that buyer's profile.
- **J4** GIVEN the seller counters, WHEN the buyer next views the listing, THEN they see the counter's terms with accept/decline/counter actions available **on the counter**, not on the original, now-terminal offer.
- **J5** GIVEN any offer decision action fails with 409 (someone else already acted, or the listing left `live`), WHEN the response returns, THEN a toast surfaces the generic message and the view refetches — no crash, no silent no-op.

---

## Out of scope (deliberately deferred)

- **Offer expiry.** Named explicitly by the fold-in as acceptable to defer — an offer remains `submitted` indefinitely until a decision, a counter, or a withdrawal. Revisit once real negotiations show it's needed.
- **Notification delivery.** M7 writes `offer_event` rows (creation, every decision, every auto-decline) exactly as M3/M5/M6 write their own events — M8 is the milestone that projects notifications from them (`milestones.md` § Scope fold-ins → M8).
- **Deep due diligence, APA drafting, escrow.** `design_implementation.md`: "MVP stops here." `under_offer → sold` and the fell-through path back to `live` (honoring this spec's sibling policy on re-list) are M12's.
- **Re-opening a terminal offer.** `declined`/`withdrawn`/`countered`/`accepted` are all terminal for that row; there is no "un-decline" or "un-withdraw," matching `AccessRequest`'s own terminal philosophy (spec 005 D3) — a fresh `POST .../offers` (subject to D7) is the only way to restart, and only while the listing is still `live`.
- **Exhaustive-depth negotiation testing.** The chain (`parent_offer_id`) supports arbitrary rounds by construction; this spec tests at least two rounds (C1–C5) rather than an unbounded depth search — no artificial cap exists in the model, but proving deeper chains is not this milestone's job.
- **Currency / multi-currency.** Inherits M2's single-currency (USD) assumption; `price` is `Decimal` via the existing `Money` type, never a new representation.
