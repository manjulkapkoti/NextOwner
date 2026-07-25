# Spec 009 — M9: Watchlist

> **Milestone:** M9 — `docs/design_implementation.md` Part 4 § *Milestone 9 — Watchlist (F10)* ("an hour" of work: `POST /watchlist/{listing_id}` / `DELETE /watchlist/{listing_id}` toggle; `GET /watchlist` joins to listings for the "Watchlist" page).
> **Not security-critical** (`docs/security.md` §7 M9; the crown-jewel list is M1/M2/M3/M5/M7/M8/M10 — no independent `appsec-engineer` pass required). It still gets the standard **Security & abuse** treatment below: `security.md` §7's M9 line is "every operation caller-scoped; a user only ever sees/edits their own items."
> **Scope fold-ins read at spec time:** `docs/milestones.md` § Scope fold-ins has **no M9 bullet** — unlike M1/M2/M3/M5/M8/M10/M11, this milestone carries no additional scope beyond `design_implementation.md`'s one-line description. Nothing is imported from another milestone's fold-ins.

---

## 1. What this milestone is

A buyer favorites a listing into a personal watchlist — the cheapest, highest-engagement feature in the MVP feature list (F10: "Cheap, high-engagement"). Structurally this is the smallest kind of artifact the codebase already knows how to build: a caller-owned preference row, one rung simpler than M8's `SavedSearch` because there is no filter blob, no fan-out, and no per-user cap to justify. The whole milestone is add / remove / list, caller-scoped throughout.

It is deliberately **not** a notification surface — that loop belongs to M8's saved searches (FR-11). Watchlisting a listing tells the platform "keep this in front of me"; it triggers no alert, no email, no fan-out cost on anyone else's action.

## 2. FR references

| FR | What this milestone owes it |
|---|---|
| **FR-12** | Buyers can favorite listings into a watchlist. |
| **F10** (`docs/requirements.md` §1) | Watchlist/favorites — MVP feature, "cheap, high-engagement." |

## 3. User stories

- As a **buyer**, I want to favorite a listing while I'm still deciding, so that I can find it again without re-searching.
- As a **buyer**, I want to un-favorite a listing, so that my watchlist stays a useful shortlist rather than an ever-growing pile.
- As a **buyer**, I want my watchlist to show only listings I can still act on, so that I'm not misled into requesting access to something no longer available.
- As **any user**, I want my watchlist to be mine alone — nobody else's favorites show up in it, and mine never show up in theirs.

## 4. Decisions

