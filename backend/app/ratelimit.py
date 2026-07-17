"""Login rate limiting — behind a swappable backend (horizontal-scale blocker #1).

The in-process backend is the correct MVP implementation. It is **per-instance
state**, so behind a load balancer N instances would allow N× the limit — which
is why the store sits behind `RateLimiterBackend`: swapping to a shared
(Redis-class) backend is constructing `RateLimiter(backend=...)` differently, not
a rewrite. See `design_implementation.md` § Horizontal scale, and the F2 test.
"""

from __future__ import annotations

import time
from typing import Protocol


class RateLimiterBackend(Protocol):
    """The seam. A shared-store backend implements the same two methods."""

    def hit(self, key: str, window_seconds: int) -> int: ...
    def reset(self, key: str) -> None: ...


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


class RateLimiter:
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        backend: RateLimiterBackend | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.backend: RateLimiterBackend = backend or InMemoryRateLimiterBackend()

    def check(self, key: str) -> bool:
        """Count this attempt; return True while still under the limit."""
        return self.backend.hit(key, self.window_seconds) <= self.max_attempts

    def reset(self, key: str) -> None:
        self.backend.reset(key)
