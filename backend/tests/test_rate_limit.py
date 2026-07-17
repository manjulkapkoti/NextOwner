"""M1 — Login abuse (spec 001 acceptance criteria F1–F2)."""


def test_f1_repeated_failed_logins_get_rate_limited(client, register):
    register()
    got_429 = False
    # Exceed the threshold with wrong-password attempts from one caller.
    for _ in range(20):
        r = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "wrong"})
        if r.status_code == 429:
            got_429 = True
            break
    assert got_429, "expected the login endpoint to rate-limit brute-force attempts"


def test_f3_repeated_registrations_get_rate_limited(client):
    """security.md §1.1 — register is rate-limited too (signup spam), not just login."""
    got_429 = False
    for i in range(20):
        r = client.post(
            "/api/auth/register",
            json={"email": f"user{i}@example.com", "password": "correct horse battery staple", "role": "buyer"},
        )
        if r.status_code == 429:
            got_429 = True
            break
    assert got_429, "expected /auth/register to rate-limit signup spam"


def test_f2_rate_limiter_store_is_behind_a_swappable_interface():
    """Horizontal-scale blocker #1: the store must be a config swap, not a rewrite.

    Structural test — documents the seam. The in-process backend is the MVP
    implementation; a shared (Redis-class) backend must drop in without touching
    the limiter's callers.
    """
    from app import ratelimit

    # A backend interface exists, and the default in-memory backend implements it.
    assert hasattr(ratelimit, "RateLimiterBackend")
    assert hasattr(ratelimit, "InMemoryRateLimiterBackend")
    limiter = ratelimit.RateLimiter(backend=ratelimit.InMemoryRateLimiterBackend())
    assert limiter.backend is not None
