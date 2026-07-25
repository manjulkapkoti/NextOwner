# Plan 008 — M8: Notifications engine + saved searches & alerts + account lifecycle

> Implementation plan for [`spec.md`](./spec.md). Schema, endpoints, gates, and — at the end — the **Build order**, the ordered slices the milestone is actually worked in.

---

## Schema deltas (`backend/app/models.py`)

**`Notification`** — the delivery record (spec D1).

| Column | Type | Note |
|---|---|---|
| `id` | int PK | |
| `recipient_id` | FK `user.id`, indexed | **Always server-derived** (D3). Every read is filtered on it. |
| `type` | str | `listing_approved`, `listing_rejected`, `listing_matched`, `access_requested`, `access_approved`, `access_denied`, `access_revoked`, `message_received`, `offer_submitted`, `offer_countered`, `offer_accepted`, `offer_declined`, `offer_auto_declined`, `offer_withdrawn` |
| `title` | str | Server-composed from **public** fields only (D2). |
| `listing_id` | FK, nullable, indexed | Link target. |
| `conversation_id` | FK, nullable | Link target. |
| `offer_id` | FK, nullable | Link target. |
| `read_at` | datetime, nullable | The one mutable field — this table is a projection, not an audit row. |
| `created_at` | datetime | |

Three nullable link FKs rather than a polymorphic `(kind, id)` pair: real referential integrity, and it is what makes the B7 dedupe expressible as a **partial unique index** — `(recipient_id, listing_id) WHERE type = 'listing_matched'` — reusing exactly the `Offer.uq_offer_one_active_per_pair` construction (`sqlite_where` + `postgresql_where`) so the guarantee survives the Postgres swap. Access-decision notifications link to the **listing**, not the access request; the buyer's destination is the data room.

**`SavedSearch`** — `id`, `user_id` (FK, indexed), `name`, `filters_json` (str — a JSON blob, mirroring `ListingPrivate.detailed_financials`), `created_at`. The blob is **never** interpolated into SQL: it is parsed back through the same Pydantic filter model M4's browse endpoint already validates, and matching re-uses that predicate builder (spec S5).

**`PasswordResetToken`** and **`EmailVerificationToken`** — deliberately **two tables, not one with a `purpose` column** (spec D4), so cross-purpose redemption is structurally impossible. Identical shape each: `id`, `user_id` (FK, indexed), `token_hash` (str, unique index), `expires_at`, `used_at` (nullable), `created_at`. The raw token is never stored (D5).

**`User`** gains **`email_verified_at: datetime | None`** — a timestamp, not a bool, matching `nda_signed_at`/`tos_accepted_at`. `UserRead` exposes the derived `email_verified: bool`, so there is exactly one stored source of truth for the fact.

## Config (`backend/app/config.py`)

`smtp_host` (`localhost`), `smtp_port` (`1025` — MailHog), `email_from`, `email_enabled`; `app_base_url` (for links in mail); `password_reset_token_ttl_minutes` (30), `email_verification_token_ttl_hours` (24); `forgot_password_rate_limit_max` (3) / `_window_seconds` (900); `saved_search_max_per_user` (20 — spec A9); `notifications_page_limit` (50 — spec E8).

## New modules

- **`backend/app/mailer.py`** — `EmailSender` (Protocol) / `SmtpEmailSender` / `NullEmailSender`, the `Dispatcher` / `ThreadDispatcher` / `InlineDispatcher` trio that decides *where* a send runs, plus the module-level `mailer` and `dispatcher`. The test double is `RecordingEmailSender` and lives in `conftest.py` — it is a test artifact, not product code. Shaped exactly like `ratelimit.py` and `chat_broker.py` (spec D9). **Named `mailer.py`, not `email.py`**, so nothing in the package can be confused with the stdlib `email` package `smtplib` imports.
- **`backend/app/notifications.py`** — `notify(...)` plus one small helper per event source, and `fan_out_saved_searches(session, listing)`. **This module is the trust boundary for recipient derivation** (D3): every recipient is computed here from the domain object, and no caller may pass one in.
- **`backend/app/tokens.py`** — `new_token()` → `(raw, sha256_hash)`, and the two redeem-and-consume functions. Redemption is uniform-failure by construction: missing, expired, used, malformed and wrong-purpose all take the same return path (spec G12, H5, H6, X4).

## Endpoints

| Method + path | Permission gate | Effect |
|---|---|---|
| `POST /api/saved-searches` | `get_current_user` | 201; `user_id` from JWT |
| `GET /api/saved-searches` | `get_current_user` | caller-scoped list |
| `DELETE /api/saved-searches/{id}` | **`get_owned_saved_search`** | 204 |
| `GET /api/notifications` | `get_current_user` | caller-scoped; `?unread`, capped `limit`/`offset` |
| `GET /api/notifications/unread-count` | `get_current_user` | caller-scoped count |
| `POST /api/notifications/{id}/read` | **`get_owned_notification`** | sets `read_at`; idempotent |
| `POST /api/notifications/read-all` | `get_current_user` | caller's unread only |
| `POST /api/auth/forgot-password` | *public* + rate limiter | **202, always** — identical for known and unknown addresses |
| `POST /api/auth/reset-password` | *public*; token **in the body** (D11) | 200; consumes the token, invalidates siblings |
| `POST /api/auth/verify-email` | *public*; token in the body | 200; stamps `email_verified_at` |
| `POST /api/auth/resend-verification` | `get_current_user` | 202; 409 if already verified |

**No route creates a notification** (spec S4) — they exist only as a side effect of a domain action, written by `notifications.py`.

## Permission gates (`backend/app/permissions.py`)

