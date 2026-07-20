# Plan 006 — Realtime chat

Implementation plan for `spec.md`. Same order M5 used: the boundary exists and is proven by
tests before any UI depends on it. This milestone additionally proves the boundary **live** —
a WebSocket connection, not just a request/response pair.

## Schema deltas (`backend/app/models.py`)

**`Conversation`** — new table, one per `(listing, buyer)` pair, created only by approval:

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `listing_id` | FK `listing.id`, indexed | The seller is `listing.owner_id` — not duplicated here. |
| `buyer_id` | FK `user.id`, indexed | **From the approved `AccessRequest`, never the body.** |
| `created_at` | `datetime` | |
| `buyer_last_read_at` | `datetime \| None` | D3 — two columns instead of a participant table. |
| `seller_last_read_at` | `datetime \| None` | |

**Unique constraint on `(listing_id, buyer_id)`** — mirrors `AccessRequest`'s (spec 005), and for
the same reason: at most one conversation per pair, ever. In practice the state machine already
guarantees `approve` fires at most once per pair (a second attempt is `409` before reaching
conversation creation), so this is defense in depth, not the only line of defense.

**`Message`** — new table:

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `conversation_id` | FK `conversation.id`, indexed | |
| `sender_id` | FK `user.id` | **Server-derived from the WS connection's verified token** (C3). |
| `text` | `str` | Length-capped at the WS boundary (D2), not the column. |
| `created_at` | `datetime` | |

*Erasure note (`data_protection.md`):* both tables reference a person but store no PII of their
own beyond user-typed `text`, which is the same class of free-text content `ListingPrivate` and
`ListingUpdate` already carry. Anonymizing a `User` in place leaves conversation/message rows
intact and readable — same "keep for audit with the author anonymized" treatment `offers` and
`access-requests` already get (`data_protection.md` §3).

**Config** (`backend/app/config.py`):

| Setting | Default | Used by |
|---|---|---|
| `chat_message_max_chars` | `4000` | D2 — the size cap |
| `chat_rate_limit_max` | `20` | E1 — messages per window |
| `chat_rate_limit_window_seconds` | `10` | E1 |
| `chat_history_page_limit` | `50` | G5 — the pagination ceiling |

## Endpoints

| Method + path | Permission dependency | Notes |
|---|---|---|
| `WS /ws/conversations/{id}?token=…` | inline auth + membership (below — not `Depends`, see § Permission gates) | connect, send, receive |
| `GET /api/conversations` | `get_current_user` (caller-scoped query) | list, with `unread_count` |
| `GET /api/conversations/{id}/messages` | `require_conversation_member` | history, paginated |
| `POST /api/conversations/{id}/read` | `require_conversation_member` | stamps caller's own `*_last_read_at` |

**Two existing M5 endpoints change** (`backend/app/routers/access.py`), both flagged in
`progress.md` as this milestone's to finish:

- `approve_access_request` additionally creates the `Conversation` row (A1). Stays `def`, not
  `async def` — creating a row needs no `await`.
- `revoke_access_request` becomes `async def` (there is precedent: `upload_document`, M2, is
  already `async def` beside sync `Session` calls) so it can `await chat_broker.close_user(...)`
  after the decision commits (F1). The revoke logic itself — `_decide()`, the transition guard,
  the audit row — is **unchanged**; only the new call after it.

## Permission gates (`backend/app/permissions.py`)

One new function, plus a helper shared with the WebSocket handler — the rule lives in one place
even though it has two callers that can't both use `Depends` (a WS auth failure needs to
`close()` the socket, not raise an `AppError` a JSON response handler would render):

- **`conversation_role_for(session, conversation, user) -> Literal["buyer","seller"] | None`** —
  the shared logic. Owner of the conversation's listing → `"seller"`, unconditionally (mirrors
  D1 in `require_private_access`: the owner always passes). The conversation's `buyer_id` →
  `"buyer"` **only if** an `approved` `AccessRequest` for that exact `(listing, buyer)` pair
  still exists right now — re-checked live, not inferred from the conversation row's mere
  existence, which is what makes F1–F3 possible. Not a call into `require_private_access` or a
  refactor of it: a 5-line duplicate query, deliberately, so M6 cannot introduce a regression in
  M5's crown-jewel gate by editing it. Returns `None` for everyone else, uniformly (D2/S4) —
  never distinguishes "no such conversation" from "not yours."
