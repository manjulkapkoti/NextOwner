# Spec 003 — M3: Admin curation

> **Goal:** an admin reviews `pending_review` listings and approves or rejects them, with a reason. Approval is the **only** path to `live` — a seller can never publish themselves. Every decision leaves an immutable audit row.
>
> **Requirements:** FR-7 (pending-review → admin approves / rejects with reason), FR-21 (admin dashboard: curation queue), F3 (marketplace quality is the moat).
> **Scope fold-ins** (`docs/milestones.md`): `listing_event` audit table; notification events on approve/reject.
> **Security:** `docs/security.md` §7 — M3 row. **M3 is on the security-critical list** (`M1/M2/M3/M5/M7/M8/M10`) and gets an independent `appsec-engineer` pass. *It was added to that list because of this milestone:* M3 was originally absent, received the pass only because a stale note wrongly said otherwise, and that pass found a blocking curation bypass (see E5).

---

## Why this milestone matters

Curation *is* the product's quality promise. Every listing a buyer sees passed a human check, and the gate that makes that true is one endpoint. If a seller can reach `live` without an admin — through a status field on an update, a transition endpoint, or mass-assignment — the promise is void and the marketplace is a free-for-all. **The forbidden paths here are the feature.**

## User stories

**As an admin**, I see every listing waiting for review, so nothing sits unnoticed.
**As an admin**, I approve a listing and it becomes publicly visible.
**As an admin**, I reject a listing with a reason, so the seller knows what to fix.
**As a seller**, I can see why my listing was rejected.
**As anyone**, I cannot approve or reject anything unless I am an admin.

---

## Acceptance criteria

Each becomes exactly one test, written failing first. IDs are cited in test names (`test_a1_...`).

### A — The curation queue

- **A1** — GIVEN listings in several statuses, WHEN an admin calls `GET /api/admin/listings?status=pending_review`, THEN only `pending_review` listings are returned.
- **A2** — GIVEN no `status` filter, WHEN an admin calls `GET /api/admin/listings`, THEN listings of every status are returned (the admin view is not restricted to one state).
- **A3** — GIVEN a non-admin authenticated user, WHEN they call `GET /api/admin/listings`, THEN **403**.
- **A4** — GIVEN no credentials, WHEN `GET /api/admin/listings` is called, THEN **401**.
- **A5** — GIVEN the queue response, WHEN it is inspected, THEN each entry carries the seller-facing fields an admin needs to judge it (headline, type, asking price, status, created_at) **and** the private company detail (`company_name`, `website_url`) — an admin is explicitly authorised to see it, and cannot curate blind.

### B — Approve

