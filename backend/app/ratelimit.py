"""Rate limiting — the limiters, the registry, and the one enforcement helper.

The in-process backend is the correct MVP implementation. It is **per-instance
state**, so behind a load balancer N instances would allow N× the limit — which
is why the store sits behind `RateLimiterBackend`: swapping to a shared
(Redis-class) backend is constructing `RateLimiter(backend=...)` differently, not
a rewrite. See `design_implementation.md` § Horizontal scale, and the F2 test.

**spec pre-011** added three things to this module, all of them structural:

- a **registry** (D4): every `RateLimiter` self-registers, so `reset_all()` — the
  test fixture's single entry point — cannot fall behind a limiter somebody adds
  later. The failure mode it closes is silent cross-test pollution, not a wrong
  answer.
- `client_ip()` (D3): the one place that decides what an anonymous limit keys on.
- `enforce()` / `enforce_per_ip()` / `enforce_per_user()` (D1, D2, D7): one helper
  that counts the hit **and** raises, because a limiter that a route forgets to
  check fails silently *open* — nothing errors, the route simply has no limit.
"""

from __future__ import annotations

import time
from typing import Protocol

from fastapi import Request

from .config import settings
from .errors import RateLimited


class RateLimiterBackend(Protocol):
    """The seam. A shared-store backend implements the same three methods."""

    def hit(self, key: str, window_seconds: int) -> int: ...
    def reset(self, key: str) -> None: ...
    def clear(self) -> None: ...


class InMemoryRateLimiterBackend:
    """Fixed-window counter in a dict. Single-instance only, by construction."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def hit(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        recent = [t for t in self._hits.get(key, []) if now - t < window_seconds]
        recent.append(now)
        self._hits[key] = recent
        return len(recent)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)

    def clear(self) -> None:
        """Drop every counter. Test isolation (D4); a shared backend flushes the
        limiter's key namespace instead — which is safe precisely because
        `RateLimiter.key_for` namespaces every key by limiter name."""
        self._hits.clear()


# Every `RateLimiter` ever constructed, in construction order (D4). The test
# fixture resets whatever is in here, so adding a limiter needs no second edit
# in `conftest.py` — and a limiter that leaked state between tests would
# otherwise make an unrelated test 429 for reasons it never asserts.
_REGISTRY: list[RateLimiter] = []


class RateLimiter:
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        backend: RateLimiterBackend | None = None,
        name: str = "",
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.backend: RateLimiterBackend = backend or InMemoryRateLimiterBackend()
        # The name is a key namespace, not decoration — see `key_for`.
        self.name = name or f"limiter{len(_REGISTRY)}"
        _REGISTRY.append(self)

    def key_for(self, scope: str, value: str) -> str:
        """Namespace a key by this limiter (and by what it keys on).

        Two limiters sharing a backend would otherwise share a counter for the
        same IP or user id: ordinary browse traffic would exhaust the upload cap,
        and one surface's abuse would lock a caller out of an unrelated one.
        `scope` keeps `ip:1.2.3.4` and `user:1234` apart for the same reason.
        """
        return f"{self.name}:{scope}:{value}"

    def check(self, key: str) -> bool:
        """Count this attempt; return True while still under the limit."""
        return self.backend.hit(key, self.window_seconds) <= self.max_attempts

    def reset(self, key: str) -> None:
        self.backend.reset(key)

    def clear(self) -> None:
        self.backend.clear()


def reset_all() -> None:
    """Clear every registered limiter — the test fixture's single entry point."""
    for limiter in _REGISTRY:
        limiter.clear()


def client_ip(request: Request) -> str:
    """The address to key an anonymous limit on.

    `X-Forwarded-For` is a client-supplied header. Trusting it unconditionally
    makes a limiter *weaker than none*: the caller picks a fresh key per request
    and the counter never reaches its cap. So it is read only as far as
    `settings.trusted_proxy_count` entries from the RIGHT — those were appended
    by infrastructure we run, while everything to their left is attacker input.

    Concretely: skip the rightmost `trusted_proxy_count` entries (our own
    proxies' addresses, written by the hop behind them) and take the next one to
    the left — that is the address the innermost trusted proxy actually observed.
    Anything an attacker prepends stays to the left of that position and is never
    read. Two deliberate properties:

    - **`0` (the default) ignores the header entirely**, which is both correct
      for local dev and safe in front of any deployment: an unproxied app that
      trusted the header would hand every caller a free counter per request.
    - **Every failure falls back to `request.client.host`**, never to header
      content: too few entries to satisfy the hop count means the header was not
      written by the infrastructure we assumed, so it is not evidence. Setting
      the count too high therefore degrades to "everyone behind the proxy shares
      one bucket" (a tight limit), never to "the caller picks their own key".

    Read from `settings` at **call** time, not import time, so the value is
    configurable per deployment (and monkeypatchable in the S3/S4 tests).
    """
    direct = request.client.host if request.client else "unknown"

    trusted = getattr(settings, "trusted_proxy_count", 0) or 0
    if trusted <= 0:
        return direct

    forwarded = request.headers.get("x-forwarded-for", "")
    entries = [part.strip() for part in forwarded.split(",") if part.strip()]
    index = len(entries) - 1 - trusted
    if index < 0:
        return direct
    return entries[index]


def enforce(limiter: RateLimiter, key: str, *, retry_after: int | None = None) -> None:
    """Count this hit and refuse it if the cap is spent (D1, D7).

    One function, so a route cannot half-implement the check — the dangerous
    half being "counted but never refused". `Retry-After` rides on the error
    (D7): a caller told to back off but not for how long polls, which is the
    behavior the limiter exists to prevent.

    The message is deliberately uniform and content-free: these caps sit on
    public routes, and a 429 must not become an information channel about how
    the key was derived (R7).
    """
    if not limiter.check(key):
        raise RateLimited(
            "Too many requests — please try again later",
            retry_after=retry_after or limiter.window_seconds,
        )


def enforce_per_ip(
    limiter: RateLimiter, request: Request, *, retry_after: int | None = None
) -> None:
    """Anonymous routes: the only thing there is to key on (D2)."""
    enforce(limiter, limiter.key_for("ip", client_ip(request)), retry_after=retry_after)


def enforce_per_user(
    limiter: RateLimiter, user, *, retry_after: int | None = None
) -> None:
    """Authenticated routes: key on the JWT-derived identity, never the address
    (D2). Keying an authenticated route on IP is wrong in both directions — one
    account evades its cap by moving address, while a NAT'd office punishes
    every user behind it for one abuser. Deliberately **not** `user.id` plus the
    address: that also isolates users, but lets one user reset their own cap by
    presenting a new address (S2).
    """
    enforce(limiter, limiter.key_for("user", str(user.id)), retry_after=retry_after)


def reset_per_ip(limiter: RateLimiter, request: Request) -> None:
    """Forget an IP's counter — the success path of a limited auth route, which
    must build the same namespaced key `enforce_per_ip` counted against."""
    limiter.reset(limiter.key_for("ip", client_ip(request)))
