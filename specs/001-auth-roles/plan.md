# Plan 001 — Auth & Roles (M1)

> The *how* for [`spec.md`](./spec.md). Schema, endpoints, gates, and the **Build order** (the implementation slices).

---

## Schema deltas

`backend/app/models.py` — one new table. **`SandboxItem` is deleted** (slice 11).

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)          # PII — never on a public response_model
    password_hash: str                                    # bcrypt — never returned
    is_buyer: bool = Field(default=False)                 # FR-2: both roles under one account
    is_seller: bool = Field(default=False)                #   → two flags, not one enum
    is_admin: bool = Field(default=False)                 # server-only; re-read per request
    # profile (FR-3, minimal)
    display_name: str | None = None
    budget: Decimal | None = None                         # money is Decimal, never float (M2 fold-in, applied early)
    target_industries: str | None = None
    experience: str | None = None
    # legal record
    tos_accepted_at: datetime | None = None
    tos_version: str | None = None
    # erasure-ready (data_protection.md §3) — schema support only; no endpoint in M1
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)
```

**Why two role booleans, not a `role` enum:** FR-2 says a user *may hold both* roles. An enum would force a third `both` value and a migration the first time someone upgrades. Two flags make E1 a one-line change.

**Erasure behaviour:** anonymize-in-place, never hard-delete — `email` → `deleted-user-{id}@nextowner.invalid`, profile fields nulled, `deleted_at` set, the row (and its future FKs) kept for audit.

---

## Endpoints

| Method + path | Gate | Notes |
|---|---|---|
| `POST /api/auth/register` | — (public) | 201; server ignores `is_admin`/`is_seller` escalation in the body |
| `POST /api/auth/login` | — (public) | OAuth2 password form → JWT. **Rate-limited.** Uniform 401 |
| `GET /api/auth/me` | `get_current_user` | The caller's own record; `UserRead` excludes `password_hash` |
| `POST /api/auth/roles` | `get_current_user` | FR-2 role upgrade — target is the caller, from the JWT |
| `PUT /api/profile` | `get_current_user` | FR-3. Target derived from JWT — a client-supplied id is ignored |
| `GET /api/admin/ping` | `require_admin` | A probe route so `require_admin` has a testable surface at M1 (D1/D2). The real admin queue is M3 |

## Permission gates

`backend/app/permissions.py` — **new file, one function per trust boundary** (Article 2 #1):

- **`get_current_user`** — decode JWT (**pinned alg**, verify `exp`) → **load the user from the DB** → reject if missing or `deleted_at` set. Never trusts claims beyond `sub`.
- **`require_admin`** — depends on `get_current_user`, then checks **`user.is_admin` from that DB row**. Never from the token.

## Response models

`backend/app/schemas.py`: `UserRead` (id, email, roles, profile, timestamps — **no `password_hash`**, by schema), `UserRegister`, `LoginResponse`, `ProfileUpdate` (profile fields only — no `is_admin`, no `email`; mass-assignment is impossible *by schema*, not by filtering).

## Errors

`backend/app/errors.py` (new): `AppError` + `NotFound` / `Forbidden` / `Unauthorized` / `InvalidTransition` / `Conflict` / `RateLimited`. Handlers registered in `main.py`; request-id middleware. Codes raised here: `email_taken`, `unauthorized`, `token_expired`, `forbidden`, `rate_limited`.

## Frontend

`app/src/`: `lib/api.ts` → throw typed `ApiError(status, code, detail)`; global 401 → clear + redirect. `stores/authStore.ts` (MobX: token + user; clear on logout). `components/ErrorBoundary.tsx`, a global snackbar, `RequireAuth` route guard on `/sell` + `/admin`, and a login/register form with **loading / error / inline-422** states.

## Analytics events

`track("user_registered", { role })` · `track("user_logged_in", {})` — **no email, no id, no PII** (`security.md` § Audit & logging).

## Data protection

Covered in `spec.md` § Data protection. Schema support only; **no erasure endpoint in M1**.

---

## Build order

**Ordered implementation slices — one trust boundary each** (Article 2 #1). Each ends with its named tests green and one Conventional Commit.

**Status is not tracked here.** `cd backend && pytest -q --lf` is the live to-do list, and the red count is the progress bar — `/resume` pairs the red set against this list to find the next slice. **This section has no checkboxes and must never get any:** it fixes the *order* (a design decision); the tests report the *state*. Mid-milestone the suite is **red by design** — that's the queue draining, not a broken build.

| # | Slice | Turns green | Why here |
|---|---|---|---|
| 1 | **Settings + secrets** — `pydantic-settings`, `DATABASE_URL` + `JWT_SECRET` from env, `.env.example`; `db.py` stops hardcoding | *(none — unblocks all)* | Everything below reads config. Fold-in: settings module owns `DATABASE_URL` |
| 2 | **Error contract** — `errors.py`, global handlers, request-id middleware | G1, G2, G3 | `error_handling.md` §7: the foundation lands at M1 and every later slice raises through it. Build it *before* the code that needs to fail correctly |
| 3 | **`User` model + `POST /auth/register`** — bcrypt, `tos_accepted_at`, erasure-ready columns | A1, A2, A3, A4, A5, A6 | First write path; no gate exists to guard yet. Raises `email_taken` through slice 2 |
| 4 | **`POST /auth/login` → JWT** | B1, B2, B3 | Needs a user (3) to authenticate. B3's uniform 401 is a *login* property, so it lands with login |
| 5 | **`get_current_user` — trust boundary #1** | B4, C1, C2, C3, C4, C5 | The gate everything below depends on. Pinned alg + DB re-read are *here*, not sprinkled at call sites |
| 6 | **`require_admin` — trust boundary #2** + `GET /admin/ping` | D1, D2, D3 | Depends on 5. D2 (role change after issuance) is the reason the DB re-read exists |
| 7 | **Login rate-limit behind a store interface** | F1, F2 | Guards slice 4; needs the error contract for 429. **Build the port, not Redis** — fold-in / horizontal-scale blocker #1 |
| 8 | **Roles + profile** — `POST /auth/roles`, `PUT /profile` | E1, E2, E3 | Needs 5. E3 (IDOR) is why the target comes from the JWT |
| 9 | **Frontend auth** — `ApiError`, `authStore`, `RequireAuth`, login form | H1, H2, H3 | Needs the API to exist. H3's inline 422 needs slice 2's contract |
| 10 | **Frontend error surfaces** — `ErrorBoundary`, global snackbar | H4 | Completes `error_handling.md` §7's frontend half |
| 11 | **Delete the sandbox** — `/api/sandbox` × 2, `SandboxItem`, and its **two M0 tests** | I1 *(and **removes** `test_sandbox_write_then_read_proves_db_path` + `test_fresh_db_per_test_has_no_leftover_rows`)* | **Last, deliberately.** This slice *deletes* tests rather than greening them — an explicit spec criterion (I1), because `/dod` forbids editing tests to pass. Removing it earlier turns the suite red for reasons unrelated to M1, and slice 3's fixtures still prove the DB path anyway |
| 12 | **Linters** — Ruff (`backend/`), ESLint (`app/`), `npm run lint`, CI step | *(no tests — tooling)* | Last: lint the finished code once, not each slice mid-flight. Fold-in, 2026-07-17 |

**If a slice reveals the order is wrong** (a dependency invisible at spec time), fix this table and say so in the commit — the plan is a design artifact, not a prophecy. **Never** reorder by weakening a test.
