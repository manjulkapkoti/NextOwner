# Spec 005 — Platform NDA + access gate ⭐

> **Milestone M5** — `docs/design_implementation.md` Part 4 § *Milestone 5 — Platform NDA + access gate (F6)*.
> **The product's trust core.** `require_private_access` is the function this whole
> architecture exists to make possible (`design_implementation.md` §3.6), and
> `backend/tests/test_nda_gate.py` becomes the most important test file in the project
> (`CLAUDE.md` § Non-negotiable architecture rules #5).

## FR references

| FR | What it requires |
|---|---|
| **FR-6** | Listings are anonymous publicly; identifying details hidden until NDA acceptance. |
| **FR-13** | A buyer signs the standardized platform NDA **once** (click-wrap, timestamped on their account); thereafter they request access **per listing**, each request timestamped per buyer-listing pair. |
| **FR-14** | Sellers can approve/deny access requests and see buyer profile / verification status before approving. |
| **F6** (MVP scope) | Click-to-sign NDA that unlocks private details. |

**Scope fold-ins** (`docs/milestones.md` § Scope fold-ins → M5), each carried below as criteria:
revocation endpoint (`approved → revoked`, seller-only); `nda_version` recorded at signature;
the access-request list shows buyer profile + verification status; `GET /my/access-requests`
(buyer side). *Notification events are **not** emitted as rows — see § Out of scope.*

---

## User stories

1. **As a buyer**, I want to sign one platform NDA and then request access per listing, so that I prove my commitment once instead of re-signing at every door.
2. **As a buyer with approved access**, I want to read the private financials and download the data-room documents, so that I can evaluate the business for real.
3. **As a seller**, I want to see who is asking — their profile and verification status — and decide, so that I choose who carries my business forward rather than exposing it to anyone who clicks.
4. **As a seller**, I want to revoke access I already granted, so that a decision I regret is reversible.
5. **As the platform**, I want private data to be unreachable by anyone without a live approved request, through any sequence of actions, so that the core promise is a property of the system rather than of each endpoint's care.

---

## Decisions (owner approval requested — flagged at `--pause-after-spec`)

**D1 — A denied request returns `403`; an unpublished listing returns `404`.**
The two existence rules already in the codebase point in opposite directions, and M5 sits
exactly between them. M2 chose **404** for owner-scoped routes so an unpublished draft's
existence is never confirmed (`permissions.py:get_owned_listing`). M4's public route returns
**404** for a non-`live` listing for the same reason. But `security.md` §7 M5 requires **403**
for every denied gate state — and it must, because the frontend has to distinguish *"this
doesn't exist"* from *"ask for access"*; a 404 there would make the request-access CTA
unbuildable.

Both are right, for different listings. The rule: **once a listing has been published
(`published_at is not null`) its existence is public knowledge**, so denial is `403` and
carries a machine code the UI can branch on. A listing that has **never** been published is
still a secret, so a non-owner gets `404` — identical to a listing that does not exist.

*Consequence worth noting:* this keeps M2's `test_listing_download.py::test_e2` **passing
unchanged** (it uses a draft listing, and its author wrote *"buyer NDA-gated access is M5"*
in the assertion). The rule was chosen for the existence-disclosure reason, not to spare the
test — but a rule that leaves an adjacent milestone's forbidden-path test intact is a rule
that agrees with the code already shipped.

**D2 — An approved buyer keeps access when the listing leaves `live`.**
The gate is the access request, not the listing's status. `testing_guide.md` §5 M12 requires
*"the NDA gate still guards a `sold` listing's private data (approved buyer 200, everyone
else 403)"* — which only parses if approval survives the status change. A seller who pauses a
listing has not withdrawn a granted confidence; **`revoke` is the tool for that**, and it is
the only one.

