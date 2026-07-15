# NextOwner Security Guide

> **Security is the owner's #1 priority.** This document is the end-to-end security policy and threat model for NextOwner. It is **binding** alongside `../specs/000-constitution.md` and must be consulted at **every step** — writing a spec, a query, an endpoint, a component, or a review. If a change touches **auth, permissions, data exposure, uploads, money, or WebSockets**, the relevant controls here are a definition-of-done requirement, covered by negative tests written *before* the happy path.
>
> **How to use it:** at spec time → §7 (per-milestone focus) + §6 (edge cases); while coding → §1 (the boundary you're crossing) + §2–§5 (controls); at `/dod` → §8 (the touched→must-cover matrix).

---

## 0. Posture — the non-negotiable principles

1. **The API is the only door.** The browser never reaches the database. Every privilege check lives in `backend/app/permissions.py`, one function per trust boundary (constitution Article 2, design_implementation §3.6).
2. **Default-deny.** No non-public route ships without an explicit `permissions.py` gate. When in doubt, forbid.
3. **Never trust the client.** `owner_id`, `sender_id`, `status`, `is_admin`, `verified`, prices, and timestamps are derived server-side from the JWT + DB — never accepted from the request.
4. **Validate in, shape out.** Every input is validated at the boundary (Pydantic); every response is shaped by an explicit `response_model` that cannot leak private fields.
5. **Fail closed, don't leak.** Correct status codes, generic client messages, no stack traces / SQL / internal detail. Log the detail server-side, not to the client.
6. **Least privilege & defense in depth.** Each actor (human or agent) gets only what its identity allows; multiple layers (authZ + schema + validation + DB scoping) each independently prevent a breach.
7. **Security is testable.** Every "who is denied?" is a permission test (the crown jewels, testing_guide §1). If you can't write the forbidden-path test, the spec is too vague.

---

## 1. End-to-end data flow — trust boundaries

### 1.1 Frontend → Backend (the primary trust boundary)

Everything arriving from the browser is **hostile until proven otherwise** — a real user's browser can be scripted, a token replayed, a field spoofed.

- **Authenticate every protected request.** JWT in the `Authorization: Bearer` header (attached by `app/src/lib/api.ts`); `get_current_user` decodes + verifies on every route → 401 if missing/invalid/expired.
- **Authorize every protected request.** An explicit `permissions.py` gate per route (default-deny). Authorize **the object, not just the action** — prevents IDOR (see §6).
- **Reject mass-assignment.** Server-controlled fields are never read from the body. Use request schemas that only declare client-settable fields; do **not** bind the ORM model directly to request input. Consider `model_config = ConfigDict(extra="forbid")` on sensitive request models so unexpected fields 422 instead of being silently ignored.
- **Validate types & bounds.** Pydantic on body/query/path: `asking_price > 0`, `role ∈ {buyer, seller}`, `status`/`type` via enums, string length caps, pagination `limit` capped (e.g. ≤ 100).
- **CSRF.** Using a `Bearer` header (not a cookie) for the JWT sidesteps classic CSRF. **If you ever move the token to a cookie, you must add CSRF protection** (SameSite=strict + CSRF token). Document any such change here.
- **CORS.** The app is single-origin (Vite proxy in dev, reverse proxy in prod), so **no CORS middleware is needed — do not add a permissive `allow_origins=["*"]`.** If cross-origin is ever required, use a strict allowlist + `allow_credentials` only with explicit origins.
- **Abuse limits.** Rate-limit auth endpoints (login/register) against brute force / credential stuffing; cap request body size; enforce `Content-Type`.

### 1.2 Backend → Database

- **Parameterized queries only.** Use SQLModel / SQLAlchemy expressions (`select(...).where(Model.col == value)`). **Never** build SQL with f-strings / string concatenation / `.text()` on user input → SQL injection.
- **Scope every query to the caller.** Filter by identity, not just by id: `where(AccessRequest.buyer_id == user.id)`. Fetching by primary key alone, then returning it, is the classic IDOR bug — gate or scope it.
- **Public vs private at the query layer.** Public paths query `Listing` only; `ListingPrivate` is reachable **only** behind `require_private_access`. Never `join` private data into a public response.
- **Atomic state transitions.** Multi-row changes happen in one transaction (accepting an offer flips `offer.status=accepted` **and** `listing.status=under_offer` together — never half-applied).
- **Least-privilege DB.** SQLite locally; on the Postgres swap, the app connects as a role **without** DDL/superuser rights. Connection string from env (§4), never hardcoded.
- **Migrations (Postgres/Alembic later).** Review every migration; no destructive change without a backup; never auto-run untrusted migrations.

### 1.3 Database → Backend

- **Rows are data, not trusted invariants.** Re-validate business rules in code even if the DB would allow the write (status-machine transitions are enforced in endpoints, not by the DB).
- **Deserialize safely.** JSON columns (`detailed_financials`, `document_paths`) are parsed with `json.loads` **and validated** into a Pydantic model — never `eval`, never trust the shape blindly.
- **Fetch the minimum.** Select only the columns a path needs; never load `ListingPrivate` (or password hashes) into a public code path "just in case."

### 1.4 Backend → Frontend (response shaping — the leak-prevention boundary)

- **Explicit `response_model` on every route.** Public listing responses use a `ListingPublic` schema that **does not declare** `company_name`, `website_url`, `document_paths`, `owner` identity, etc. — the schema physically strips them (design_implementation §3.5). **Never return a raw ORM object on a public route.**
- **Never serialize secrets.** Password hashes, JWT secrets, internal tokens, and other users' data must never appear in any response.
- **Error responses are generic.** A global exception handler returns `{detail: "..."}` with the right status; it must not surface stack traces, SQL, exception classes, or file paths. Log full detail server-side with a request id.
- **Existence disclosure.** Decide per spec whether "forbidden" should be `403` (reveals the resource exists) or `404` (hides it). For resources an unauthorized user shouldn't even know about, prefer `404` to prevent enumeration. Be consistent within a boundary.
- **Anti-scraping.** Cap pagination; only `live` listings are ever public; consider opaque IDs before any large public exposure (sequential ints enable enumeration — see §6).
- **Analytics don't leak.** The `track(event, props)` wrapper must never receive private/identity fields.

### 1.5 Backend ↔ Frontend over WebSocket (chat, M6)

- **Authenticate on connect, not on first message.** Verify the JWT and `require_conversation_member` **during the handshake**; reject the connection outright if invalid — do not accept-then-ignore.
- **Identity from the token, never the payload.** A spoofed `sender_id` in the message JSON is ignored; the sender is the connected, verified user.
- **Membership is enforced server-side.** Broadcast only to the conversation's participants; a non-participant can neither connect nor read history (`403`).
- **Revocation applies live.** If access is revoked (`access_request → denied`), the socket and history must re-deny immediately.
- **Message hygiene.** Cap message size and rate; persist then broadcast; the frontend renders message text as **text, never HTML** (XSS — §2 Frontend).
- **Transport.** `ws://` locally is fine; production must use `wss://` (TLS). A token in the URL/query is acceptable locally but is logged by proxies — prefer a subprotocol or first-frame auth in production, and keep tokens short-lived.

---

## 2. Cross-cutting controls

### Authentication — passwords & JWT
- **Passwords:** bcrypt with a sensible cost factor; never plaintext or reversible; never logged. Enforce a minimum length at registration.
- **JWT:** signing secret from env (§4), long & random; verify **signature, `exp`, and the allowed algorithm** on every request. **Pin the algorithm** (reject `alg: none` and algorithm-confusion). Keep tokens short-lived; plan a refresh flow. Put only non-sensitive claims in the token (user id) — **re-read privileged attributes (`is_admin`, `verified`) from the DB**, never trust them from the claim (a token issued before a role change must not grant the old role).
- **User enumeration:** login returns the **same** error for "unknown email" and "wrong password"; keep response timing similar (bcrypt helps). (Note the UX tradeoff and decide deliberately.)
- **Revocation:** short expiry is the MVP mitigation; a token blocklist / rotating secret is the deploy-time upgrade.

### Authorization — `permissions.py`
- One function per trust boundary, reused by every route behind it (`get_current_user`, `require_admin`, `require_private_access`, `require_conversation_member`).
- **Default-deny + authorize the object.** `require_private_access` checks *this* listing for *this* user (owner or approved) — that's the anti-IDOR pattern; copy its shape.
- **No privilege escalation:** clients cannot set `is_admin`, `verified`, `status`, `owner_id`; only `require_admin` routes flip admin-controlled fields; a seller has **no** code path to publish their own listing.

### Input validation
- Pydantic request schemas on all input; strict types, enums, bounds; reject server-controlled fields; `extra="forbid"` on sensitive models.

### File uploads (data room, M2/M5) — treat as hostile
- **Whitelist** content-type + extension; enforce a **max size**; reject anything else.
- **Never use the client-supplied filename in a path.** Generate the stored name server-side; store under `uploads/{listing_id}/`; **resolve the final path and assert it stays inside `uploads/`** (reject `..`, absolute paths, symlinks, URL-encoded traversal like `%2e%2e%2f`).
- **Serve only through `require_private_access`** — never statically expose `uploads/`. Set `Content-Disposition: attachment`; never serve as executable/inline HTML.
- Upload to someone else's listing → `403`; download without approved access → `403`.

### Output & error handling
- `response_model` everywhere; global exception handler → generic message + correct code; never leak internals; log server-side with a request id.

### Secrets & configuration
- All secrets (JWT signing key, DB URL, future Stripe/Persona/Escrow keys) live in **`.env` (gitignored)** loaded via a settings module (`pydantic-settings`). **Never hardcode, never log, never commit.** Provide `.env.example` with placeholder keys. Different secret per environment; rotate on any suspected leak.

### Frontend session & XSS
- **Token storage:** `localStorage` is readable by any XSS payload. It's acceptable for the local MVP, but record the tradeoff; for production prefer an httpOnly cookie (+ CSRF) or in-memory token + refresh. State the chosen approach in the M1 spec.
- **MobX `authStore`:** clear token + user on logout; store nothing more sensitive than the token. **Client-side route guards are UX only** — the server gate is the real boundary; never rely on hiding a button.
- **XSS:** React escapes by default — keep it that way. **Never `dangerouslySetInnerHTML`** with user-controlled content (listing descriptions, chat messages, `company_name`). If markdown is rendered, sanitize with DOMPurify. Validate/scrub URLs (`website_url`) before rendering as links — reject `javascript:`/`data:` schemes.
- **CSP** and other security headers at deploy (§9).

### Audit & logging
- Timestamped event rows already exist for offers (`offer_event`) and access decisions (`access_request.decided_at`). Extend the habit: log admin actions, logins, and **permission denials** server-side. Never log secrets, passwords, tokens, or full PII in plaintext. The `track()` analytics wrapper never receives private fields.

### Dependencies & supply chain
- Pin versions (`requirements.txt`, `package-lock.json`); run `pip audit` / `npm audit`; review any new dependency; keep FastAPI/Starlette/PyJWT/bcrypt patched.

### Third-party vendors & webhooks (mocked now, design for real later)
- **Never trust the client's word that a payment/KYC/escrow event happened — trust the server-to-server webhook.** Verify webhook **signatures** (e.g. Stripe signing secret), enforce **idempotency**, and validate the payload. Build the **mocks to mirror this shape** (a mock webhook endpoint that still checks a signature/secret) so the real swap is a drop-in.
- Vendor **client SDKs** (Stripe card form, Persona ID capture) keep sensitive data (card numbers, gov-ID) **off our servers** — preserve that boundary; our webhook is the source of truth for state changes.

### Agents (post-MVP, per constitution Article 1)
- Agents run **as scoped users through the same `permissions.py` gates** — never a rules-bypassing super-identity; an agent physically cannot read a data room its user wasn't approved for.
- Validate agent tool arguments and structured LLM outputs with Pydantic (same schema system as API requests).
- Treat LLM output as **untrusted** (prompt-injection): it may not bypass gates, exfiltrate private data, or escalate privilege. Log `agent_runs` / `agent_steps` for audit.

---

## 3. Frontend security specifics

- Escaping by default; no `dangerouslySetInnerHTML` on user content; sanitize any markdown; scrub URLs before linking.
- Route guards are UX; the server is the gate.
- Don't embed secrets in the bundle (no API keys in frontend code — the JWT is the only credential the browser holds).
- Handle 401 globally (clear session, redirect to login); handle 403 without leaking why beyond the generic message.

## 4. Backend security specifics

- Every router mounted under `/api` (WS under `/ws`); every non-public route has a `Depends(gate)`.
- `response_model` on every route; request schemas separate from ORM models.
- Global exception handler; structured server-side logging with request ids.
- Settings module reads `.env`; startup fails loudly if a required secret is missing (don't fall back to a hardcoded default).

## 5. Database & storage specifics

- Parameterized queries; caller-scoped filters; public/private table split maintained.
- Transactions for multi-row transitions; status guards in code.
- `uploads/` never statically served; path confinement enforced.
- `.gitignore` excludes `nextowner.db`, `backend/uploads/`, `.env` (already configured).

---

## 6. Edge cases & abuse scenarios — the "did you think about…" checklist

Run this list against every milestone that adds a route or a state change.

- **IDOR on every `{id}` route** — listing, `listing_private`, offer, conversation, message, access_request, watchlist, notification. Always authorize/scope the specific object to the caller.
- **Mass assignment via create/PUT** — client sends `status`, `owner_id`, `is_admin`, `verified`, `published_at`, price on a privileged flow → must be ignored/rejected.
- **Illegal state transitions** — submit a non-draft (409), approve an already-live listing (409), act on an already-decided offer/access request (409), publish without admin.
- **Self-dealing** — seller approving their own access request as if a buyer; buyer self-verifying; non-admin performing admin actions; user approving/deciding on a listing they don't own (403).
- **Access revocation** — `approved → denied` after the fact must immediately re-deny private data **and** chat **and** document downloads.
- **Duplicate / idempotency** — signing the NDA twice is idempotent (timestamp unchanged); duplicate access request for the same buyer+listing → 409 (unique constraint).
- **Enumeration & scraping** — sequential integer IDs let an attacker walk resources; mitigate with authZ on every fetch, rate limits, capped pagination; consider opaque IDs before public exposure.
- **Race conditions** — two concurrent offer-accepts, concurrent access approvals → transaction + status guard (re-check status inside the transaction).
- **File attacks** — upload to another's listing (403); download another's docs (403); path-traversal filename (`../../etc`); oversized file; wrong/spoofed content-type; (post-MVP) archive bombs / malware scan.
- **Token attacks** — expired token; tampered signature; `alg:none` / algorithm confusion; token for a since-deleted user; role changed after issuance (re-check from DB); missing token on a protected route (401).
- **Login abuse** — brute force / credential stuffing (rate limit); user enumeration via distinct errors/timing (return uniform failure).
- **DoS surface** — unbounded pagination, expensive filter combos, large uploads, WebSocket message floods → limits everywhere.
- **Info leakage** — 500 exposing SQL/stack; response including a private field; logs containing secrets/PII; analytics event carrying identity fields.
- **Test-only backdoors in prod** — the "make admin by writing to the session" helper is **test-only**; ensure no endpoint ever exposes admin-granting or status-force-setting to a client.

---

## 7. Per-milestone security focus (M0–M11)

Each milestone's spec must include a **"Security & abuse"** subsection turning the relevant items below into GIVEN/WHEN/THEN forbidden-path scenarios.

- **M0 — Hello FastAPI:** `.gitignore` in place; no secret in code; `/health` leaks nothing; the sandbox endpoint is throwaway and not shipped as a real write path.
- **M1 — Auth & roles:** bcrypt; JWT secret from env; verify on every route; `exp` + pinned alg; `is_admin` re-read from DB; login rate-limit; uniform login error (no enumeration); 401 paths.
- **M2 — Listing builder + uploads:** `owner_id` from JWT; no client self-publish (`status` ignored); `PUT` on another's listing → 403; upload type/size whitelist; server-generated filename; path confined to `uploads/{listing_id}/`; upload to another's listing → 403.
- **M3 — Admin curation:** `require_admin` (from DB); status-transition guards (409); no seller path to set `live`; reject reason stored; approve/reject by non-admin → 403.
- **M4 — Marketplace browse:** `ListingPublic` response_model — **no identity leak** (schema-leak test); only `live` returned (drafts never appear, even to the owner, via public route); filters are parameterized; pagination capped.
- **M5 — Platform NDA + access gate (crown jewels):** every state tested — unsigned NDA (403 on request), no request (403), `requested` (403), `approved` (200), owner (200), `denied` (403); unique-constraint duplicate (409); only the listing's seller may approve/deny; document download enforces the **same** gate; revocation re-denies.
- **M6 — Chat:** authN on WS connect; membership authZ; sender from token (spoof ignored); history 403 for non-members; message size/rate caps; XSS-safe render.
- **M7 — Offers:** requires approved access **and** live listing (else 403/409); atomic accept (offer + listing in one transaction); seller-only decisions; 409 on already-decided; `offer_event` audit row written.
- **M8 — Saved searches & alerts:** notifications scoped to the caller; the background fan-out doesn't leak private data or create cross-user notifications.
- **M9 — Watchlist:** every operation caller-scoped; a user only ever sees/edits their own items.
- **M10 — Buyer verification:** buyer cannot self-verify (`verified` ignored/403); only admin flips it; proof-of-funds upload obeys the M2 upload rules.
- **M11 — Valuation calculator:** pure client calc; if a `POST /valuation` endpoint is added, validate inputs and keep it injection-safe; no data exposure.
- **After Phase D — E2E golden path:** the Playwright run exercises the full trust chain (sign-up → gated data → offer) — a passing golden path is also a security regression check.

---

## 8. Security in the SDD loop — apply at every step

1. **Spec (`/new-spec`):** add a **"Security & abuse"** subsection from §6 + §7 — the forbidden-path scenarios as GIVEN/WHEN/THEN, citing the FR and the control here.
2. **Tests (before code):** every `401/403/404/409` is one failing test first (permission tests = crown jewels). Include the negative tests: IDOR, mass-assignment, path traversal, spoofed identity, schema-leak.
3. **Implement:** gate first (default-deny) → validate input → parameterized query, caller-scoped → shape output (`response_model`) → secrets from env.
4. **Review (the `/dod` green gate + the inline branch review every milestone; an independent `appsec-engineer` pass on the security-critical milestones M1/M2/M5/M7/M10) — touched → must-cover matrix:**

   | If the change touches… | It must have a passing negative test for… |
   |---|---|
   | **Auth** | expired/invalid/missing token → 401; role re-checked from DB |
   | **Permissions / a new route** | wrong identity → 403/404; IDOR on the object |
   | **Create / PUT** | mass-assignment of `status`/`owner_id`/`is_admin`/`verified`/price ignored |
   | **Data exposure / public route** | `response_model` leak test (no private/identity fields) |
   | **Uploads** | path traversal + wrong-owner + type/size |
   | **Money / offers** | atomic transition + illegal-state 409 + audit row |
   | **WebSocket** | non-member connect/read rejected; spoofed sender ignored |

   A milestone is not done until the matrix rows it touched are green (this is on top of the constitution's "full `npm test` green").

---

## 9. Deferred-but-designed — deploy-time hardening

These are post-MVP but decided now so nothing is retrofitted blindly:

- **TLS everywhere** (`https://` + `wss://`), HSTS.
- **Security headers:** `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, `Strict-Transport-Security`.
- **Rate limiting / WAF** at the reverse proxy (the "App Check" equivalent the research docs defer).
- **Secrets manager**, DB least-privilege role, automated backups, reviewed Alembic migrations.
- **Postgres RLS** as optional defense-in-depth (the API stays the primary gate).
- **Monitoring/alerting** on auth-failure and 403 spikes; centralized log aggregation (Sentry equivalent) — scrubbed of secrets/PII.

---

## 10. Architecture verdict (recorded)

The current architecture (`design_implementation.md` Part 2–3, `diagrams/nextowner_system_architecture`) is **security-sound and needs no structural rewrite** — it is built on "the API is the only door," `permissions.py` one-function-per-boundary, the public/private table split, bcrypt/JWT, and permission-checked uploads.

**Additive items to introduce as the build reaches them** (not rewrites):
- A **config/secrets module** (`.env` → `pydantic-settings`) as the home for the JWT signing key and future vendor keys — introduce in **M1**.
- **Auth rate-limiting** — introduce in **M1**.
- **Deploy-time hardening** (§9) — TLS, security headers, WAF/rate-limit middleware — post-MVP.

**Optional diagram touch-ups** (additive, if desired): a `config/.env — JWT secret & settings` node in the backend zone, a `rate-limit` annotation on the `/auth` path, and an explicit "TRUST BOUNDARY — all browser input untrusted" label on the single-origin bar. Edit `diagrams/diagGenerator/elements_d2.json` and regenerate with `/gen-diagrams`.
