# Spec 006 — Realtime chat

> **Milestone M6** — `docs/design_implementation.md` Part 4 § *Milestone 6 — Realtime chat (F7)*.
> The project's **first WebSocket surface** (`docs/testing_guide.md` §4.4, `docs/security.md`
> §1.5). Everything M5 built exists to gate this: a conversation only exists between an owner
> and a buyer who holds — right now, not merely once — an `approved` access request.

## FR references

| FR | What it requires |
|---|---|
| **FR-16** | Buyer and seller can exchange realtime messages with unread counts **and email fallback notifications**. **Partially satisfied — the realtime + unread half only.** The email-fallback half ships at M8, which builds the email channel (`milestones.md` § Scope fold-ins → M6 and → M8; mirrors M5's FR-14/D5 partial-satisfaction pattern). |
| **F7** (MVP scope) | In-app buyer↔seller messaging (realtime) — "the connection moment," the marketplace's job. |

**Scope fold-ins** (`docs/milestones.md` § Scope fold-ins → M6), each carried below as criteria:
a conversation **unique per `(listing, buyer)`**; **`last_read_at` per participant** for unread
counts; a **WebSocket error contract** (close codes for auth-fail / non-member / revocation /
rate-cap, landing as an `error_handling.md` addendum); message events for the FR-16 email
fallback (M8 delivers — M6 only needs to leave the `message` row M8 will read).

**Carried from M5's close** (`docs/progress.md` § ▶ NEXT ACTION, written at the M5 PR):
approving access also creates the `conversation` row (design_implementation.md M6); revocation
must re-deny the socket **and** history immediately (`security.md` §1.5); the in-memory
`{conversation_id: [sockets]}` registry is single-instance by construction, so the fan-out sits
behind a `publish(conversation_id, message)` port from the first commit, not retrofitted later.

---

## User stories

1. **As a buyer with approved access**, I want to message the seller directly, so I can ask
   questions before deciding whether to make an offer.
2. **As a seller**, I want to message an approved buyer, so I can build the relationship and
   answer questions without leaving the platform.
3. **As either participant**, I want to see how many messages I haven't read yet, so I know
   when to check back in.
4. **As the platform**, I want a revoked buyer's chat access cut off immediately — the live
   socket **and** the history endpoint alike — so revocation is a real boundary, not a
   decorative one that a still-open tab quietly ignores.
5. **As a participant**, I want message history to survive a reload or reconnect, so the
   conversation isn't lost the moment a tab closes.

---

## Decisions

Not gated on `--pause-after-spec` this run, but recorded for the same reason M5's were:
implementation choices with a real alternative deserve a written reason, not just a diff.

**D1 — Close codes are custom, in the RFC 6455 private-use range (4000–4999).** Four codes, one
per fold-in item: `4001` auth-fail, `4003` non-member, `4004` revoked-live, `4009` rate-capped.
`4003` and `4004` are deliberately **different codes for the same underlying fact** (no approved
access) because they answer different questions for the frontend: `4003` means "you were never
in this conversation" (connect-time), `4004` means "you were, and it just ended" (a live
force-close). Documented in `docs/error_handling.md`'s new WS section (the fold-in's required
landing spot).

**D2 — A missing or foreign conversation id is `403`/`4003`, uniformly — never `404`.** M5 faced
this exact choice twice and answered it both ways (`require_private_access`: 404 for a
never-published listing, because the listing's existence is the secret; `require_request_decider`:
403 for a missing-or-foreign access-request id, because the id carries no such secret). A
conversation only ever exists after an approval already granted through a boundary that has its
own existence rule; the conversation id itself protects nothing an attacker couldn't already
have learned by other means, so this boundary follows `require_request_decider`'s precedent:
one uniform refusal, not two distinguishable ones (S1, S4).

**D3 — `last_read_at` is two columns on `Conversation`, not a separate participant table.** A
conversation has exactly two possible participants — the buyer and the listing's owner — the
same shape `AccessRequest` already has. A `ConversationParticipant` table would be the general
form for a feature (group chat) this product doesn't have and has no FR asking for.

**D4 — The sender's own socket receives the broadcast too.** `security.md` §1.5 requires the
server, not the client, to be the source of a message's `id`/`created_at`; echoing it back to
the sender means the frontend never has to guess those values or reconcile a locally-drawn
optimistic bubble against the server's — one code path renders every message, sender included.