**D3 — A decided request is terminal; re-requesting is `409`.**
The unique constraint is one row per `(listing_id, buyer_id)` — required by FR-13 and
`security.md` §6. So after `denied` or `revoked`, that buyer cannot re-request: the state
machine is strictly forward (`requested → approved|denied`, `approved → revoked`). Re-granting
after a revocation is **deferred** (§ Out of scope) rather than improvised here: it is a
product question (does a revoked buyer get a second chance, and who initiates?) and inventing
an answer inside the security milestone is how a gate grows a side door.

**D4 — Signing is idempotent and the version is frozen at signature.**
`nda_version` comes from server config, never the client. Re-signing does **not** re-stamp:
the first signature is the legal record (`data_protection.md` — retained legal record, same
class as `tos_accepted_at`). What happens when the NDA *text* changes and users hold v1
signatures is **out of scope** — flagged, not solved (§ Out of scope).

---

## Acceptance criteria

Each GIVEN/WHEN/THEN below becomes **exactly one test** (constitution Article 3 §2).

### A — Signing the platform NDA (FR-13)

- **A1** GIVEN an authenticated user who has never signed, WHEN they `POST /api/auth/nda`, THEN 200 and their `nda_signed_at` is stamped and `nda_version` records the server's current version.
- **A2** GIVEN a user who signed at time T with version V, WHEN they `POST /api/auth/nda` again, THEN 200 and `nda_signed_at` is **still T** and `nda_version` is **still V** (idempotent — D4).
- **A3** GIVEN no credentials, WHEN `POST /api/auth/nda`, THEN 401.
- **A4** GIVEN an authenticated user, WHEN they `POST /api/auth/nda` with `nda_signed_at` and `nda_version` in the body, THEN both are **ignored** and the server-derived values are stored (mass assignment — Article 2 #4).

### B — Requesting access to a listing (FR-13)

- **B1** GIVEN a signed buyer and a `live` listing they don't own, WHEN they `POST /api/listings/{id}/access-request`, THEN 201, a row exists with status `requested`, `buyer_id` taken from the JWT, and a timestamp.
- **B2** GIVEN a buyer who has **not** signed the platform NDA, WHEN they request access, THEN 403 with code `nda_not_signed` (the signature gates the request — `design_implementation.md` M5).
- **B3** GIVEN a buyer with an existing request for that listing, WHEN they request again, THEN 409 (unique constraint on `(listing_id, buyer_id)`).
- **B4** GIVEN a signed buyer, WHEN they request access sending `status: "approved"`, `buyer_id` of another user, and a `decided_at` in the body, THEN all three are ignored — the row is `requested`, owned by the caller, undecided.
- **B5** GIVEN a seller and their **own** listing, WHEN they request access to it, THEN 403 (self-dealing — `security.md` §6; the owner already has access, and a self-request is a self-approval path).
- **B6** GIVEN a signed buyer and a listing that has **never been published**, WHEN they request access, THEN 404 — the same response as a listing that does not exist (D1).
- **B7** GIVEN no credentials, WHEN `POST /api/listings/{id}/access-request`, THEN 401.

### C — The seller's decision (FR-14, + the revocation fold-in)

- **C1** GIVEN the listing's seller and a `requested` row, WHEN they `POST /api/access-requests/{id}/approve`, THEN 200, status `approved`, `decided_at` stamped.
- **C2** GIVEN the listing's seller and a `requested` row, WHEN they `POST /api/access-requests/{id}/deny`, THEN 200, status `denied`.
- **C3** GIVEN the listing's seller and an `approved` row, WHEN they `POST /api/access-requests/{id}/revoke`, THEN 200, status `revoked`.
- **C4** GIVEN a user who is neither the listing's seller nor the buyer, WHEN they approve the request, THEN 403.
- **C5** GIVEN the **buyer** who created the request, WHEN they approve their own request, THEN 403 (self-dealing — the decisive forbidden path of this milestone).
- **C6** GIVEN a request already `approved`, WHEN the seller approves it again, THEN 409 (already decided).
- **C7** GIVEN a request still `requested`, WHEN the seller revokes it, THEN 409 (`revoke` is legal only from `approved` — D3).
- **C8** GIVEN an **admin** who does not own the listing, WHEN they approve the request, THEN 403 — admin is not special-cased on this boundary; the seller alone decides who sees their data.

### D — The gate: `require_private_access` on private data ⭐

`GET /api/listings/{id}/private`. **Every state, per `security.md` §7 M5.**

- **D1** GIVEN the listing's owner, WHEN they read private data, THEN 200.
- **D2** GIVEN a buyer whose request is `approved`, THEN 200 and the payload carries `company_name`, `website_url`, `detailed_financials`.
- **D3** GIVEN a buyer whose request is `requested`, THEN 403 with code `nda_access_required`.
- **D4** GIVEN a buyer whose request is `denied`, THEN 403.
- **D5** GIVEN a buyer whose request was `approved` and is now `revoked`, THEN 403 — **revocation re-denies immediately** (`security.md` §6).
- **D6** GIVEN an authenticated user with **no request at all**, THEN 403.
- **D7** GIVEN no credentials, THEN 401.
- **D8** GIVEN a listing that has never been published and a non-owner caller, THEN 404 — not 403 (D1 in § Decisions).
- **D9** GIVEN an approved buyer and a listing the seller has since **paused/closed**, THEN still 200 — approval survives the listing's status change (D2 in § Decisions).
- **D10 — reachability (the corridor, not the door).** GIVEN every sequence of up to **three** actions drawn from {sign NDA, request access, seller approves, seller denies, seller revokes, seller pauses, seller resumes, seller closes}, WHEN private data is fetched **after every step**, THEN it returns 200 **only** when the caller is the owner or holds an `approved` request. *This exists because M3's forbidden-path tests each named one door and missed the corridor (`pause → edit → resume`), and M4's first attempt at the fix could not reach the corridor it claimed to test (constitution amendment 2026-07-19; `progress.md` § M4 carryover). Verify it by reverting the gate — it must fail.*

### E — The same gate on document downloads

- **E1** GIVEN an approved buyer, WHEN they `GET /api/listings/{id}/documents/{doc_id}`, THEN 200 and the file is served as an attachment.
- **E2** GIVEN a buyer whose request is `requested`, THEN 403 — the download path enforces the **same** gate, not a second copy of it.
- **E3** GIVEN a buyer whose access was `revoked`, THEN 403.
- **E4** GIVEN the owner, THEN 200 — M2's behaviour is preserved.
- **E5** GIVEN a non-owner and a never-published listing, THEN 404 — M2's `test_e2` still passes **unchanged** (D1).

### F — The buyer's own requests (`GET /api/my/access-requests`)

- **F1** GIVEN a buyer with requests across two listings, WHEN they fetch, THEN both are returned with their statuses.
- **F2** GIVEN two buyers with requests, WHEN buyer A fetches, THEN buyer B's rows never appear (caller-scoped).
- **F3** GIVEN no credentials, THEN 401.

### G — The seller's queue (`GET /api/access-requests?listing_id=…`, FR-14)

- **G1** GIVEN a seller with a listing that has two requests, WHEN they fetch for that listing, THEN both are returned with each buyer's **profile** (display name, budget, target industries, experience) and verification status.
- **G2** GIVEN a user who does not own that listing, WHEN they fetch its requests, THEN 404 (never-published) / 403 (published) per D1 — a seller's queue is not readable by anyone else.
- **G3** GIVEN a request from a buyer, WHEN the seller fetches the queue, THEN the response contains **no buyer email** — the seller sees a profile, not contact details (PII minimization, `data_protection.md`).

### Security & abuse

Derived from `docs/security.md` §7 (M5) + §6. These are the crown jewels.

- **S1 — IDOR on the decision route.** GIVEN a request belonging to another seller's listing, WHEN a seller approves it by guessing its id, THEN 403 — the row is authorized against the caller's ownership of *its* listing, not merely fetched by id.
- **S2 — IDOR on private data.** GIVEN an approved request for listing X, WHEN that buyer reads listing **Y**'s private data, THEN 403 — approval is per listing and never transfers.
- **S3 — Schema leak.** GIVEN the access-request response model, WHEN any endpoint returns it, THEN it cannot contain the buyer's email or password hash **by schema** (asserted against the model, not a sampled response).
- **S4 — Schema leak, private payload.** GIVEN the public listing route (`GET /api/listings/{id}`), WHEN M5's private model exists, THEN the public response still carries no private or identity field — M5 must not widen M4's boundary.
- **S5 — Mass assignment on decision.** GIVEN the seller, WHEN they approve while sending `status: "revoked"` and a forged `decided_at`, THEN the server derives both.
- **S6 — Token attacks reach the gate too.** GIVEN an expired or tampered token, WHEN private data is requested, THEN 401 (never 403 — the identity boundary resolves first).
- **S7 — Enumeration.** GIVEN a sequence of access-request ids the caller does not own, WHEN each is probed, THEN the response is uniform and reveals no existence signal.
- **S8 — No leak on denial.** GIVEN any 403 from the gate, WHEN the body is inspected, THEN it carries the generic contract + machine code — no company name, no owner identity, no SQL, no stack.

### Errors & failure modes

Per `docs/error_handling.md` (§7 contract: `{detail, code, request_id}`).

- **X1 — 422.** GIVEN a malformed decision body (wrong types), WHEN posted, THEN 422 with field-level detail.
- **X2 — 409 carries a machine code.** GIVEN an illegal transition (C6/C7), WHEN it 409s, THEN the body carries a stable `code` the UI can branch on.
- **X3 — 500-safety.** GIVEN a forced internal error inside the gate, WHEN private data is requested, THEN the generic 500 contract is returned — no stack, no SQL, no private field (`security.md` §6 info-leakage).
- **X4 — Frontend states.** GIVEN the listing detail page, WHEN the private section is loading / locked (403) / unlocked / errored, THEN each renders its own state; a 403 renders the request-access CTA rather than an error page.

### Frontend (FR-6, FR-13, FR-14)

- **J1** GIVEN a buyer who has not signed, WHEN they click "Request access", THEN the click-wrap NDA modal appears; confirming signs **and** creates the request in one flow.
- **J2** GIVEN a buyer who has signed, WHEN they click "Request access", THEN no modal appears and the listing shows a **pending** state.
- **J3** GIVEN a buyer with approved access, WHEN they open the listing, THEN the private section renders the real data and the documents are downloadable.
- **J4** GIVEN a seller, WHEN they open their listing's access requests, THEN each row shows the buyer profile + verification status with approve / deny actions (and revoke on approved rows).
- **J5** GIVEN the gate returns 403 `nda_access_required`, WHEN the page handles it, THEN the locked state renders — the global-401 handler is not triggered and nothing crashes.

---

## Out of scope (deliberately deferred)

- **Re-granting access after a revocation** (D3). The unique constraint makes a decided request terminal. Reversing that is a product decision — deferred rather than improvised inside the security milestone.
- **NDA re-signature on a version bump** (D4). Users holding a v1 signature keep access when the text moves to v2. Needs a legal answer before a technical one.
- **Notification rows.** M5 emits **no** `notification` table writes — that table is M8's to design (`milestones.md` § Scope fold-ins → M8, owner-approved 2026-07-19: *a table designed five milestones before its only consumer is speculative*). M5's `accessrequest` rows already carry actor, status and timestamps, which is what M8 will project from — the same relationship M3's `listingevent` has to M8.
- **Chat on approval.** `design_implementation.md` M6 says approving access also creates a `conversation` row — that belongs to M6, with the conversation model.
- **Rate limiting the access-request endpoint.** M1's limiter covers auth only; the public-browse gap is already recorded for deploy-hardening (`progress.md` carryover, `security.md` §9). Noted, not widened here.
- **The real NDA text.** A placeholder document with a version string; legal copy is the `legal-compliance` layer (`data_protection.md`).