- **D1 — `POST /watchlist/{listing_id}` is idempotent, not a duplicate-erroring create.** A watchlist entry is a boolean membership fact with no state machine and no meaning to lose on a repeat (contrast `access_request`, where a decided row is terminal and a duplicate is a real conflict — FR-13). The closer precedent is `POST /auth/nda`: "signing again is idempotent, timestamp unchanged" (`docs/testing_guide.md` M5 checklist; `security.md` §6 "Duplicate / idempotency"). A repeat `POST` for an already-watchlisted listing succeeds (200) without creating a second row — the natural behavior for a heart-icon toggle a client might call twice (a double-click, a stale UI, two open tabs).
- **D2 — Adding requires the target listing be currently `live`; missing or non-`live` → 404.** This reuses `get_public_listing`'s existing rule verbatim: "a non-`live` listing and a missing one raise the same 404 with the same message, so this route is not an existence oracle" (`backend/app/routers/listings.py`). A buyer cannot watchlist what they could never even view via public browse — `draft`, `pending_review`, `paused`, `closed`, `rejected`, `under_offer`, and `sold` are all "not found" here, exactly as they are at `GET /listings/{id}`. **This applies even to the listing's own seller** — `get_public_listing`'s comment is explicit that "the owner is not special-cased," and this route inherits that.
- **D3 — `GET /watchlist` only returns entries whose listing is currently `live`; a listing that later leaves `live` is silently omitted, not deleted.** Once a listing a buyer watchlisted is paused, closed, rejected-after-resubmit, put `under_offer`, or (later, M12) marked `sold`, it disappears from that buyer's watchlist view — the underlying row is untouched. If the listing returns to `live` (e.g., unpaused), it reappears automatically with no re-add. This mirrors the same existence-oracle rule D2 leans on and deliberately avoids inventing a new surface that would disclose a listing's internal lifecycle state (`pending_review` / `rejected` / `draft` are seller-side facts, not something a watching buyer is owed) — showing a raw status string here would be a new leak channel the M4 `ListingPublic` design specifically chose not to open (`ListingPublic`'s docstring: status is "excluded even though it is not private... the field would be a constant that tells a caller nothing while creating a channel for a future state to leak by accident"; here it would not even be constant). **Accepted trade-off:** a buyer gets no visible signal that an entry vanished or why. This is a deliberate simplification consistent with the milestone's "an hour" scope, not an oversight — revisit if usage shows buyers want a "no longer available" indicator instead.
- **D4 — No role restriction.** Any authenticated user — buyer, seller, or an account holding both roles (FR-2) — may watchlist any `live` listing, including their own. FR-12 is written from the buyer's perspective because that is the primary use case, not because it names an access rule, and the design doc doesn't ask for one. Inventing a buyer-only gate not asked for would be scope creep beyond this milestone's one-line description.
- **D5 — The new permission gate is keyed on `listing_id`, not the row's own surrogate id.** Unlike `get_owned_saved_search` (keyed on `saved_search_id`), the design doc's routes are `POST /watchlist/{listing_id}` / `DELETE /watchlist/{listing_id}` — the natural key of a watchlist entry is the pair `(user, listing)`, and the client never needs to know the row's own id. `get_owned_watchlist_entry(listing_id, ...)` looks up by `(user_id == caller, listing_id == path param)`.
- **D6 — No per-user cap.** `SavedSearch` caps at `saved_search_max_per_user` because every saved search costs one predicate evaluation on **every** publication (M8 spec A9 — a real scalability control). A watchlist entry triggers no fan-out and costs nothing on anyone else's action, so that justification doesn't transfer. No cap is added; this can be revisited if abuse is ever observed.
- **D7 — The table cascade-deletes on user erasure; no anonymize-in-place.** Per `docs/data_protection.md` §3's per-child-table question ("does erasure cascade or anonymize"), a watchlist entry carries no evidentiary or audit value — the same reasoning M8 used for `SavedSearch` ("a saved search is a convenience with no evidentiary value," `backend/app/routers/saved_searches.py`). Deleting a user's `WatchlistEntry` rows outright is safe and simpler than anonymizing a row nobody else's history depends on.

## 5. Acceptance criteria

> Each line below becomes **exactly one test** (constitution Article 3 §2), written failing first. Group letters: **W** watchlist core (add/remove/list) · **S** security & abuse · **X** errors & failure modes.

### W — Watchlist core (FR-12)

- **W1** — GIVEN an authenticated user and a `live` listing, WHEN they `POST /api/watchlist/{listing_id}`, THEN 201 and the listing appears in their `GET /api/watchlist`.
- **W2** — GIVEN a listing on a user's watchlist, WHEN they `DELETE /api/watchlist/{listing_id}`, THEN 204 and it no longer appears in their `GET /api/watchlist`.
- **W3** — GIVEN a user with several watchlisted `live` listings, WHEN they `GET /api/watchlist`, THEN all of them are returned, newest-added first.
- **W4** — GIVEN a listing already on a user's watchlist, WHEN they `POST /api/watchlist/{listing_id}` again, THEN 200 (not 201) and `GET /api/watchlist` still shows exactly one entry for it — no duplicate row (D1).
- **W5** — GIVEN a user, WHEN they `POST /api/watchlist/{listing_id}` for a `listing_id` that does not exist, THEN 404.
- **W6** — GIVEN a user, WHEN they `POST /api/watchlist/{listing_id}` for a listing that exists but is not `live` (parametrized over `draft`, `pending_review`, `paused`, `closed`, `rejected`, `under_offer`), THEN 404 for each (D2).
- **W7** — GIVEN a user who watchlisted a listing while it was `live`, WHEN the seller pauses it, THEN it no longer appears in that user's `GET /api/watchlist` (D3) — but the underlying entry is not deleted (verified by W8).
- **W8** — GIVEN the paused listing from W7 (omitted from the watchlist response), WHEN the seller makes it `live` again, THEN it reappears in the user's `GET /api/watchlist` without the user re-adding it (D3).
- **W9** — GIVEN a user, WHEN they `DELETE /api/watchlist/{listing_id}` for a listing they never watchlisted (but the listing exists and is `live`), THEN 404.
- **W10** — GIVEN a user, WHEN they `DELETE /api/watchlist/{listing_id}` for a `listing_id` that does not exist at all, THEN 404 with the same shape as W9 — no oracle distinguishing "never watchlisted" from "doesn't exist."
- **W11** — GIVEN a response from `GET /api/watchlist`, WHEN its schema is inspected, THEN it contains no `company_name`, `website_url`, `detailed_financials`, `owner_id`, or raw `status` field (schema-leak test, mirroring `ListingPublic`'s absent-field-set assertion at spec 004 S3).
- **W12** — GIVEN an authenticated seller-role account, WHEN they `POST /api/watchlist/{listing_id}` on another seller's `live` listing, THEN 201 (D4 — no role restriction).
- **W13** — GIVEN a seller whose own listing is currently `pending_review`, WHEN they `POST /api/watchlist/{their own listing_id}`, THEN 404 — D2 applies uniformly, even to the listing's own owner (mirrors `get_public_listing`'s "not even the person who wrote it").

### S — Security & abuse (`docs/security.md` §7 M9: "every operation caller-scoped")

- **S1** — GIVEN user A and user B both authenticated, WHEN A watchlists listing X, THEN X never appears in B's `GET /api/watchlist`.
- **S2** — GIVEN user A and user B have each independently watchlisted the same listing X, WHEN B calls `DELETE /api/watchlist/{X}`, THEN A's entry for X still exists (verified via A's `GET /api/watchlist`) — the delete is structurally scoped to the caller's own `(user_id, listing_id)` pair, so B's call cannot reach A's row by construction, not by a runtime check that could be forgotten.
- **S3** — GIVEN an unauthenticated visitor, WHEN they call `POST /api/watchlist/{id}`, `DELETE /api/watchlist/{id}`, or `GET /api/watchlist`, THEN 401 for all three.
- **S4** — GIVEN an authenticated user, WHEN they `POST /api/watchlist/{listing_id}`, THEN the created row's `user_id` is the caller's id from the JWT — there is no request body on this route, so `user_id` mass-assignment isn't merely rejected, it has no field to be assigned from (schema-level impossibility, the strongest form of the control `security.md` §2 asks for).

