# Plan pre-011 — Rate limiting the routes that never got it

> Implementation plan for [`spec.md`](./spec.md). No schema changes at all — this pass adds no table, no column and no response field. It is config, one helper, one registry, and nine call sites.

## Schema deltas

**None.** Rate-limit state lives in the in-process backend, not the database (D8). Worth stating explicitly so nobody looks for a migration.

## `config.py` — per-surface limits (D5)

Following the `forgot_password_rate_limit_*` naming M8 established. Values are deliberately generous for reads and tight for anything that costs someone else something:

| Setting | Default | Reasoning |
|---|---|---|
| `browse_rate_limit_max` | `120` | Per IP per minute. A real visitor paging and filtering fires a handful per minute; 120 is well clear of human use and still bounds a scraper. |
| `browse_rate_limit_window_seconds` | `60` | |
| `access_request_rate_limit_max` | `10` | Per **user** per hour. A genuine buyer asks for access to a few listings in a sitting; 10/hour makes the fan-out attack (M5's §9 note) slow enough to be pointless. |
| `access_request_rate_limit_window_seconds` | `3600` | |
| `upload_rate_limit_max` | `20` | Per **user** per hour, shared by both document routes. Complements M10's *stored* quota (20 files / 50 MB) with a bound on *arrival rate* — which is what actually narrows the read-then-insert race D11 accepted. |
| `upload_rate_limit_window_seconds` | `3600` | |
| `forgot_password_address_rate_limit_max` | `3` | Per **email address** per hour — the victim-side cap (D6), alongside M8's existing per-IP `3 / 15 min`. |
| `forgot_password_address_rate_limit_window_seconds` | `3600` | |
| `trusted_proxy_count` | `0` | **The security-relevant one** (D3). `0` = ignore `X-Forwarded-For` entirely, which is correct locally and safe everywhere. A deployment behind one reverse proxy sets `1`. |

## `ratelimit.py` — the helper and the registry

**`RateLimiter` self-registers** (D4). A module-level `_REGISTRY: list[RateLimiter]`, appended in `__init__`, plus:

```python
def reset_all() -> None:
    """Clear every registered limiter — the test fixture's single entry point."""
```

`conftest.py`'s autouse `_fresh_rate_limiters` becomes `ratelimit.reset_all()` and stops naming limiters. That deletes the `hasattr` guards it needed for limiters that did not exist in earlier slices, and — the actual point — makes it impossible to add a limiter the fixture forgets.

**`client_ip(request) -> str`** — the D3 decision, in one place:

```python
def client_ip(request: Request) -> str:
    """The address to key an anonymous limit on.

    `X-Forwarded-For` is a client-supplied header. Trusting it unconditionally
    makes a limiter *weaker than none*: the caller picks a fresh key per request
    and the counter never reaches its cap. So it is read only as far as
    `settings.trusted_proxy_count` entries from the RIGHT — those were appended
    by infrastructure we run, while everything to their left is attacker input.
    """
```

**`enforce(limiter, key, *, retry_after) -> None`** — counts the hit and raises `RateLimited` with `Retry-After` (D1, D7). One function, so a route cannot half-implement the check.

Two thin wrappers over it, because the keying rule (D2) is the part most likely to be got wrong at a call site:

- `enforce_per_ip(limiter, request)` → key `f"{limiter_name}:ip:{client_ip(request)}"`
- `enforce_per_user(limiter, user)` → key `f"{limiter_name}:user:{user.id}"`

**Where each limiter is constructed** — the first draft of this plan left this unstated, and the failing-test pass caught what that ambiguity costs: `_upload_limiter` is described as "shared by both document routes", but if each router builds its own instance then R4 and R5 both still pass while the shared budget quietly does not exist (hence the new **R8**). So, explicitly:

| Limiter | Module | Why there |
|---|---|---|
| `_browse_limiter` | `routers/listings.py` | Only that router's public reads use it. |
| `_access_request_limiter` | `routers/access.py` | Single consumer. |
| **`_upload_limiter`** | **`app/uploads.py`** | **Two consumers, so it belongs with the seam they already share.** M10 moved the validator and the storage backend there for exactly this reason — one object, imported by both routers, so "shared budget" is true by construction rather than by two modules agreeing. A second instance is then not constructible without deleting the import. |
| `_forgot_password_address_limiter` | `routers/auth.py` | Beside the per-IP limiter it complements (D6). |

Namespacing the key by limiter matters: two limiters sharing a backend would otherwise share a counter for the same IP, and browse traffic would exhaust the upload cap.

## Call sites (nine, all one line each)

| Route | Limiter | Keyed on | Criterion |
|---|---|---|---|
| `GET /api/listings` | `_browse_limiter` | IP | R1, R2, S3, S4 |
| `GET /api/listings/{id}` | `_browse_limiter` | IP | shares the counter — a scraper walking ids is the same abuse as walking pages |
| `POST /api/listings/{id}/access-request` | `_access_request_limiter` | **user** | R3, S1, S2 |
| `POST /api/listings/{id}/documents` | `_upload_limiter` | **user** | R4 |
| `POST /api/verification/documents` | `_upload_limiter` | **user** | R5 |
| `POST /api/auth/forgot-password` | `_forgot_password_address_limiter` | **email address** | R6 |

Existing limiters (login, register, forgot-password-per-IP, chat frames) are **not** re-tuned — they work, they have tests, and changing their numbers in a pass about missing limits would muddle what this branch proves. They are only migrated onto the registry and `client_ip`.

## Frontend

**None.** No new route, no new state. A 429 already surfaces through `api.ts`'s error path, and `error_handling.md` §3's toast covers it. Deliberately no retry/backoff UI: a client that automatically retries a rate limit is the polling behaviour D7's `Retry-After` exists to discourage.

## Build order

Four slices, one commit each. The red test list is the status — no checkboxes.

1. **The seam: registry + `reset_all()` + `client_ip()` + `enforce*()`, and `conftest.py` migrated onto the registry.** → **S5, S3, S4**. *First, and deliberately including the two `X-Forwarded-For` criteria: they test `client_ip` itself, which every later slice depends on. Getting the key derivation wrong makes every limit that follows either evadable (S3) or shared across all users (S4), so it is proven before anything is keyed with it. The `conftest.py` migration lands here too — from this commit on, a new limiter is reset automatically, which is what keeps the later slices' tests honest.*
2. **The anonymous surface: browse + detail.** → **R1, R2, R7**. *Second because it is the only IP-keyed pair, so it exercises `enforce_per_ip` end to end while the authenticated keying is still unwritten. R7's `Retry-After` assertion lands here since this is the first route that can 429.*
3. **The authenticated surfaces: access-request + both upload routes.** → **R3, R4, R5, S1, S2**. *Third: `enforce_per_user` and the D2 keying rule, including the two tests that pin it in both directions (two users on one IP must not share; one user on two IPs must). Grouped rather than split per route because they are one rule applied three times — splitting would give three commits that each re-prove the same property.*
4. **The forgot-password address cap.** → **R6**. *Last, and separate, because it is the only limiter keyed on something that is neither an address nor an authenticated identity, and the only one whose refusal must stay **enumeration-safe** (M8 G2/G14): the response cannot become distinguishable for a popular address, so the test asserts the mail was not dispatched rather than a visible status. That constraint is unique to this slice and does not want to be tangled with slice 3's.*

**Independent `appsec-engineer` pass** after slice 4. This branch *is* a security control, so it takes the crown-jewel treatment despite not being a numbered milestone — and the specific question for it is whether `client_ip` can be made to lie.

**Then `security.md` §9:** the four deferral entries collapse into one note recording that the routes are now limited in-application, with the per-instance (`N×` behind a load balancer) and WAF items **kept** — those are still true and still deferred (D8).
