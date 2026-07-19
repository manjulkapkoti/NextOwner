# Spec 001 — Auth & Roles (M1)

> **Milestone:** M1 — Auth & roles ([`design_implementation.md`](../../docs/design_implementation.md) Part 4 → *Milestone 1*).
> **Complies with:** [`specs/000-constitution.md`](../000-constitution.md). **Security is the owner's #1 priority** — the forbidden-path tests below are the crown jewels.
> **Status:** ✅ shipped — merged as #22. *(Decisions D1/D2 resolved 2026-07-17, § Decisions.)*

---

## FR references

| FR | What it requires | This milestone |
|---|---|---|
| **FR-1** | Register/sign in with **email + password**; sessions use short-lived tokens with refresh | Email+password **yes**. **Refresh → deferred (owned), M1 is access-token-only** (D1). *Google OAuth is **(Post-MVP)** — excluded (`requirements.md` FR-1, 2026-07-17).* |
| **FR-2** | A user selects a role (buyer/seller); **may hold both** under one account | Yes |
| **FR-3** | Buyers complete a profile: budget, target industries, experience | **Minimal** subset — display name + those three fields. Proof-of-funds → M10 |
| **F1** | MVP feature: email+password auth, buyer/seller roles | Yes |

**Also lands here (not FR-driven, but binding):**
- **`docs/error_handling.md` §7** — *"Foundation built at M1"*: `errors.py` + global handlers + request-id middleware + `ApiError` + `ErrorBoundary` + global snackbar. M1 is the first milestone with real error paths, so the contract lands here and every later milestone reuses it.
- **`docs/data_protection.md` §3** — the `user` table ships **erasure-ready** at M1.
- **`docs/milestones.md` § Scope fold-ins → M1** — all ten items.

---

## Decisions (resolved 2026-07-17)

**D1 — Refresh tokens: DEFER, to an owner (not to limbo).** M1 ships **access-token-only**. Refresh tokens + the httpOnly-cookie session they need are deferred to the **deploy-hardening pass** (`security.md` §9 — *Session hardening*), triggered by *a real deployment / real users* — recorded and owned, so it surfaces when actually needed instead of rotting in a `(Post-MVP)` tag. FR-1 amended deliberately (`requirements.md`), meeting the fold-in's *"amend, don't drift."* This is safe precisely because M1 states its token-storage approach (below): `get_current_user` trusts the JWT (not the auth method) and `api.ts` is the single frontend choke point, so refresh becomes a new table + endpoint + one interceptor later — not a rewrite.

**D2 — Accept the 12-slice Build order.** The error-contract foundation (`error_handling.md` §7) is **M1-mandated infrastructure** — the doc assigns it to "the first API milestone" — with no FR of its own; splitting it out would ship a featureless milestone and renumber M2–M12. Building **slice by slice** is itself the mitigation for milestone size, so 12 small, independently-verifiable slices is fine, not a red flag.

**Token storage — stated per `security.md` § Frontend session (which requires the M1 spec to declare it):** M1 stores the **short-lived access token in `localStorage`** — acceptable for the 100%-local MVP with no real users; the XSS tradeoff is recorded here and in §9. **Production approach: httpOnly cookie (+ CSRF) + refresh**, deferred to §9 (D1). Because `api.ts` is the single choke point, that later switch is localized.

---

## User stories

1. **As a visitor,** I want to register with an email and password and pick a role, so that I can act as a buyer or a seller.
2. **As a registered user,** I want to log in and stay logged in, so that I don't re-authenticate on every request.
3. **As a buyer,** I want to add my budget, target industries, and experience, so that a seller can judge my access request later (M5).
4. **As a buyer,** I want to also become a seller without a second account, so that one identity covers both sides.
5. **As an admin,** I want admin-only routes to be closed to everyone else, so that curation (M3) can't be hijacked.
6. **As any user,** I want failures to be clear and safe, so that I'm never shown a stack trace or told which half of my credentials was wrong.

---

## Acceptance criteria

**Each scenario = exactly one test, written failing first.** Paths omit `/api` for readability; **test code always includes it** (Article 4).

### A. Registration