**D5 — Entry point is a global "Messages" nav link, not a per-listing deep link.** No FR or
fold-in asks for "message this buyer" from the access-request queue or "message the seller" from
the listing page; building it would be scope no criterion below tests. `NavBar` gains a
"Messages" link with an unread badge; the conversation list is the hub. A per-row deep link is a
plausible fast-follow, deliberately deferred (§ Out of scope).

**D6 — WebSocket auth reads the token from a query parameter, not a header.** Browsers cannot
attach a custom header to a WebSocket handshake request. `security.md` §1.5 already accepts
`ws://` + a query-param token as fine **locally**; production TLS/subprotocol hardening is
deferred to §9 alongside M5's other deploy-hardening items — unchanged by this milestone, just
inherited.

---

## Acceptance criteria

Each GIVEN/WHEN/THEN below becomes **exactly one test** (constitution Article 3 §2).

### A — Conversation creation on approval

- **A1** GIVEN a `requested` access request, WHEN the seller approves it, THEN a `Conversation` row exists for `(listing_id, buyer_id)` (design_implementation.md M6).
- **A2** GIVEN an access request that is denied (never approved), WHEN the conversation table is checked, THEN no row exists for that pair — only `approve` creates one.

### B — WebSocket connect: authentication + membership (`security.md` §1.5)

`WS /ws/conversations/{id}?token=…`. Rejection happens **during the handshake**, before
`accept()` — `docs/testing_guide.md` §4.4's own test shape (`pytest.raises` around
`websocket_connect`).