### X — Errors & failure modes (`docs/error_handling.md`)

- **X1** — GIVEN a non-numeric path segment, WHEN `POST /api/watchlist/{listing_id}` or `DELETE /api/watchlist/{listing_id}` is called with it, THEN 422.
- **X2** — GIVEN a forced internal error inside the watchlist router, WHEN any of its three routes is called, THEN the generic 500 contract is returned (`detail`, `request_id`) with no stack trace, SQL, or internal detail (reuses the global exception handler built at M1 — no new code, one new test).

> **No 409 criterion.** `error_handling.md` §7's minimum coverage asks for "any 409 illegal transition," but a watchlist entry has no state machine (constitution Article 2 #3 governs `listing.status` / `offer.status` / `access_request.status`; membership in a watchlist is a boolean fact, not a workflow). The honest statement is that no 409 applies here, recorded rather than manufactured to fill the checklist.

## 6. Out of scope (deliberately deferred)

- **No per-user cap** on watchlist size (D6) — the scalability justification `SavedSearch` has doesn't transfer; revisit only if abuse is observed.
- **No watchlist notifications or alerts.** That loop is FR-11 / M8's saved searches; favoriting a listing here triggers nothing for anyone.
- **No "unavailable" badge or indicator** when a watchlisted listing leaves `live` (D3) — it is silently omitted from the response. A status badge is a reasonable future addition but is not part of this milestone's one-line scope.
- **No bulk add/remove.** Single-listing toggle only, per the design doc's sketch.
- **No re-request / undo semantics** beyond D1's plain idempotency — unrelated to FR-13's post-MVP access-request re-request deferral, a different feature with a different state machine.
- **No frontend surfacing of *why* a listing disappeared** from the watchlist — consistent with D3.
