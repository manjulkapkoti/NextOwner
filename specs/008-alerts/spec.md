# Spec 008 — M8: Notifications engine + saved searches & alerts + account lifecycle ⭐

> **Milestone:** M8 — `docs/design_implementation.md` Part 4 § *Milestone 8 — Notifications engine + saved searches & alerts (F9)*.
> **Security-critical** (`docs/security.md` §7 M8, constitution Article 3 §3). This milestone adds **auth surface**: a password-reset token is account takeover if it leaks. It gets an independent `appsec-engineer` pass before the PR.
> **Scope fold-ins read at spec time:** `docs/milestones.md` § Scope fold-ins → M8 (all four bullets, including the ⚠ consequence note).

---

## 1. What this milestone is

Three previously-deferred things land together, because they are one machine:

1. **The notifications engine** — M3/M5/M6/M7 each left **event rows** behind (`listingevent`, `accessrequestevent`, `Message`, `offerevent`) and deliberately shipped **no** notification code. M8 builds the `notification` table and **projects notifications from those events**, exactly as the 2026-07-19 amendment sequenced it.
2. **Saved searches & alerts** (FR-11) — buyers save filters; a listing going `live` fans out to the buyers whose searches match.
3. **Account lifecycle** — password reset + email verification, moved here from M1 (2026-07-17) **because they *are* email**, and M8 is the milestone that builds the email channel.

The load-bearing sentence for the whole milestone: **a notification is a delivery record, not a new source of truth.** It carries a type, some ids, and a server-composed title made of public data — never private content. Every click-through is re-gated by the boundary that already owns that data.

## 2. FR references

| FR | What this milestone owes it |
|---|---|
| **FR-11** | Buyers save a search; new matching listings trigger an alert on publication. |
| **FR-22** | All notification templates are **centrally managed and event-driven** — one `notify()` service, one template map (`notifications._TEMPLATES`), no per-endpoint ad-hoc messaging. |
| **FR-16** | The **email fallback** half of buyer↔seller messaging (M6 shipped the realtime half and left this). |
| **FR-8** | **Partially** — "state changes propagate to search and alerts". M8 wires the `pending_review → live` publication path only; pause / close / under-offer emit no alert type in this milestone. |
| **FR-1** | Self-serve password reset. **A deliberate extension, not a literal match:** FR-1's text covers register/sign-in and token lifetime and never names recovery. The work is anchored here because `milestones.md` § Scope fold-ins → M8 moved it from M1 as *"these flows **are** email"*. Recorded rather than assumed, so a reader checking FR-1 is not surprised. |
| **NFR Scalability** | **Partially** — see D12. The per-user cap (A9) and the dispatch seam (D9) bound *per-subscriber* cost and keep SMTP off the request thread, but `fan_out_saved_searches` still scans every saved search in the system on each publication. Handling a real spike needs the queue D9 leaves room for; this milestone does not claim it. |

## 3. User stories

- As a **buyer**, I want to save a search and be alerted when a matching business is listed, so that I don't have to check the marketplace daily.
- As a **buyer**, I want one inbox showing access decisions, replies, and offer activity, so that the deal doesn't stall because nobody happened to log in.
- As a **seller**, I want to be told when a buyer requests access, sends a message, or makes an offer, so that I can respond while the buyer is still interested.
- As **any user**, I want to reset my password by email, so that losing it doesn't lose me the account.
- As **the platform**, I want addresses verified before I send bulk mail to them, so that a typo'd or hostile address can't turn NextOwner into a spam source.

## 4. Decisions