- **A1** — GIVEN no user with `alice@example.com`, WHEN `POST /auth/register` with a valid email, password, and role `buyer`, THEN 201 and the user exists with that email and role.
- **A2** — GIVEN a registration succeeded, WHEN the stored row is inspected via the `session` fixture, THEN `password_hash` is a **bcrypt hash** — not the plaintext, and not reversible.
- **A3** — GIVEN a registration succeeded, WHEN the stored row is inspected, THEN **`tos_accepted_at` is stamped** and `tos_version` records which text was accepted.
- **A4** — GIVEN an existing user with `alice@example.com`, WHEN registering that email again, THEN **409** (`code: "email_taken"`).
- **A5** — GIVEN a registration request with role `"wizard"`, WHEN posted, THEN **422** (field-level).
- **A6** — GIVEN a registration request with `"email": "not-an-email"`, WHEN posted, THEN **422** with `loc` pointing at `email`.
- **A7** *(added from appsec review)* — GIVEN a registration with a password shorter than the minimum, WHEN posted, THEN **422** (`security.md` §2 — a minimum length is enforced at the boundary).
- **A8** *(added from appsec review)* — GIVEN a registration with a very long passphrase (>72 bytes), WHEN posted, THEN **201** (not a 500 — bcrypt's 72-byte limit is handled by a SHA-256 pre-hash), it logs in with the full password, and a 72-byte-truncated version does **not** (no silent truncation).

### B. Login & tokens

- **B1** — GIVEN a registered user, WHEN `POST /auth/login` with the correct password, THEN 200 and a JWT whose `sub` is that user's id.
- **B2** — GIVEN a registered user, WHEN logging in with the **wrong password**, THEN **401**.
- **B3** — GIVEN **no** user with that email, WHEN logging in, THEN **401 with a byte-identical body to B2** — no user enumeration.
- **B4** — GIVEN a valid token, WHEN `GET /auth/me`, THEN 200 and the caller's own record (email, roles, profile) — and **never** `password_hash`.

### C. `get_current_user` — trust boundary #1

- **C1** — GIVEN no `Authorization` header, WHEN `GET /auth/me`, THEN **401**.
- **C2** — GIVEN a token whose `exp` is in the past, WHEN `GET /auth/me`, THEN **401** (`code: "token_expired"`).
- **C3** — GIVEN a token whose **signature is tampered**, WHEN `GET /auth/me`, THEN **401**.
- **C4** — GIVEN a token signed with **`alg: none`** (algorithm-confusion attack), WHEN `GET /auth/me`, THEN **401** — the verifier pins the algorithm.
- **C5** — GIVEN a valid token for a user who has since been **anonymized/soft-deleted**, WHEN `GET /auth/me`, THEN **401** — identity is re-read from the DB, not trusted from the token.

### D. `require_admin` — trust boundary #2

- **D1** — GIVEN a valid token for a non-admin, WHEN calling an admin-only probe route, THEN **403**.
- **D2** — GIVEN a valid token for a user who was **made admin in the DB after the token was issued**, WHEN calling the admin route, THEN **200** — `is_admin` is re-read from the DB per request, never read from the token.
- **D3** — GIVEN a registration or profile-update payload containing **`"is_admin": true`**, WHEN posted, THEN the flag is **ignored** and the stored user is not an admin (mass-assignment).

### E. Roles & profile

- **E1** — GIVEN a user registered as `buyer`, WHEN they call the role-upgrade endpoint for `seller`, THEN they hold **both** roles (FR-2).
- **E2** — GIVEN an authenticated buyer, WHEN `PUT /profile` with display name, budget, industries, experience, THEN 200 and the fields persist on **their own** record.
- **E3** — GIVEN authenticated user A, WHEN A attempts `PUT /profile` targeting user B's id, THEN **403/404** — the server derives the target from the JWT and ignores any client-supplied id (IDOR + never-trust-the-client).

### F. Login abuse

- **F1** — GIVEN the configured failed-login threshold, WHEN it is exceeded from one caller, THEN **429** and further attempts are rejected for the window.
- **F2** — GIVEN the rate limiter, WHEN inspected, THEN its **store is behind an interface** — swapping to a shared backend is a config change, not a rewrite (fold-in / horizontal-scale blocker #1).
- **F3** *(added from appsec review)* — GIVEN repeated registrations from one caller, WHEN the threshold is exceeded, THEN **429** (`security.md` §1.1 requires rate-limiting **register** too, not only login — signup spam).

### G. The error contract (`error_handling.md` §7)

- **G1** — GIVEN a route that raises an unhandled exception, WHEN called, THEN **500** with the generic contract `{detail, request_id}` and **no** stack trace, SQL, exception class, or file path.
- **G2** — GIVEN any error response, WHEN inspected, THEN the 4xx shape carries a stable machine `code` alongside `detail`.
- **G3** — GIVEN a request with an `X-Request-ID` header, WHEN it errors, THEN the same id is echoed in the response and appears in the server log line.

### H. Frontend

- **H1** — GIVEN a logged-out visitor, WHEN they navigate to `/sell`, THEN they are redirected to login. *(Client-side guards are UX only — the server gate is the real boundary.)*
- **H2** — GIVEN the API returns 401, WHEN `api()` handles it, THEN it throws a typed **`ApiError`** carrying `status` and `code` — not a bare `Error`.
- **H5** *(added from appsec review)* — GIVEN the API returns 401, WHEN `api()` handles it, THEN it **clears the stale token** and emits an `auth:unauthorized` event so the app redirects to login (plan slice 9 / `security.md` §3 — global 401 handling).
- **H3** — GIVEN the login form receives a **422**, WHEN rendered, THEN the message appears **inline on the offending field**.
- **H4** — GIVEN a render-time crash inside a route, WHEN it happens, THEN the **`ErrorBoundary`** fallback renders — never a white screen.

### I. Cleanup

- **I1** — GIVEN M1 is complete, WHEN `POST /api/sandbox` or `GET /api/sandbox` is called, THEN **404** — the throwaway unauthenticated write path is gone, along with `SandboxItem` and its two M0 tests.

---

## Security & abuse

*(From `security.md` §7 M1 + the §6 edge cases. These are the crown jewels — written first.)*

| Threat (§6) | Covered by |
|---|---|
| **Token attacks** — expired, tampered, `alg:none`, token for a deleted user, missing token | C1–C5 |
| **Role changed after issuance** — token says non-admin, DB says admin (and vice versa) | D2 |
| **Mass assignment** — `is_admin` via register/profile | D3 |
| **Login abuse** — brute force / credential stuffing | F1 |
| **User enumeration** — distinct errors for unknown email vs wrong password | B3 (byte-identical bodies) |
| **IDOR** — writing another user's profile | E3 |
| **Info leakage** — 500 exposing SQL/stack; `password_hash` in a response | G1, B4 |
| **Secrets** | JWT signing key from `.env` via `pydantic-settings` — never hardcoded, never logged, never committed. `.env.example` ships with placeholders |

**Not negotiable in implementation:** bcrypt for passwords · JWT `exp` + **pinned algorithm** (reject `none` and algorithm confusion) · `is_admin` **re-read from the DB every request** · uniform login failure (same body *and* no timing oracle from an early return) · default-deny on every non-public route.

---

## Errors & failure modes

*(From `error_handling.md`. M1 builds the foundation — §7.)*

| Path | Status | `code` | Test |
|---|---|---|---|
| Invalid email / role | 422 | field-level shape | A5, A6 |
| Duplicate email | 409 | `email_taken` | A4 |
| Bad credentials / unknown email | 401 | `unauthorized` (identical bodies) | B2, B3 |
| Expired token | 401 | `token_expired` | C2 |
| Invalid/tampered/`alg:none` token | 401 | `unauthorized` | C3, C4 |
| Non-admin on admin route | 403 | `forbidden` | D1 |
| Rate limited | 429 | `rate_limited` | F1 |
| Unhandled exception | 500 | generic + `request_id`, no internals | G1 |

**Frontend:** `ApiError` from `api.ts` (H2) · global 401 → clear session + redirect · inline 422 (H3) · `ErrorBoundary` (H4) · snackbar for 409/500/network · login form has **loading / error** states.

---

## Data protection

- **`user` ships erasure-ready** (`data_protection.md` §3): an anonymization path in the schema from day one — `deleted_at` + PII fields nullable/replaceable (email → `deleted-user-{id}@nextowner.invalid`). **The user-facing erasure endpoint is *not* in M1** (it's a GDPR flow → `legal-compliance`); only the schema support is. C5 is the security half of this: an anonymized user's live token must stop working.
- **PII added:** `email` (identifier — never on a public `response_model`, never logged), `password_hash` (never returned — B4), profile fields (budget/industries/experience — private to the user until M5's seller view).
- `track()` events carry **no** identity fields.

---

## Out of scope (deliberately deferred)

- **Google OAuth** — FR-1 marks it (Post-MVP). Needs a cloud account, which Article 1's "100% local" rule excludes.
- **Refresh tokens** — deferred to deploy-hardening (`security.md` §9), **owned + triggered** (D1). M1 is access-token-only; production token storage becomes httpOnly cookie + refresh at that trigger.
- **Password reset + email verification** — moved to **M8** (2026-07-17), which owns the email channel. ⚠ M1–M7 therefore have no self-serve reset; fine while local with no real users.
- **Proof-of-funds upload / verified badge** — M10.
- **A real admin UI** — `is_admin` is set by hand in the DB at M1; the admin queue is M3.
- **A user-facing erasure endpoint** — schema support only (above).

### Deferred security decisions (recorded from the appsec review, 2026-07-17 — owner may override)

The independent appsec pass raised two items that are **judgment calls, not clear-cut fixes**. Recorded here as deliberate deferrals with rationale (rather than shipped silently), per the reviewer's own recommendation:

- **Registration-time email enumeration** (`409 email_taken` vs `201` reveals whether an email is registered). This is the industry-standard signup UX; making it non-enumerable requires a *"we've sent you an email"* confirmation flow that never confirms existence — which **is** the email-verification work already moved to **M8**. **Decision: accept for M1, close it at M8** with verification. (The login path is already enumeration-safe — B3.)
- **Frontend not wired into an app shell** — `RequireAuth` / `LoginForm` exist and are unit-tested (H1, H3) but `App.tsx` has no `/login` or `/sell` route yet. No security hole (the server JWT gate is unconditional), but the integrated flow isn't live. **Decision: defer integration to M2**, which adds the first real authed pages to route between; the end-to-end flow is covered by the **Phase-D Playwright E2E**. Wiring a router now would rewrite the M0 health page for no user-visible gain.
