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


# How often the store sweeps elapsed keys (D9). Not a correctness parameter —
# a key's own window decides whether it is live — only how much untidy state is
# tolerated between sweeps. Sweeping on *every* write would be O(keys) per
# request, which under exactly the address-rotating flood this exists to survive
# is quadratic: the cure would be the denial of service.
_SWEEP_INTERVAL_SECONDS = 60


class InMemoryRateLimiterBackend:
    """Fixed-window counter in a dict. Single-instance only, by construction.

    **Evicts keys whose window has fully elapsed** (pre-011 D9/R9). It never used
    to, which was defensible while the only IP-keyed routes were login, register
    and forgot-password: that key space is bounded by addresses that bother to
    attempt authentication. Keying public browse per IP makes the key space
    *every address that ever fetches a listing*, so without eviction an attacker
    rotating source addresses grows this dict without bound — exhausting memory
    through the very control added to stop them. A mitigation that opens a new
    denial-of-service path is not a mitigation.

    Eviction changes no counter's value: a key is dropped only once every one of
    its timestamps is outside its own window, which is exactly the state in which
    `hit` would have filtered them all away anyway.
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        # Each key's window, so the sweep can judge a key by the limiter that
        # owns it rather than by whichever window the current caller passed.
        self._windows: dict[str, int] = {}
        # Set lazily on the first hit, never at construction: the clock a caller
        # (or a test) installs may not be the one this object was built under.
        self._last_sweep: float | None = None

    def hit(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        self._sweep(now)
        recent = [t for t in self._hits.get(key, []) if now - t < window_seconds]
        recent.append(now)
        self._hits[key] = recent
        self._windows[key] = window_seconds
        return len(recent)

    def _sweep(self, now: float) -> None:
        """Drop every key whose window has fully elapsed — opportunistically, on
        write, with no background task (D9)."""
        if self._last_sweep is None or now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
            if self._last_sweep is None:
                self._last_sweep = now
            return

        self._last_sweep = now
        for key, timestamps in list(self._hits.items()):
            if not timestamps or now - timestamps[-1] >= self._windows.get(key, 0):
                del self._hits[key]
                self._windows.pop(key, None)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
        self._windows.pop(key, None)

    def clear(self) -> None:
        """Drop every counter. Test isolation (D4); a shared backend flushes the
        limiter's key namespace instead — which is safe precisely because
        `RateLimiter.key_for` namespaces every key by limiter name."""
        self._hits.clear()
        self._windows.clear()
        self._last_sweep = None


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
    """The address to key an anonymous limit on (D3).

    `X-Forwarded-For` is a client-supplied header. Trusting it unconditionally
    makes a limiter *weaker than none*: the caller picks a fresh key per request
    and the counter never reaches its cap. So the header is evidence only when
    the connection it arrived on came from a proxy we run, and even then only the
    part of it our own infrastructure wrote:

    1. **If the immediate peer is not in `settings.trusted_proxies`, the header is
       ignored entirely** and the connection address is the key. With the default
       (empty) allowlist that is always the case, which is both correct for local
       dev and safe in front of anything.
    2. **Otherwise walk the header right-to-left, skipping entries that are
       themselves trusted proxies, and take the first entry that is not.** That
       entry is the address our innermost proxy actually observed. Anything an
       attacker prepends sits to its *left* and is never read.

    Every failure degrades to `request.client.host`, never to header content: an
    absent header, an empty one, or one whose entries are all trusted means the
    header carries no evidence about who called. The worst a misconfigured
    allowlist can do is merge callers into one bucket — a tighter limit, never a
    free key per request. That is the property the replaced hop-count design did
    not have: it could be set too high, and then the index landed inside
    attacker-supplied text.

    Entries are compared verbatim (whitespace-stripped). A proxy that writes a
    form we did not list — a port suffix, a bracketed IPv6 literal — simply is
    not recognised as trusted, which again fails toward one shared bucket.

    **All `X-Forwarded-For` lines are joined, not just the first.** A client can
    send its own header line, and a proxy that appends a *second* line rather
    than extending the first is entirely conformant (RFC 7230 §3.2.2 — repeated
    field lines are equivalent to one comma-joined value). Reading only
    `headers.get(...)` would then read the attacker's line and never our proxy's,
    handing the caller the key. Joining in receipt order keeps our proxy's entry
    where the right-to-left walk expects it: last.

    Read from `settings` at **call** time, not import time, so the value is
    configurable per deployment (and monkeypatchable in the S3/S4/S6 tests).
    """
    direct = request.client.host if request.client else "unknown"

    trusted = frozenset(getattr(settings, "trusted_proxies", None) or ())
    if direct not in trusted:
        return direct

    forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
    entries = [part.strip() for part in forwarded.split(",") if part.strip()]
    for entry in reversed(entries):
        if entry not in trusted:
            return entry
    return direct


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
