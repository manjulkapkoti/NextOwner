# Spec pre-011 — Rate limiting the routes that never got it

> **Not a milestone** — a hardening pass inserted before M11, numbered `pre-011` per constitution Article 4 so no M-number or spec number shifts. It ships no new user-facing capability; it closes a control that four separate milestones each deferred.
> **Security-critical** by content (it *is* a security control), so it takes an independent `appsec-engineer` pass before its PR opens, the same as a crown-jewel milestone.

## Why now

`docs/security.md` §9 records the same missing control four times, each deferral individually reasonable:

| Recorded at | Surface | The abuse it leaves open |
|---|---|---|
| M4 (2026-07-25, in `progress.md`) | public browse / search | unbounded request volume per IP; pagination caps per-request cost, nothing caps the rate |
| M5 (2026-07-20) | `POST /listings/{id}/access-request` | one signed buyer fans out across every live listing and fills every seller's queue |
| M8 (2026-07-26) | `POST /auth/forgot-password` | limited per **caller**, but the cost lands on the **target** — N IPs pile reset mail on one victim |
| M10 (2026-07-28) | both document upload routes | the D8 quota is read-then-insert, and with no rate limit the race window is however many connections one account opens |

**Four deferrals of one control is not four small decisions; it is one accumulating one.** M11 would have made it five, on the worst surface yet — an unauthenticated form that causes outbound email. The owner's call (2026-07-28) was to close all of them in one pass *before* M11 rather than add a fifth entry.

Nothing here is new machinery: `ratelimit.py`'s `RateLimiter` + `RateLimiterBackend` seam has existed since M1. This pass wires it to the routes that never got it, and fixes two structural problems that only become visible once there is more than a handful of limiters.

## Decisions

- **D1 — One shared enforcement helper, not `if not limiter.check(key)` copied per route.** M10 established the precedent that mattered here: two copies of an upload validator was the one shape guaranteed to drift, so it became `uploads.py`. The same reasoning applies harder to a limiter, because a *forgotten* check fails silently and open — nothing errors, the route simply has no limit. One helper builds the key, counts the hit, and raises.
- **D2 — Authenticated routes key on the user id; anonymous routes key on the client IP.** Keying an authenticated route on IP is wrong in both directions: one account evades its limit by moving IP, while an office or mobile-carrier NAT punishes every user behind it for one abuser. The identity is already server-derived from the JWT on these routes, so use it. Anonymous routes have nothing else to key on.
- **D3 — `X-Forwarded-For` is ignored by default, and honoured only when `trusted_proxy_count > 0`.** Today every limiter keys on `request.client.host`. Behind a production reverse proxy that is the *proxy's* address, so all callers share one bucket and every limit becomes decorative precisely where it matters most. The fix cannot be "trust the header": a client can send `X-Forwarded-For` itself, and a limiter that trusts it unconditionally is *weaker* than no limiter, because the attacker picks a fresh key per request. So the number of trusted proxies is **configuration**, defaults to `0` (= current behaviour, correct for local dev), and at `n > 0` the address is taken `n` positions from the **right** of the header — the leftmost entries are attacker-supplied and the rightmost `n` are written by our own infrastructure.
- **D4 — A limiter registry, so the test fixture cannot fall behind.** `conftest.py`'s autouse `_fresh_rate_limiters` currently resets limiters by name, guarded by `hasattr` for the ones that did not exist yet. Going from 4 limiters to 9 makes that list a maintenance hazard whose failure mode is *silent cross-test pollution* — a limiter left hot by an earlier test makes a later one 429 for reasons unrelated to what it asserts. `RateLimiter` instances register themselves; the fixture resets whatever is registered.
- **D5 — Limits are per-surface config, not one global number.** Browse is a read a real user does constantly; a password-reset request is something a real user does twice a year. One number cannot serve both. Each surface gets its own `*_rate_limit_max` / `*_rate_limit_window_seconds` pair, following the `forgot_password_rate_limit_*` naming M8 established.
- **D6 — The forgot-password fix is a *second* cap, keyed on the address, not a replacement for the per-IP one.** They defend different victims: the per-IP cap stops one attacker burning our mail budget, the per-address cap stops N attackers burying one person's inbox. Both apply.
- **D7 — 429 carries `Retry-After`.** The `RateLimited` error already maps to 429 `rate_limited`. A client that is told to back off but not for how long will poll, which is the behaviour the limiter exists to prevent.
- **D8 — Not in scope: a shared (Redis-class) backend.** The in-process backend stays, and the per-instance limitation stays recorded in §9 — behind a load balancer N instances still allow N× the limit. That is a deployment change (the seam is already there for it), and pretending otherwise in this pass would be the "decoration" `security.md` §7 warns about. What this pass fixes is *routes with no limit at all*, which is a strictly worse problem than *a limit that is N× too loose on infrastructure we do not yet run*.