- **B1** — GIVEN a `pending_review` listing, WHEN an admin `POST`s `/api/listings/{id}/approve`, THEN status becomes `live` and **200**.
- **B2** — GIVEN the same approval, WHEN the row is inspected, THEN `published_at` is stamped server-side.
- **B3** — GIVEN a `live` listing, WHEN an admin approves it again, THEN **409** and the status is unchanged.
- **B4** — GIVEN a `draft` listing (never submitted), WHEN an admin approves it, THEN **409** — only `pending_review` may be approved.
- **B5** — GIVEN a non-admin (including the listing's own seller), WHEN they call approve, THEN **403** and the status is unchanged.

### C — Reject

- **C1** — GIVEN a `pending_review` listing, WHEN an admin `POST`s `/api/listings/{id}/reject` with a reason, THEN status becomes `rejected` and **200**.
- **C2** — GIVEN a rejection, WHEN the audit row is inspected, THEN the reason is stored verbatim.
- **C3** — GIVEN a reject request with a missing or blank reason, WHEN it is sent, THEN **422** and the status is unchanged — a rejection without a reason is useless to the seller.
- **C4** — GIVEN a `live` listing, WHEN an admin rejects it, THEN **409** — only `pending_review` may be rejected.
- **C5** — GIVEN a non-admin, WHEN they call reject, THEN **403**.
- **C6** — GIVEN a rejected listing, WHEN its owner fetches it from their dashboard, THEN the rejection reason is visible to them.

### D — Audit trail

- **D1** — GIVEN an approval, WHEN `listing_event` is inspected, THEN one row records the actor, the action, `from_status`, `to_status` and a timestamp.
- **D2** — GIVEN a rejection, WHEN `listing_event` is inspected, THEN the row additionally carries the reason.
- **D3** — GIVEN a failed transition (409), WHEN `listing_event` is inspected, THEN **no row is written** — the audit records what happened, not what was attempted.
- **D4** — GIVEN two decisions on one listing, WHEN the events are read, THEN both rows survive in order — events are append-only and never updated in place.

### E — No seller path to `live` (the crown jewels)

- **E1** — GIVEN a seller updating their own listing, WHEN the request body includes `status: "live"`, THEN the field is ignored and the status is unchanged (mass-assignment).
- **E2** — GIVEN a seller, WHEN they call `POST /api/listings/{id}/submit` twice, THEN the second is **409** — submit does not become a publish loop.
- **E3** — GIVEN a seller whose listing is `pending_review`, WHEN they search the API surface, THEN no endpoint reachable with a seller identity sets `live` (asserted by attempting approve as the owner → **403**).
- **E4** — GIVEN an admin approving a listing they themselves own, WHEN they approve it, THEN it succeeds — admin authority is by role, not by ownership. *(Recorded deliberately: the alternative — forbidding self-approval — is a policy decision, not a security one, and is out of scope here.)*
- **E5** — GIVEN a `live` listing, WHEN its seller pauses it, edits its content, and resumes, THEN the listing does **not** return to `live` carrying unreviewed content — the edit sends it back to `pending_review`, and only an admin can publish it again.
  *Added mid-milestone, from the independent security review.* E1–E4 covered the paths that set `status` **directly** and missed the one that reaches `live` by composing three individually legal transitions. `pause`, `resume` and the edit-resets-review rule all predate M3 and were harmless while nothing could reach `live` at all — M3 is what turned them into a curation bypass. This is the criterion that makes the milestone's headline claim (*approval is the only path to `live`*) actually true.
- **E6** — GIVEN any status a seller can be in, WHEN **any sequence of up to two seller-reachable actions** is applied (submit / pause / resume / edit / close, in every order), THEN no sequence containing a successful edit leaves the listing `live`.
  *The invariant, rather than another door.* E1–E5 each name one forbidden path, which is why the E5 bypass survived: it was a path nobody had thought to name. E6 asserts the property instead — *a seller cannot publish content an admin has not seen* — over the whole reachable graph. Verified by reintroducing the E5 bug: E6 fails on `paused → edit → resume`. **Depth is two, not three** — an earlier draft of this criterion said three and the test never did, which is the over-claim this project keeps having to catch. Two is sufficient because `status` is the only state a transition depends on, so exhausting every single action from every reachable status proves the invariant inductively for any length. **`SELLER_ACTIONS` is hand-maintained**: a seller route added in M4+ is not covered until someone adds it there.

### F — Admin UI

- **F1** — GIVEN an admin visits `/admin`, WHEN the queue loads, THEN the pending listings are listed with their headline, price and status.
- **F2** — GIVEN a non-admin visits `/admin`, WHEN the route resolves, THEN they are redirected away and see no queue — the client gate is UX; the server gate (A3) is the boundary.
- **F3** — GIVEN an admin clicks reject, WHEN no reason has been entered, THEN the submit is blocked with an inline message rather than sending a request the server will 422.

---

## Errors & failure modes

Per `docs/error_handling.md`:

| Case | Code | Body |
|---|---|---|
| No / invalid token | 401 | generic `Not authenticated` |
| Authenticated but not admin | 403 | `Admin access required` |
| Listing does not exist | 404 | generic — no existence oracle for non-admins |
| Approve/reject from a status that forbids it | 409 | `Cannot go from X to Y` |
| Reject with no reason | 422 | Pydantic field error on `reason` |

The admin queue is the one place a 404 vs 403 distinction is safe to relax, because the caller is already known to be an admin.

## Security & abuse

Per `docs/security.md` §7 (M3) and §8:

- **`require_admin` reads `is_admin` from the DB row on every request**, never from the token — a token minted before a demotion must not retain admin power.
- **Default-deny:** both transition endpoints and the queue sit behind `require_admin`; nothing here is reachable by a plain authenticated user.
- **The client never sets status.** `status`, `published_at` and the actor on the audit row are all server-derived.
- **Reason is user input** — length-bounded at the boundary, stored as data, never interpolated into SQL, and rendered as text (it is written by an admin and read by a seller, so it is a stored-XSS surface on the frontend).
- **Forbidden-path tests are written before the happy path** (A3, A4, B5, C5, E1–E3).

## Out of scope (deferred)

- **Request-changes state.** FR-7 mentions "requests changes"; M3 ships approve/reject only. A third state needs its own transition rules and a seller resubmit flow — sequenced when the seller-side loop is built.
- **Notification delivery.** M8 owns the engine. **Open decision — see below.**
- **User management, reports, deal monitoring** (the rest of FR-21) — the admin *dashboard* beyond curation is unsequenced (`docs/milestones.md` ⚠ Trust & safety / admin ops).
- **Admin creation.** There is no endpoint to grant admin; it stays a manual DB flag, as in M1.

---

## Decision — notification table deferred to M8 (owner-approved 2026-07-19)

The M3 fold-in asked for notification events on approve/reject, "delivered when M8 lands." **M3 does not create a `notification` table.**

`listing_event` already records everything such a notification needs — actor, action, listing, reason, timestamp — so **M8 projects notifications from it** rather than M3 guessing M8's schema. Designing a table five milestones before its only consumer is speculative, and one written by M3 but read by nobody until M8 could not be verified by any test writable today.

**The obligation moves rather than disappears:** recorded in `docs/milestones.md` § Scope fold-ins → M8, where `/new-spec` will read it. That is the "amend, don't drift" rule — a fold-in may be re-sequenced by decision, never dropped by silence.

**What M3 owes M8 in exchange:** the event rows must be rich enough to project from. Hence `from_status` and `to_status` on every row (D1), the reason stored verbatim (D2), and no row on a failed transition (D3) — a notification must never be generated for something that did not happen.