- **D1 — A notification is a delivery record, not an audit row.** It is mutable (`read_at`), per-recipient, and safely deletable. The three event tables stay the immutable audit trail (constitution Article 2 #5). `notification` must never become a second, drifting copy of what happened — it is a *projection*, and the audit rows remain the fact.
- **D2 — Notification rows carry no private payload.** Type + ids + a title composed from **public** fields only (`listing.headline` is on `ListingPublic`; `company_name` is not). Message bodies, offer prices, and private-table fields never enter the row. This is what makes the inbox safe **after a revocation**: a stale row's click-through hits `require_private_access` / `conversation_role_for` and is refused (S1). Copying content into the notification would have quietly built a bypass around M5's crown-jewel gate.
- **D3 — Recipient derivation is the trust boundary.** One `notify()` service derives the recipient from the **domain object** (`listing.owner_id`, `access_request.buyer_id`, the conversation's other party, the offer's counterparty), server-side, in one place. No caller passes a recipient; no request body influences one.
- **D4 — Two token tables, not one with a `purpose` column.** `PasswordResetToken` and `EmailVerificationToken` are separate, so **cross-purpose redemption is structurally impossible** rather than test-dependent. This follows the codebase's established precedent of *duplicating rather than sharing when a boundary is at stake* — `conversation_role_for` duplicates the NDA-gate query on purpose so M6 cannot regress M5. H5/H6 pin it anyway, because a structural guarantee nobody has seen fail is still worth a test.
- **D5 — Reset tokens are SHA-256 hashed at rest, not bcrypt.** The token is 256 bits from `secrets.token_urlsafe(32)`; there is no low-entropy guess space for a slow KDF to defend, so bcrypt would add latency to every redemption and buy nothing. Hashing at all is the point: a leaked DB must not yield usable tokens (`security.md` §7 M8 — "treat it like a password, not an id").
- **D6 — Email verification gates outbound *notification* email, and nothing else yet.** Transactional account mail (verify, reset) always sends — otherwise verification could never bootstrap. Notification mail requires `email_verified`; unverified users still get the full in-app inbox. This answers `security.md` §7's "say what verification gates — an unenforced flag is decoration" **without** a cross-milestone blast radius, and it is the correct anti-abuse rule on its own terms (never bulk-mail an unconfirmed address). Gating listing creation or access requests on verification is **deferred, unowned, and must be a deliberate later scoping call** — recorded here so it is not assumed to exist.
- **D7 — Alerts are forward-only.** A saved search matches listings approved *after* it was created; it never backfills. B8 pins it. Backfill would mean a new search instantly dumping the whole marketplace into an inbox.
- **D8 — A password reset does not revoke outstanding JWTs.** Access tokens are stateless with no blocklist, so a token minted before the reset stays valid until it expires (≤ 60 min). **This is a known gap, owned — not ignored:** it closes with the refresh-token + revocation work already scoped in `security.md` §9. Stated here so an appsec reader finds it recorded rather than discovering it.
- **D9 — Dispatch sits behind two ports.** `EmailSender` (Protocol) / `SmtpEmailSender` / `NullEmailSender` for *what* sends, and `Dispatcher` / `ThreadDispatcher` / `InlineDispatcher` for *where the send runs* — both shaped exactly like `RateLimiterBackend` and `ChatBroker`, the codebase's existing "external or per-instance effect behind a swappable interface" pattern. Tests swap in `RecordingEmailSender` (defined in `conftest.py`, since it is a test double rather than product code) plus `InlineDispatcher`, so no socket is ever opened and assertions never race a worker thread. Replacing either with a real queue is constructing a different object, not editing a caller.
- **D10 — No per-user notification preferences at MVP.** Every projected event produces an in-app notification. A preferences matrix (per-type, per-channel, digest) is a real product need and explicitly deferred.
- **D12 — the fan-out runs *inside* the approve transaction, not in a `BackgroundTask`.** `design_implementation.md` Part 4's M8 sketch says "add a **BackgroundTask**"; this spec deliberately does not, and the sketch is annotated to match. Two reasons. **(a) Correctness:** a background task runs after the response, outside the transaction, so a publication that rolled back could still have alerted every matching buyer about a listing that is not live. Sharing the endpoint's transaction makes that impossible. **(b) It changes nothing observable** — a plain call and a `BackgroundTask` are both complete by the time a test asserts, so the tests read identically either way; `testing_guide.md` §5's "assert right after the approve call" still holds, now because nothing is deferred at all. The cost is real and **not** fully mitigated: the matcher scans every saved search in the system on each publication, so a very large subscriber base slows an admin's approve. A9 caps how many searches *one user* holds, which bounds per-subscriber cost but not the total; the honest mitigation is the queue D9 leaves room for, and moving the fan-out onto it later is a change of *executor*, not of design.
- **D11 — `POST /api/auth/reset-password` takes the token in the body, never the query string.** `security.md` §7 M8 forbids putting the token anywhere a proxy records; a query param lands in access logs, `Referer` headers, and browser history. S7 pins it.

## 5. Acceptance criteria

> Each line below becomes **exactly one test** (constitution Article 3 §2), written failing first. Group letters: **A** saved searches · **B** alert fan-out · **C** event projection · **E** inbox · **F** email channel · **G** password reset · **H** email verification · **J** frontend · **S** security & abuse · **X** errors. (**D** is reserved for the Decisions above.)

### A — Saved searches (FR-11)

- **A1** — GIVEN an authenticated buyer, WHEN they `POST /api/saved-searches` with a name and a valid filter set, THEN 201 and the stored row's `user_id` is the caller's id from the JWT.
- **A2** — GIVEN a saved search owned by buyer A, WHEN buyer B calls `GET /api/saved-searches`, THEN the response does not contain A's row.
- **A3** — GIVEN a buyer with two saved searches, WHEN they `GET /api/saved-searches`, THEN both are returned, newest first.
- **A4** — GIVEN a saved search owned by buyer A, WHEN buyer B calls `DELETE /api/saved-searches/{id}`, THEN 404 and A's row still exists.
- **A5** — GIVEN a buyer's own saved search, WHEN they `DELETE` it, THEN 204 and it no longer appears in their list.
- **A6** — GIVEN an authenticated buyer, WHEN they `POST` a saved search whose body also sets `user_id` to another user, THEN the stored row's `user_id` is still the caller's (mass-assignment ignored).
- **A7** — GIVEN an authenticated buyer, WHEN they `POST` a saved search whose filters contain an unknown field name, THEN 422 and no row is stored.
- **A8** — GIVEN an unauthenticated visitor, WHEN they `POST /api/saved-searches`, THEN 401.
- **A9** — GIVEN a buyer already holding the maximum number of saved searches, WHEN they create one more, THEN 409 `saved_search_limit` (the fan-out cost per publication is bounded per user).
- **A10** — GIVEN an authenticated buyer, WHEN they `POST` a saved search whose `min_price` exceeds its `max_price`, THEN 422 and no row is stored.

### B — Saved-search alert fan-out (FR-11, FR-8)

- **B1** — GIVEN a buyer's saved search matching type `saas` under 200k, WHEN an admin approves a listing with those attributes, THEN a `listing_matched` notification exists for that buyer.
- **B2** — GIVEN a buyer's saved search that does not match the listing, WHEN an admin approves it, THEN no notification is created for that buyer.
- **B3** — GIVEN two different buyers whose saved searches both match, WHEN an admin approves the listing, THEN each buyer has exactly one `listing_matched` notification.
- **B4** — GIVEN a buyer's matching saved search, WHEN an admin **rejects** the listing instead, THEN no `listing_matched` notification is created (only publication fans out).
- **B5** — GIVEN the seller who owns the listing also holds a saved search that matches it, WHEN the listing is approved, THEN the seller receives no `listing_matched` notification for their own listing.
- **B6** — GIVEN a matching saved search, WHEN the listing is approved, THEN the notification row contains no `company_name`, no `website_url`, and no owner identity.
- **B7** — GIVEN a listing already alerted once that was edited back to `pending_review`, WHEN it is approved a second time, THEN the same buyer does not receive a duplicate `listing_matched` notification for that listing.
- **B8** — GIVEN a listing that went live before a buyer created their saved search, WHEN nothing further happens, THEN that buyer has no notification for it (alerts are forward-only, D7).

### C — Projecting notifications from M3/M5/M6/M7 events (FR-22, FR-16)

- **C1** — GIVEN a listing in `pending_review`, WHEN an admin approves it, THEN a notification exists for the listing's owner and for nobody else.
- **C2** — GIVEN a listing in `pending_review`, WHEN an admin rejects it with a reason, THEN the owner's notification carries that rejection reason.
- **C3** — GIVEN a live listing, WHEN a buyer requests access, THEN a notification exists for the listing's owner and none for the requesting buyer.
- **C4** — GIVEN a pending access request, WHEN the seller approves it, THEN a notification exists for the buyer.
- **C5** — GIVEN a pending access request, WHEN the seller denies it, THEN a notification exists for the buyer.
- **C6** — GIVEN an approved access request, WHEN the seller revokes it, THEN a notification exists for the buyer.
- **C7** — GIVEN a conversation with both parties, WHEN one sends a message, THEN a notification exists for the other party and none for the sender.
- **C8** — GIVEN an approved buyer on a live listing, WHEN they submit an offer, THEN a notification exists for the seller and none for the buyer.
- **C9** — GIVEN a submitted buyer offer, WHEN the seller counters it, THEN a notification exists for the buyer.
- **C10** — GIVEN a submitted offer, WHEN its counterparty accepts it, THEN a notification exists for the party who proposed those terms.
- **C11** — GIVEN a submitted offer, WHEN its counterparty declines it, THEN a notification exists for the party who proposed those terms.
- **C12** — GIVEN two competing submitted offers on one listing, WHEN the seller accepts one, THEN the auto-declined sibling's buyer also receives a notification.
- **C13** — GIVEN a buyer's submitted offer, WHEN the buyer withdraws it, THEN a notification exists for the seller.
- **C14** — GIVEN a message whose text is a distinctive secret string, WHEN its notification is created, THEN the stored notification does not contain that text (D2).
- **C15** — GIVEN any notification about a listing, WHEN the row is inspected, THEN it contains no field drawn from `ListingPrivate` (D2).

### E — The in-app inbox (FR-22)

- **E1** — GIVEN a user with several notifications, WHEN they `GET /api/notifications`, THEN only their own are returned, newest first.
- **E2** — GIVEN a notification belonging to user A, WHEN user B calls `GET /api/notifications`, THEN A's row is absent from B's response.
- **E3** — GIVEN a user with both read and unread notifications, WHEN they `GET /api/notifications?unread=true`, THEN only the unread ones are returned.
- **E4** — GIVEN a user's unread notification, WHEN they `POST /api/notifications/{id}/read`, THEN `read_at` is set and the row no longer appears under `?unread=true`.
- **E5** — GIVEN a notification belonging to user A, WHEN user B posts `/read` on its id, THEN 404 and A's row remains unread.
- **E6** — GIVEN a user with unread notifications, WHEN they `GET /api/notifications/unread-count`, THEN the count covers only their own rows.
- **E7** — GIVEN two users each holding unread notifications, WHEN one calls `POST /api/notifications/read-all`, THEN only that caller's rows become read.
- **E8** — GIVEN a user, WHEN they `GET /api/notifications?limit=500`, THEN 422 (pagination is capped, `security.md` §6 DoS surface).
- **E9** — GIVEN an unauthenticated visitor, WHEN they `GET /api/notifications`, THEN 401.
- **E10** — GIVEN a notification already marked read, WHEN the caller marks it read again, THEN 200 and `read_at` is unchanged (idempotent).

### F — The email channel (FR-22, FR-16, D9)

- **F1** — GIVEN a recipient whose address is verified, WHEN an event produces a notification for them, THEN exactly one email is dispatched to that address.
- **F2** — GIVEN a recipient whose address is **not** verified, WHEN an event produces a notification for them, THEN the in-app notification exists and **no** notification email is dispatched (D6).
- **F3** — GIVEN a new registration, WHEN it succeeds, THEN a verification email is dispatched even though the address is unverified (transactional mail is exempt, D6).
- **F4** — GIVEN an `EmailSender` that raises on send, WHEN the domain action runs, THEN the action still returns its normal 2xx and the in-app notification still exists (email failure never fails the business action).
- **F5** — GIVEN any dispatched email, WHEN its body and subject are inspected, THEN they contain no password hash, no JWT, and no `ListingPrivate` field.
- **F6** — GIVEN the test suite, WHEN any email-producing endpoint is exercised, THEN no SMTP connection is attempted (the port is swapped for `RecordingEmailSender`).
- **F7** — GIVEN the production dispatcher and a transport that blocks, WHEN a queued notification is committed, THEN the committing thread returns without waiting for the send to finish.

> **F7 was added during the branch review**, after the inline pass found that `SmtpEmailSender.send` — a blocking socket call with a 5-second timeout — was reachable from the **`async` WebSocket handler** via `notify_message` → `commit` → `after_commit`. One slow SMTP server would have stalled every live chat socket on that worker, against the sub-second delivery NFR, and it also gave `forgot-password` a timing side-channel (the known-address path paid an SMTP round trip the unknown-address path did not — the enumeration-by-timing `security.md` §6 names, which M1's login already defends with its dummy hash). **The class of question the other F criteria were not asking:** they all assert *that* a message is sent, and none asks *where the send runs*. F7 is that question.

### G — Password reset (security-critical)

- **G1** — GIVEN a registered user, WHEN they `POST /api/auth/forgot-password` with their address, THEN 202 and a reset email is dispatched to them.
- **G2** — GIVEN an address belonging to nobody, WHEN they `POST /api/auth/forgot-password`, THEN the response status and body are identical to G1's and no email is dispatched (no user enumeration).
- **G3** — GIVEN a valid reset token, WHEN it is posted to `/api/auth/reset-password` with a new password, THEN 200 and the user can log in with the new password.
- **G4** — GIVEN a reset token already redeemed once, WHEN it is redeemed a second time, THEN it is rejected and the password is unchanged (single-use).
- **G5** — GIVEN a reset token past its expiry, WHEN it is redeemed, THEN it is rejected and the password is unchanged.
- **G6** — GIVEN a reset token issued for user A, WHEN it is redeemed while naming user B's address, THEN B's password is unchanged (the token alone names its user).
- **G7** — GIVEN an issued reset token, WHEN the stored row is inspected, THEN it holds a hash and the raw token value appears nowhere in the database (D5).
- **G8** — GIVEN a user holding two outstanding reset tokens, WHEN one is redeemed, THEN the other is also invalidated.
- **G9** — GIVEN repeated `POST /api/auth/forgot-password` calls past the configured limit, WHEN the next one arrives, THEN 429 (it mails a third party on demand).
- **G10** — GIVEN a full forgot-password → reset cycle, WHEN the captured application logs are inspected, THEN the raw token appears in none of them.
- **G11** — GIVEN a valid reset token, WHEN it is posted with a password below the minimum length, THEN 422 and the password is unchanged.
- **G12** — GIVEN a syntactically valid but nonexistent reset token, WHEN it is redeemed, THEN the response is identical to the expired-token response (no oracle for which tokens exist).
- **G13** — GIVEN a soft-deleted (anonymized) user's address, WHEN `forgot-password` is called for it, THEN the same 202 is returned and no token row is created.
- **G14** — GIVEN an address belonging to nobody, WHEN `forgot-password` is called, THEN the request still performs the cost-equalizing work that the known-address path would have done (no timing oracle).

> **G14 was added by the independent appsec pass.** G2 pins that the *response* is identical; it says nothing about how long the response took. The known-address path hashes a token and does a DB write-and-commit that the unknown path skipped entirely, so latency answered the question the body refuses to — the enumeration-by-timing `security.md` §6 names, and which M1's login already defends against with `_DUMMY_HASH`. `milestones.md` § Scope fold-ins → M8 binds this endpoint to *"the same rule as M1's login"*, and that rule has always included timing. **The test spies on the equalization rather than measuring a clock**: a wall-time assertion would be flaky in CI, while the real failure mode is a later refactor quietly deleting the call.

### H — Email verification

- **H1** — GIVEN a newly registered user, WHEN they `GET /api/auth/me`, THEN `email_verified` is false.
- **H2** — GIVEN a valid verification token, WHEN it is posted to `/api/auth/verify-email`, THEN 200 and the user's `email_verified` becomes true.
- **H3** — GIVEN a verification token already redeemed, WHEN it is redeemed again, THEN it is rejected (single-use).
- **H4** — GIVEN a verification token past its expiry, WHEN it is redeemed, THEN it is rejected and `email_verified` stays false.
- **H5** — GIVEN a valid **password-reset** token, WHEN it is posted to `/api/auth/verify-email`, THEN it is rejected and `email_verified` stays false (D4 — no cross-purpose redemption).
- **H6** — GIVEN a valid **verification** token, WHEN it is posted to `/api/auth/reset-password`, THEN it is rejected and the password is unchanged (D4).
- **H7** — GIVEN an authenticated unverified user, WHEN they `POST /api/auth/resend-verification`, THEN a new email is dispatched and their previous verification token no longer redeems.
- **H8** — GIVEN an authenticated user, WHEN they send `email_verified: true` to `PUT /api/profile`, THEN the field is ignored and remains false (mass-assignment).
- **H9** — GIVEN an already-verified user, WHEN they `POST /api/auth/resend-verification`, THEN 409 and no email is dispatched.

### J — Frontend

- **J1** — GIVEN a signed-in user with notifications, WHEN the inbox page renders, THEN each notification appears and unread ones are visually distinguished.
- **J2** — GIVEN a signed-in user with unread notifications, WHEN the nav bar renders, THEN it shows an unread badge whose count comes from the API.
- **J3** — GIVEN the inbox showing an unread notification, WHEN the user clicks it, THEN it is marked read and the app navigates to the linked resource.
- **J4** — GIVEN a signed-in user with no notifications, WHEN the inbox renders, THEN an empty state is shown rather than a blank panel.
- **J5** — GIVEN the notifications request is still in flight, WHEN the inbox renders, THEN a loading state is shown.
- **J6** — GIVEN the notifications request fails, WHEN the inbox renders, THEN an error state is shown and no crash escapes the boundary.
- **J7** — GIVEN the saved-search form, WHEN a buyer submits valid filters, THEN the new search appears in their list.
- **J8** — GIVEN the forgot-password page, WHEN any address is submitted, THEN the same confirmation message is shown (the UI must not leak what the API refuses to).
- **J9** — GIVEN the reset-password page, WHEN the API returns a 422 for the new password, THEN the message is displayed inline on the field.
- **J10** — GIVEN the verify-email page, WHEN the token is rejected, THEN a failure state with a resend affordance is shown rather than a success message.

### S — Security & abuse (the crown jewels)

- **S1** — GIVEN a buyer holding a message notification whose access was then revoked, WHEN they follow it to the conversation, THEN 403 — the inbox is not a bypass of the live membership re-check (D2).
- **S2** — GIVEN a buyer holding a `listing_matched` notification, WHEN they request that listing's `/private` without an approved access request, THEN 403 `nda_access_required` — an alert grants no access.
- **S3** — GIVEN any notification response, WHEN its schema is inspected, THEN it declares no other user's identity fields and no private listing fields (schema-leak test).
- **S4** — GIVEN an authenticated client, WHEN they attempt to create a notification directly over the API, THEN no such route exists — notifications are server-created only.
- **S5** — GIVEN an authenticated buyer, WHEN they save a search whose filter names a `ListingPrivate` column such as `company_name`, THEN 422 — the alert engine can never match on private text (M4's rule, extended).
- **S6** — GIVEN a client supplying `recipient_id` or `read_at` on any M8 write route, WHEN the request is processed, THEN the server-derived values are used and the client's are ignored.
- **S7** — GIVEN a reset attempt passing the token as a query-string parameter, WHEN it is called, THEN it is refused — the token is accepted in the body only (D11).
- **S8** — GIVEN an attacker probing notification ids, WHEN they request a nonexistent id and another user's id, THEN both responses are identical (no existence oracle).
- **S9** — GIVEN an address already registered, WHEN an attacker registers that address again, THEN 409 `email_taken` and **no** verification email is dispatched to the existing owner (registration cannot be used to mail a third party).
- **S10** — GIVEN every code path that creates a notification, WHEN a walk over a reachable sequence of real transitions exercises them and the invariant is re-asserted after every step, THEN no notification ever exists whose recipient is not a party to the underlying object (the reachability invariant, in `test_nda_gate.py` D10's tradition — a linear walk rather than D10's BFS, deliberately: re-checking after each step buys the same corridor coverage far more cheaply than a sequence product).

### X — Errors & failure modes (`docs/error_handling.md`)

- **X1** — GIVEN a saved-search create, WHEN a filter field has the wrong type, THEN 422 with a field-level detail naming the offending field.
- **X2** — GIVEN a forced internal error inside a notifications route, WHEN it is called, THEN the generic 500 contract is returned with a `request_id` and no stack trace, SQL, or file path.
- **X3** — GIVEN an SMTP backend that is unreachable, WHEN `forgot-password` is called, THEN 202 is still returned (the failure must not become an enumeration oracle) and the error is logged server-side.
- **X4** — GIVEN a malformed reset token that is not valid token syntax, WHEN it is redeemed, THEN the uniform 400 contract is returned rather than a 500.
- **X5** — GIVEN the notifications list, WHEN `limit` or `offset` is negative, THEN 422.

## 6. Out of scope (deliberately deferred)

- **Per-user notification preferences** (per-type, per-channel, digest/quiet hours) — D10. Every projected event notifies in-app.
- **Verification gating anything beyond outbound notification email** — D6. Gating listing creation or access requests is a later, deliberate scoping call with no owner yet.
- **JWT revocation on password reset** — D8; owned by `security.md` §9's refresh-token work.
- **Backfilling alerts** for listings that went live before a saved search existed — D7.
- **Real SMTP delivery guarantees** (retries, bounce handling, DKIM/SPF, unsubscribe headers) — MailHog is the local channel; deliverability is a deploy-hardening concern.
- **Sorting and the "multiple" filter** on saved searches — still deferred from M4 with no milestone claimed; saved-search filters cover exactly what M4's browse endpoint already validates.
- **Notification deletion / archive** by the user — read/unread only at MVP.