- **`get_owned_notification`** — returns **404 for both** "no such id" and "not yours", mirroring `get_owned_listing`'s reasoning: this is the caller's own inbox, so the two cases must be indistinguishable (spec S8).
- **`get_owned_saved_search`** — same shape, same reasoning.

Token redemption is deliberately **not** a `Depends` gate: these routes are unauthenticated by design (a user who cannot log in is the whole point), so the boundary lives in `tokens.py`'s redeem functions rather than in a dependency that assumes an identity.

## Response models (`backend/app/schemas.py`)

- **`NotificationRead`** — `id`, `type`, `title`, `listing_id`, `conversation_id`, `offer_id`, `read_at`, `created_at`. **`recipient_id` is deliberately absent**: it is always the caller, so exposing it adds nothing and gives a future refactor a way to leak someone else's id (spec S3).
- **`UnreadCountRead`** — `unread_count`, reusing the field name `ConversationRead` already established at M6.
- **`SavedSearchCreate` / `SavedSearchRead`** — filters typed by the **same** Pydantic model M4's browse route validates, so an unknown or private-column filter is a 422 at the boundary (A7, S5).
- **`ForgotPasswordRequest` / `ResetPasswordRequest` / `VerifyEmailRequest`** — token as a body field only.
- **`UserRead`** gains `email_verified: bool`, derived from `email_verified_at`.

## Errors (`docs/error_handling.md`)

| Raised | Status + code |
|---|---|
| `Conflict("...", code="saved_search_limit")` | 409 |
| `Conflict("...", code="already_verified")` | 409 |
| `BadRequest("...", code="invalid_token")` | 400 — **the single uniform failure** for missing / expired / used / malformed / wrong-purpose tokens |
| `RateLimited(...)` | 429 |

Frontend states: loading + empty + error on the inbox (J4–J6), inline field-level 422 on reset-password (J9), and a success/failure pair on verify-email (J10).

**Vendor failure mode:** SMTP is the milestone's first outbound dependency. A send failure is caught, logged server-side, and **never propagates** — the domain action keeps its 2xx and `forgot-password` keeps its uniform 202, because an error surfaced there would itself become the enumeration oracle G2 exists to prevent (F4, X3).

## Analytics events

**None.** There is still no `track()` wrapper anywhere in the codebase, and no acceptance criterion covers analytics — so M8 emits none rather than shipping an untested side channel, exactly as M4 decided. Recorded so the gap stays visible rather than looking like an oversight.

## Data protection (`docs/data_protection.md`)

- **No new PII fields.** `email_verified_at` is a status timestamp, not personal data. Notification `title` is server-composed from public fields and **must never** embed an email address or a private-table value (spec D2, C14, C15) — the rule that keeps audit-adjacent rows PII-free applies here too.
- **Four new person-referencing tables.** All four **cascade on erasure** rather than anonymize-in-place: `Notification` and `SavedSearch` are conveniences with no audit value (D1), and the two token tables hold **credential material**, which must not outlive its user under any circumstance. This is the opposite of the offer/access-request choice (keep-and-anonymize for audit), and deliberately so — the distinguishing question is whether the row is evidence.
- Emails carry no password hash, no JWT, and no private listing field (F5).

---

## Build order

Eleven slices, each one trust boundary or one self-contained capability, each ending in one Conventional Commit. **No checkboxes and no status here by design** — the red test list is the status (`cd backend && pytest -q --lf`), and the red count is the progress bar.

1. **Config + the email port** (`mailer.py`, settings). → **F6**. *First because every later slice sends mail: the in-memory double must exist before any test can assert "an email was sent" without opening a socket.*
2. **`Notification` model + `notifications.py`'s `notify()` recipient derivation.** → the recipient-derivation half of **C1–C15**. *The trust boundary comes before anything that reads it — building the inbox first would mean building a reader for rows nothing yet writes correctly.*
3. **The inbox: `get_owned_notification` + the four read/mark routes.** → **E1–E10, S3, S4, S8, X2, X5**. *The second boundary, and the surface every remaining slice is asserted through.*
4. **Wire the projections** into the M3/M5/M6/M7 endpoints. → the wiring half of **C1–C15**, plus **S1, S2, S10**. *Only now do the call sites exist to be wired; S10's reachability walk needs every writer present to be meaningful.*
5. **`SavedSearch` model + CRUD + `get_owned_saved_search`.** → **A1–A10, S5, S6, X1**. *The third boundary. Searches must be storable before a fan-out can read them.*
6. **The alert fan-out on approve** (matching via M4's own filter predicate, the partial unique index for dedupe). → **B1–B8**. *Depends on both 4 and 5; it is the join of the notification writer and the saved-search store.*
7. **Email dispatch wiring** — the `email_verified` gate on notification mail, failure isolation. → **F1, F2, F4, F5, X3**. *Deliberately after the in-app path works: mail is the second channel, and building it first would couple the engine to a transport.*
8. **Password reset** (`tokens.py`, `PasswordResetToken`, forgot/reset, its own limiter). → **G1–G13, S7, X4**. *The security core. It sits after the mail channel because it is the channel's first real consumer.*
9. **Email verification** (`EmailVerificationToken`, the register hook, verify + resend). → **H1–H9, F3, S9**. *After reset, so the cross-purpose tests H5/H6 have both token types to cross.*
10. **Frontend** — inbox page, nav badge, saved-search UI, forgot/reset/verify pages. → **J1–J10**. *Last of the feature work, per the project's standing order: the server gate is the boundary, the client is the view.*
11. **Docs addenda** — the `error_handling.md` SMTP/vendor failure-mode entry and the `security.md` §7 M8 row reconciled with what actually shipped. *Last so it describes the built thing rather than the planned one.*

**If a slice reveals the order was wrong**, fix this section and say so in the commit — the plan is a design artifact, not a prophecy. Never reorder by weakening a test.