- **`require_conversation_member`** — the REST wrapper: loads the `Conversation` (`None` → the
  same `Forbidden` as everyone else, never `NotFound`), calls `conversation_role_for`, raises
  `Forbidden` if `None`, else returns the `Conversation`.
- **The WS handler calls `conversation_role_for` directly**, not through `Depends` — on `None` it
  awaits `websocket.close(code=4003, ...)` and returns, rather than letting an `AppError`
  propagate somewhere a WebSocket has no JSON response to render it into.

## The chat broker (`backend/app/chat_broker.py`, new file)

The fold-in's `publish(conversation_id, message)` port, shaped exactly like
`backend/app/ratelimit.py`'s `RateLimiterBackend`/`InMemoryRateLimiterBackend` split — this
codebase's existing precedent for "per-instance state behind a swappable interface"
(`design_implementation.md` § Horizontal scale, blocker #3):

```python
class ChatBroker(Protocol):
    def register(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None: ...
    def unregister(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None: ...
    async def publish(self, conversation_id: int, payload: dict) -> None: ...
    async def close_user(self, conversation_id: int, user_id: int, code: int, reason: str) -> None: ...
```

`InMemoryChatBroker` is `{conversation_id: {user_id: {sockets}}}` — single-instance **by
construction**, correct for the MVP, fatal behind a load balancer (unchanged fact, just now
behind a name instead of a bare dict). `publish` fans out to every registered socket for that
conversation, sender included (D4). `close_user` is what F1 calls on revocation. Swapping the
module-level `chat_broker` instance for a pub/sub-backed implementation later is constructing it
differently, not editing the WS handler or `access.py`.

## Response models (`backend/app/schemas.py`)

- **`ConversationSummary`** — `id`, `listing_id`, `listing_headline`, `counterpart_display_name`,
  `unread_count`, `last_message_at`. No buyer email, no seller email (S2) — a display name is
  the only identity-adjacent field, same minimization principle as `BuyerProfile` (spec 005).
- **`MessageRead`** — `id`, `conversation_id`, `sender_id`, `text`, `created_at`. `sender_id` is
  a bare integer, not a nested profile — the frontend already knows both participants from the
  conversation summary it came from, and comparing it to `authStore.user.id` is J3's whole
  mechanism.

## Errors (`backend/app/errors.py` — existing classes, no new subclass)

| Raised | Class | `code` |
|---|---|---|
| Non-member on REST | `Forbidden` | `not_a_conversation_member` |
| Over-cap `limit` | *(Pydantic, automatic)* | `422` field error |

WebSocket close codes are **not** `AppError`s — there is no JSON body to render on a closing
socket. They are documented as their own contract, added to `docs/error_handling.md` as a new
section (the fold-in's required landing spot):

| Close code | Meaning | Raised when |
|---|---|---|
| `4001` | `auth_failed` | missing/expired/tampered token at connect (B4) |
| `4003` | `not_a_member` | authenticated but not a participant, or the conversation doesn't exist (B3, B5, F2) |
| `4004` | `access_revoked` | a **live** connection is force-closed because access was just revoked (F1) |
| `4009` | `rate_limited` | the per-connection message-rate cap was exceeded (E1) |

Plus two **non-fatal** error frames sent over an otherwise-open connection (D1–D3):

| Frame `code` | Meaning |
|---|---|
| `invalid_message` | missing/blank/non-string `text`, or a frame that isn't valid JSON |
| `message_too_long` | `text` exceeds `chat_message_max_chars` |

## Frontend (`app/src/`)

- **`chatStore.ts`** (MobX, new) — mirrors `accessStore.ts`'s shape: `conversations`,
  `messages`, a `status` enum (`idle | loading | connected | closed | error`), and a `socket`
  reference. Owns the WS lifecycle (connect on mount, close on unmount) and the close-code → UI
  message mapping (X3).
- **`ConversationList.tsx`** (new) — `GET /api/conversations`, renders `ConversationSummary` rows
  with unread badges (J2).
- **`ChatWindow.tsx`** (new) — history + live socket. Renders messages as **text**, never
  `dangerouslySetInnerHTML` (J4) — React's default escaping is the control, same principle
  `PrivateSection.tsx` already relies on for seller-supplied text.
- **`NavBar.tsx`** (existing, edited) — a "Messages" link with a badge summing `unread_count`
  across `GET /api/conversations`, refetched on route change (the same "poll/refetch on route
  change, fine for MVP" pattern the rest of the app already uses — no new live-update mechanism
  needed just for a nav badge).
- Routes (`App.tsx`): `/messages` (list) and `/messages/:id` (window), both behind `RequireAuth`
  — the real boundary is `require_conversation_member`/`conversation_role_for` server-side, this
  is UX only (same framing as M5's `/my-listings/:id/requests` route guard).

## Analytics events

**None.** Still no `track()` wrapper in the codebase (`progress.md` § M4 carryover, restated at
M5). A chat message is exactly the kind of event an analytics call could leak by accident if it
existed; it doesn't, so there is nothing to be careful with yet.

## Data protection

No new PII field. `Conversation`/`Message` reference people by id only; `Message.text` is
user-generated free text, the same category `ListingPrivate.detailed_financials` already is —
minimized by not existing on any schema it doesn't need to, not by restricting what a user types
into their own conversation. Erasure behavior: anonymize-in-place on `User`, keep the rows
(§ Schema deltas above).

---

## Build order

Ordered slices — **one trust boundary each**, each turning a named cluster of red tests green,
each one commit. No checkboxes: the red test list is the status (`pytest -q --lf`).

1. **Schema + config + the broker port.** `Conversation`, `Message`, the four new config values,
   `chat_broker.py` (`ChatBroker` protocol + `InMemoryChatBroker`, unregistered with anything
   yet). *First because every later slice reads or writes these, the same reason M5's slice 1
   was schema-only.* Turns green: model/constraint tests only.

2. **Conversation creation on approval.** Edit `approve_access_request` (`access.py`) to create
   the `Conversation` row. *Before the WS layer exists, because A1/A2 need nothing else — they
   only read the table a decision writes.*
   → **A1, A2**.

3. **`conversation_role_for` + `require_conversation_member` + the WS handshake (connect only —
   no send/receive yet).** *The first real trust boundary of the milestone, and the one every
   other WS behavior sits behind.* Implement the WS route accepting or closing during the
   handshake per § Permission gates, with no message loop body yet (accept, then immediately
   hold the connection open with nothing to do — the tests only assert accept-vs-reject).
   → **B1–B5, S1 (partial — REST side lands in slice 6), S3, S4 (partial)**.

4. **The message loop — receive, validate, rate-limit, persist, broadcast.** Add the `while`
   loop inside the accepted connection: parse, validate (D1–D3), rate-limit (E1), persist,
   `chat_broker.publish(...)` including the sender's own socket (D4). *Sequenced after slice 3
   because there is no point validating messages on a connection that can't yet be proven to
   reject the wrong caller.*
   → **C1–C4, D1–D3, E1**.

5. **Revocation applies live.** Edit `revoke_access_request` (`access.py`) to `async def` and
   `await chat_broker.close_user(...)` after the decision commits. *Only possible after slice 4
   — there must be a real, connected socket for revocation to close, or F1 is untestable.* Also
   land `conversation_role_for`'s live re-check here if it wasn't already exercised by a test —
   F2/F3 are what prove the re-check happens on **every** call, not once at connect.
   → **F1–F4, S5**.

   **Re-run M5's `test_access_decisions.py` (C1–C12) in full after this slice** — `revoke_access_request`
   is the one M5 endpoint this milestone edits, and "if you touch the gate, re-run the sabotage"
   (`progress.md` § M5 carryover) applies here too: temporarily remove the new `await
   chat_broker.close_user(...)` call and confirm **only** F1 goes red, nothing in M5's own suite
   does — proof the edit added behavior without changing any of M5's.

6. **REST reads: history, mark-as-read, the conversation list.** `GET /conversations`,
   `GET /conversations/{id}/messages`, `POST /conversations/{id}/read`. *Read-only and
   lowest-risk, so last among the backend slices — same ordering rationale as M5's slice 7.*
   Also land the `docs/error_handling.md` WS-contract addendum in this commit: by now all four
   close codes and both error-frame codes have a passing test behind them, so the doc describes
   shipped behavior rather than a plan.
   → **G1–G5, H1–H4, I1–I3, S1 (REST half), S2, S4 (REST half), X1**.

7. **Frontend.** `chatStore`, `ConversationList`, `ChatWindow`, the `NavBar` badge, routes.
   *Last, same reason M5's UI slice was last: building it against a still-moving gate means
   rebuilding it.*
   → **J1–J5, X2, X3**.

*If a slice reveals this order was wrong, fix the order here and say so in the commit — the plan
is a design artifact, not a prophecy. Never reorder by weakening a test.*