## Acceptance criteria

> Each becomes exactly one test, written failing first. **R** the limits themselves · **S** the abuse each one blocks, including the ways a limiter can be worse than useless.

- **R1** — GIVEN an anonymous visitor who has made exactly `browse_rate_limit_max` requests to `GET /api/listings` inside the window, WHEN they make one more, THEN 429 with code `rate_limited`.
- **R2** — GIVEN an anonymous visitor under the browse cap, WHEN they page through results normally, THEN every request succeeds — the limit does not break the ordinary reading pattern the marketplace depends on.
- **R3** — GIVEN a buyer who has requested access to `access_request_rate_limit_max` listings inside the window, WHEN they request one more, THEN 429 `rate_limited` and no new `AccessRequest` row is written.
- **R4** — GIVEN a seller at the listing-document upload rate cap, WHEN they upload again, THEN 429 `rate_limited` — distinct from M10's 413 `upload_quota_exceeded`, which is about how much is *stored*, not how fast it arrives.
- **R5** — GIVEN a buyer at the verification-document upload rate cap, WHEN they upload again, THEN 429 `rate_limited`.
- **R6** — GIVEN `forgot_password_address_rate_limit_max` reset requests for one email address, each from a **different** client IP so no per-IP cap is reached, WHEN another arrives for that same address, THEN it is refused and no further mail is dispatched (D6 — the victim-side cap M8's §9 note asked for).
- **R7** — GIVEN any rate-limited response, WHEN inspected, THEN it carries `Retry-After` and the generic `{detail, code}` body — no internal detail, no hint of how the key was derived (D7).
- **S1** — GIVEN an authenticated route and two *different* users behind one shared client IP, WHEN user A exhausts their limit, THEN user B is unaffected — authenticated routes key on the JWT-derived identity, never the address (D2). *A NAT'd office sharing one bucket is a self-inflicted outage, and this is the test that would catch it.*
- **S2** — GIVEN one authenticated user who exhausts a limit and then presents the same token from a different client address, WHEN they retry, THEN still 429 — the other half of D2: changing IP must not reset an identity-keyed limit.
- **S3** — GIVEN `trusted_proxy_count = 0` (the default) and a client that sends its own `X-Forwarded-For` header, WHEN it varies that header on every request, THEN the limit still applies — a spoofable key would make the limiter weaker than none at all (D3). **This is the crown jewel of this pass.**
- **S4** — GIVEN `trusted_proxy_count = 1`, WHEN requests arrive carrying `X-Forwarded-For: <client>, <our-proxy>`, THEN callers are limited per *client* address rather than all sharing the proxy's — the deployment case D3 exists for, with the address taken from the right.
- **S5** — GIVEN every `RateLimiter` the app constructs, WHEN the test fixture resets the registry, THEN all of them are cleared — so no limiter can be added later that silently leaks state between tests (D4). *Verified by asserting the registry's size against the limiters the app actually builds, so a new unregistered limiter fails this.*

## Errors & failure modes

- **429 `rate_limited`** with `Retry-After` on every capped surface (R1, R3–R6, R7). The `RateLimited` class and its handler already exist from M1 — no new error machinery.
- **Fail closed, but do not fail the wrong request:** a limiter check happens *before* the work and before any write, so a refused request leaves no row and no file (R3 asserts the row's absence).
- **The forgot-password refusal stays enumeration-safe** (M8 G2/G14): the response for a rate-limited address must remain indistinguishable from an ordinary one, so R6 asserts the *mail* was not dispatched rather than expecting a distinguishable status — a 429 there would tell an attacker the address is real and popular.

## Out of scope

- **A shared/Redis backend** (D8) — the seam exists; using it is a deployment change, and §9 keeps the per-instance note.
- **A WAF / edge rate limiting** — §9's reverse-proxy item stands; this pass is defence in the application, which is where it belongs regardless of what sits in front.
- **Rate-limiting authenticated read routes generally** (`/my/listings`, the conversation list, notifications). No recorded abuse case, and a limit on a route a logged-in user's own dashboard polls is a support ticket waiting to happen. The four surfaces here are the ones with a written abuse story.
- **Per-route limits on the WebSocket** — M6 already caps inbound frames, and that cap counts every frame including invalid ones (the M6 lesson). Untouched.
