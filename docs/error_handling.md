# Error Handling — the product's failure contract

> How NextOwner fails: one consistent, safe, testable contract for every error —
> backend, frontend, and mocked vendors. A first-class cross-cutting concern,
> handled the way `docs/security.md` handles security: a strategy here + a
> mandatory **"Errors & failure modes"** section in every spec (`/new-spec`) +
> per-milestone tests. Binding alongside the constitution.
>
> **Relationship to security:** this doc and `docs/security.md` §5/§Output overlap
> on *fail closed, don't leak*. `security.md` stays authoritative for the
> threat/leakage angle; this doc is the general product-facing failure contract.

---

## 0. Principles

1. **Errors are UX.** In a trust marketplace a confusing or leaky error erodes trust as much as a bug. Fail **closed**, fail **clearly**, never **leak**.
2. **One contract.** Every error crosses the API in a predictable shape so the frontend handles them uniformly — the HTTP status is the primary signal, a machine `code` the secondary discriminator.
3. **Test the failure paths first (SDD).** Every failure mode is a GIVEN/WHEN/THEN → exactly one test, written failing before the code — same discipline as the forbidden-path/permission tests.
4. **Classify, then handle.** Each error class has one status and one frontend treatment (§4). Don't invent per-endpoint behavior.
5. **The server owns the truth.** Detail is logged server-side with a request id; the client gets a generic, safe message.

## 1. The error response contract

Three shapes, chosen by class:

```jsonc
// 4xx business/permission errors — the common shape:
{ "detail": "You do not have access to this data room.", // generic, safe, human-readable
  "code": "nda_access_required" }                          // machine slug: frontend branch / i18n

// 422 validation — keep FastAPI's native field-level shape (the frontend maps loc → field):
{ "detail": [ { "loc": ["body", "email"], "msg": "value is not a valid email address",
               "type": "value_error.email" } ] }

// 500 — generic; correlate via request id (safe to expose for support), full detail only in logs:
{ "detail": "Something went wrong on our end.", "request_id": "req_a1b2c3" }
```

Rules:
- **Status code is canonical** (401/403/404/409/422/500 — constitution Article 4). `code` is an added machine-readable discriminator, **not** a replacement.
- **Never** include stack traces, SQL, exception class names, file paths, or private/identity fields in any error body (`security.md` §Info leakage).
- `code` slugs are stable, lowercase, snake_case (`nda_access_required`, `invalid_transition`, `listing_not_live`, `offer_already_decided`).

### 1.1 The WebSocket error contract (chat, M6)

WebSockets have no response body to carry `{detail, code}` — a closing socket has a **close
code** and an optional reason string instead, and an otherwise-open one can carry a small JSON
error frame. Two different shapes for two different severities (spec 006 D1, `security.md` §1.5):

**Close codes — the connection ends.** Custom, in the RFC 6455 private-use range (4000–4999):