- **B1** GIVEN the listing's owner, WHEN they connect with their token, THEN the connection is accepted.
- **B2** GIVEN the buyer of an `approved` request, WHEN they connect with their token, THEN accepted.
- **B3** GIVEN a user who is neither the buyer nor the listing's owner, WHEN they connect with an otherwise-valid token, THEN rejected during the handshake with close code `4003`.
- **B4** GIVEN no token, an expired token, or a tampered/invalid-signature token, WHEN connecting, THEN rejected with close code `4001` — **never** `4003`, so the frontend can tell "log in again" from "you're not part of this" (mirrors M5's S6: identity resolves first).
- **B5** GIVEN a conversation id that does not exist, WHEN any authenticated user connects, THEN rejected with `4003` — the same code as B3, so a nonexistent id and a real one you don't belong to are indistinguishable (D2).

### C — Sending and receiving messages

- **C1** GIVEN two connected participants, WHEN the buyer sends `{"text": "Is churn really 2%?"}`, THEN the seller's socket receives a message frame carrying the same text (`testing_guide.md` §4.4).
- **C2** GIVEN a message sent while both are connected, WHEN both disconnect and a participant later fetches history, THEN the message is present — it was persisted, not merely relayed.
- **C3** GIVEN a connected user, WHEN they send `{"text": "hi", "sender_id": <someone else's id>}`, THEN the persisted **and** broadcast message's `sender_id` is the connected user's real id — the payload field is ignored (Article 2 #4, `security.md` §1.5's "identity from the token, never the payload").
- **C4** GIVEN a message sent, WHEN it is broadcast, THEN the **sender's own** open socket also receives it, carrying the server-assigned `id` and `created_at` (D4).

### D — Message validation (non-fatal — the connection survives)

- **D1** GIVEN a connected user, WHEN they send `{"text": ""}` or a whitespace-only string, THEN they receive an error frame `{"type":"error","code":"invalid_message"}`, the connection stays open, and nothing is persisted or broadcast.
- **D2** GIVEN a connected user, WHEN they send `text` longer than the configured cap, THEN an error frame `code:"message_too_long"`, connection stays open, nothing persisted.
- **D3** GIVEN a connected user, WHEN they send a frame that isn't valid JSON, or valid JSON with no `text` key or a non-string `text`, THEN an error frame `code:"invalid_message"`, connection stays open.

### E — Rate limiting (fatal — the connection ends)

- **E1** GIVEN a connected user sending messages faster than the configured cap, WHEN the cap is exceeded, THEN the connection is closed with code `4009`; every message that landed **under** the cap was persisted and broadcast normally before the close (`security.md` §6 DoS surface, §7 M6 "message size/rate caps").

### F — Revocation applies live (`security.md` §1.5, the M5→M6 carryover)

- **F1** GIVEN a buyer with a live, open WebSocket connection and `approved` access, WHEN the seller revokes it, THEN that socket is closed with code `4004` — in the **same** request that performs the revocation, not on the buyer's next action.
- **F2** GIVEN a buyer whose access was just revoked, WHEN they attempt to reconnect, THEN rejected with `4003` — a fresh attempt after revocation is indistinguishable from never having been a member (consistent with B3/B5, D2).
- **F3** GIVEN a revoked buyer, WHEN they call `GET /api/conversations/{id}/messages` over REST, THEN `403` — the REST boundary re-checks membership on **every** call, not only at WS connect time, so a buyer who never opens the socket again is still cut off.
- **F4** GIVEN a revoked buyer's conversation, WHEN the seller (the owner) continues to use it, THEN the seller's own access is unaffected (`200`) — revocation is buyer-scoped, not conversation-wide.

### G — Message history (REST)

- **G1** GIVEN a conversation with several persisted messages, WHEN a member calls `GET /api/conversations/{id}/messages`, THEN the most recent page is returned, newest first.
- **G2** GIVEN more messages than fit one page, WHEN the caller passes `before=<message id>`, THEN only messages older than that id are returned (pagination, mirrors M4's cursor style).
- **G3** GIVEN a user who is not a member of the conversation, WHEN they call the history endpoint, THEN `403`.
- **G4** GIVEN no credentials, WHEN the history endpoint is called, THEN `401`.
- **G5** GIVEN a `limit` above the configured ceiling, WHEN requested, THEN `422` — bounded pagination is a boundary rule, not a runtime clamp (same discipline as M4's `ListingQuery`).

### H — Unread counts (`last_read_at` per participant)

- **H1** GIVEN a buyer who has never opened a conversation the seller has sent 3 messages in, WHEN they fetch `GET /api/conversations`, THEN that row's `unread_count` is `3`.
- **H2** GIVEN a participant, WHEN they `POST /api/conversations/{id}/read`, THEN their own `last_read_at` is stamped to now, and a subsequent `GET /api/conversations` shows `unread_count: 0` for messages up to that moment.
- **H3** GIVEN a participant who has read everything so far, WHEN the **other** participant sends one more message, THEN `unread_count` becomes `1` — unread is computed from the counterpart's messages only, never the caller's own sends.
- **H4** GIVEN a non-member, WHEN they call `POST /api/conversations/{id}/read`, THEN `403`.

### I — The conversation list

- **I1** GIVEN a buyer with two approved conversations, WHEN they `GET /api/conversations`, THEN both appear; a third conversation belonging to a **different** buyer never does (caller-scoped in the query, mirroring M5's F2).
- **I2** GIVEN a seller who owns two listings, each with one approved buyer, WHEN they `GET /api/conversations`, THEN both of their conversations appear regardless of which listing.
- **I3** GIVEN no credentials, WHEN `GET /api/conversations` is called, THEN `401`.

### Security & abuse

Derived from `docs/security.md` §1.5, §6, §7 (M6).

- **S1** — *IDOR on the conversation id, REST side.* GIVEN a conversation belonging to two other users, WHEN a third user requests its history or posts a read-receipt by guessing its id, THEN `403` — never `200`, and indistinguishable from a nonexistent id (D2, mirrors G3).
- **S2** — *Schema leak.* GIVEN the conversation-list and message response models, WHEN inspected, THEN neither exposes the counterpart's email or password hash — a display name and a listing headline are the only identity-adjacent fields present.
- **S3** — *Token attacks reach the WS gate too.* GIVEN an expired or signature-tampered token, WHEN connecting, THEN rejected `4001` — identity resolves before membership, same ordering M5's S6 requires on the HTTP gate.
- **S4** — *Enumeration uniformity.* GIVEN a conversation id that does not exist and one that exists but belongs to others, WHEN each is probed (REST and WS), THEN the two responses are identical in status and code — no signal either way (D2).
- **S5** — *Revocation reachability.* GIVEN any sequence of {approve, revoke} on one access request, WHEN the buyer's conversation access is checked (REST history **and** a fresh WS connect) after the **last** action in the sequence, THEN access reflects only the current status — never a status carried over from an earlier step in the sequence. A lighter-weight cousin of M5's D10 corridor test, scoped to chat's two-state space (`approved`/`revoked`). Verify by reverting F1–F3's checks and confirming this fails.

### Errors & failure modes

Per `docs/error_handling.md` §1 (HTTP) and its new WS section (this milestone, D1 above).

- **X1** — *422.* GIVEN an over-cap page size, WHEN `GET /api/conversations/{id}/messages?limit=<above the cap>` is requested, THEN `422` with field-level detail.

*500-safety is deliberately not a numbered criterion here* — the generic catch-all handler (`main.py`) is already exercised by the `/_debug/boom` route from M1 and reused by every subsequent milestone; a chat-specific forced error would test the same handler a second time, not new behavior. Recorded as a decision, not a gap, so it reads as intentional rather than as a numbered criterion gone missing.

- **X2** — *Frontend states.* GIVEN the chat window, WHEN loading / empty (no messages yet) / connected / connection-lost / rate-limited / access-revoked, THEN each state renders distinctly and none crashes the page.
- **X3** — *WS close-code mapping.* GIVEN a WebSocket `onclose` event, WHEN its code is `4001`, `4003`, `4004`, or `4009`, THEN the frontend shows the matching message from § Decisions D1; any other code (`1000`/`1001` — a normal close, e.g. the user navigating away) shows nothing.

### Frontend (FR-16, F7)

- **J1** GIVEN a signed-in user with unread messages across conversations, WHEN they view the nav bar, THEN a "Messages" link shows the total unread count as a badge (D5).
- **J2** GIVEN the conversation list, WHEN it renders, THEN each row shows the listing headline, the counterpart's display name, and its own unread badge; clicking a row opens that chat.
- **J3** GIVEN the chat window, WHEN it renders history, THEN messages appear oldest-first and a message is visually distinguished as "mine" vs "theirs" by comparing `sender_id` to the logged-in user's own id (`authStore.user.id`).
- **J4** — *XSS-safe render.* GIVEN a message whose text is `<script>alert(1)</script>` (or any HTML-looking string), WHEN it renders in the chat window, THEN it appears as **literal text** — never executed, never interpreted as markup. No `dangerouslySetInnerHTML` anywhere in the component (`security.md` §2 Frontend / §1.5 message hygiene).
- **J5** GIVEN the chat window open, WHEN the user types and submits a message, THEN the input clears immediately and the message appears once the server's broadcast/echo arrives — no optimistic render that could desync from the server-assigned id (D4).

---

## Out of scope (deliberately deferred)

- **Auto-reconnect on an unexpected socket drop.** A manual "refresh to reconnect" fallback is
  the MVP behavior. `design_implementation.md` frames this endpoint as "~40 lines and excellent
  learning" — reconnect/backoff/resubscribe logic would balloon that for a feature no criterion
  above requires.
- **Typing indicators, read receipts beyond unread counts, message editing/deletion, file
  attachments in chat.** None are named by FR-16, F7, or the M6 fold-in. Documents stay in the
  M5 data room; chat is text.
- **Per-listing/per-request deep links into a specific conversation** (§ Decisions D5). The
  global "Messages" nav entry + conversation list is the hub for this milestone; a plausible
  fast-follow, not required by any criterion here.
- **Email fallback for new messages.** FR-16's email half, and the saved-search/notification
  engine generally, is M8's (`milestones.md` § Scope fold-ins → M8). M6 leaves the `message` row
  M8 is expected to project a notification from — the same relationship `listing_event` already
  has to M8, established at M3/M5.
- **Horizontal scale.** The `ChatBroker` **port** is introduced now (the fold-in's explicit ask),
  but its only implementation stays the single-instance in-memory registry. Swapping in a
  pub/sub backend (Redis, Postgres `LISTEN/NOTIFY`) is deploy-hardening work
  (`design_implementation.md` § Horizontal scale, blocker #3), not this milestone's.
  Explicitly **not** re-architecture — constructing `ChatBroker` differently, not rewriting
  anything that calls `publish`/`close_user`.
- **Production WebSocket transport hardening** (`wss://`, moving the token out of the URL query
  into a subprotocol or first-frame auth). `security.md` §1.5 already scopes this to production;
  unchanged by this milestone, same deferral bucket as M5's httpOnly-cookie item (§9).