| Close code | Meaning | Raised when |
|---|---|---|
| `4001` | `auth_failed` | missing/expired/tampered token at connect — identity resolves before membership, so this is never confused with `4003` |
| `4003` | `not_a_member` | authenticated but not a participant (including a revoked buyer's fresh attempt), or the conversation doesn't exist — one code for both, never an existence oracle |
| `4004` | `access_revoked` | a **live** connection is force-closed because access was just revoked — distinct from `4003` on purpose: this answers "you were, and it just ended," not "you never were" |
| `4009` | `rate_limited` | the per-connection message-rate cap was exceeded |

Any other close code (`1000`/`1001` — a normal close, e.g. the user navigating away) is not part
of this contract and the frontend shows nothing for it.

**Error frames — the connection survives.** Sent over an otherwise-open socket, shaped
`{"type": "error", "code": "..."}`:

| Frame `code` | Meaning |
|---|---|
| `invalid_message` | the frame isn't valid JSON, or `text` is missing/blank/non-string |
| `message_too_long` | `text` exceeds the configured cap (`chat_message_max_chars`) |

Rules mirror §1's: codes are stable, lowercase, snake_case; nothing here ever carries stack
traces, SQL, or private/identity fields; a spoofed `sender_id` in a message payload is never
read, let alone echoed back in an error.

## 2. Backend pattern

- **`backend/app/errors.py`** — a small hierarchy:
  ```python
  class AppError(Exception):
      status_code: int = 400
      code: str = "bad_request"
      def __init__(self, message: str, *, code: str | None = None):
          self.message, self.code = message, code or self.code
  class NotFound(AppError):        status_code, code = 404, "not_found"
  class Forbidden(AppError):       status_code, code = 403, "forbidden"
  class Unauthorized(AppError):    status_code, code = 401, "unauthorized"
  class InvalidTransition(AppError): status_code, code = 409, "invalid_transition"
  ```
- **`permissions.py` and endpoints raise these** (e.g. `raise Forbidden("NDA access not granted", code="nda_access_required")`). State machines raise `InvalidTransition` → 409. This keeps status/`code` mapping in one place, not scattered `HTTPException(...)` literals.
- **Global exception handlers** registered on the app (`main.py`):
  - `AppError` → render the §1 4xx contract (`detail`, `code`) with `status_code`.
  - `RequestValidationError` → 422 field-level shape (FastAPI default; keep it).
  - unhandled `Exception` → **500 generic**; log the full traceback server-side **with the request id**; return only `{detail, request_id}`.
- **Request-id middleware** — assign a request id per request, attach to the logger and to the 500 response; propagate `X-Request-ID` if present.
- **Structured server-side logging** — log errors with class, `code`, request id, and safe context; **never** secrets/PII (`security.md` §Info leakage).

## 3. Frontend pattern

- **`app/src/lib/api.ts`** — on `!res.ok`, parse the contract and throw a typed **`ApiError(status, code, detail)`** (not a bare `Error`), so callers branch on `status`/`code` instead of string-matching.
- **Global handling:**
  - **401** → clear session + redirect to login (one interceptor, not per-call).
  - **Network / fetch failure** → a "connection lost" state, with retry.
- **Display surfaces:**
  - a top-level React **`ErrorBoundary`** → fallback UI for render-time crashes (never a white screen);
  - a global **snackbar/toast** for transient errors (409, 500, network);
  - **inline field errors** for 422 (map each `loc` → the form field);
  - the **empty / loading / error triad** for every data view (NFR: `requirements.md` §3).
- **Never render server internals** — show the generic `detail`; surface `request_id` only as "reference: …" for support.

## 4. Error classes → handling

| Class | HTTP | `code` examples | Frontend treatment |
|---|---|---|---|
| Validation | 422 | (field-level) | inline errors on the offending fields |
| Unauthenticated | 401 | `unauthorized`, `token_expired` | global: clear session → login |
| Forbidden / not found | 403 / 404 | `forbidden`, `nda_access_required`, `not_found` | generic "no access" / "not found"; **no leak** of why |
| Invalid state | 409 | `invalid_transition`, `offer_already_decided` | toast + refresh the entity's state |
| System | 500 | `internal_error` | toast "something went wrong" + `request_id` for support |
| Upstream / vendor | 502 / 503 | `payment_unavailable`, `kyc_unavailable` | "provider unavailable — retry"; safe to retry |

## 5. Mocked-vendor failure modes

The Stripe / Persona / Escrow mocks are **production-shaped state machines** (constitution Article 1) — that means modeling **failures**, not just happy paths. The flows that use them must handle:

- **Stripe (payments):** card declined, insufficient funds, 3DS-required, webhook-failed.
- **Persona (KYC/verification):** pending, failed, needs-manual-review.
- **Escrow.com (escrow):** funding-failed, dispute-opened, cancelled.

Each is a state in the mock, surfaced through the §1 contract (mapped to 402/409/502 as appropriate) and covered by the owning milestone's spec — the **payments milestone** (not yet sequenced — see `docs/milestones.md`) and M10 verification.

## 6. Observability

- Structured server-side logs keyed by **request id** (§2); log the error class + `code` + safe context, **never** secrets/PII.
- Client-side error events through the local **`track(event, props)`** wrapper (console for now).
- Post-MVP: real error monitoring; the request-id contract makes that a drop-in.

## 7. In the SDD loop (per milestone)

- Every spec's **"Errors & failure modes"** section (via `/new-spec`) enumerates that milestone's failure paths as GIVEN/WHEN/THEN → one test each, written **failing first** — alongside "Security & abuse."
- **Minimum coverage per milestone that touches the API:** the 422 validation path, any 409 illegal transition, and a **500-safety** assertion (a forced error returns a generic body with **no** stack/SQL). Frontend milestones add error-state component tests (empty/loading/error, inline 422).
- **Foundation built at M1 (auth):** `errors.py` + the global handlers + request-id middleware + the `ApiError` type in `api.ts` + the `ErrorBoundary` + the global snackbar. M1 is the first milestone with real error paths (bad credentials, expired token, invalid input), so the contract lands there and every later milestone reuses it.

## 8. Checklist (per milestone touching the API or UI)

- [ ] Failure paths enumerated in the spec's **Errors & failure modes** section (GIVEN/WHEN/THEN).
- [ ] 422 validation returns the field-level shape; the UI shows inline errors.
- [ ] Business/permission errors raise an `AppError` subclass → correct status + `code`; **no** raw `HTTPException` literals with leaky messages.
- [ ] Illegal state transitions → 409 (`invalid_transition`), tested.
- [ ] A forced 500 returns the generic contract with a `request_id` and **no** internals (tested).
- [ ] Frontend: `ApiError` thrown by `api.ts`; 401 handled globally; error/empty/loading states present; `ErrorBoundary` covers the route.
- [ ] Vendor-mock failure states (if used) modeled and handled.
