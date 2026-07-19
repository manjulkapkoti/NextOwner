"""Shared pytest fixtures — write once, every test stays short.

Each test gets a fresh, empty in-memory SQLite database via
``app.dependency_overrides`` (``docs/testing_guide.md`` §3.4). Tests go through
the real endpoints; only seeding (making a user admin, forging tokens) reaches
past them.

The JWT secret is pinned **before** the app imports its settings, so the app and
the token-forging tests (C2–C4) agree on signing key + algorithm.
"""

import os
import tempfile

# Must precede `import app.main` — pydantic-settings reads the environment at
# import time. A fixed test secret lets C3/C4 forge tokens the app will verify.
# ≥32 bytes — below that PyJWT warns (InsecureKeyLength) for HS256. Real
# deployments set a strong secret from a secrets manager (security.md §9).
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
# Enables the gated /_debug/boom route so the 500-contract tests (G1/G3) have a
# route that raises. Off by default in the app → never mounted in production.
os.environ.setdefault("ENABLE_DEBUG_ROUTES", "1")

# Point uploads at a throwaway temp dir so tests never write into the repo's
# uploads/ (must precede `import app.main` — the storage backend reads it at import).
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="nextowner-test-uploads-"))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app

TEST_JWT_SECRET = os.environ["JWT_SECRET"]
TEST_JWT_ALG = os.environ["JWT_ALGORITHM"]
VALID_PW = "correct horse battery staple"


@pytest.fixture
def session():
    """A fresh, empty in-memory database for every single test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    """TestClient whose ``get_session`` dependency is the per-test DB.

    Plain ``TestClient(app)`` (no ``with``) deliberately skips the app's startup
    lifespan so tests never touch the real ``nextowner.db`` file.
    """
    app.dependency_overrides[get_session] = lambda: session
    # raise_server_exceptions=False so the 500 handler's *response* reaches the
    # test (G1/G3) instead of the exception re-raising through TestClient.
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ── M1 auth helpers ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _fresh_rate_limiters():
    """Give every test clean rate-limiters, like the fresh per-test DB.

    The limiters are module-level in-process state (one counter per app process
    — by design; the swappable backend is the horizontal-scale seam). Across a
    pytest run that state would leak between tests — the brute-force tests (F1,
    F3) would trip them and later requests would 429 — so we reset per test.
    """
    from app.ratelimit import InMemoryRateLimiterBackend
    from app.routers import auth as auth_router

    auth_router._login_limiter.backend = InMemoryRateLimiterBackend()
    auth_router._register_limiter.backend = InMemoryRateLimiterBackend()
    yield


@pytest.fixture
def register(client):
    """Register a user through the real endpoint; returns the response."""
    def _register(email="alice@example.com", password=VALID_PW, role="buyer", **extra):
        return client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "role": role, **extra},
        )
    return _register


@pytest.fixture
def login(client):
    """Log in through the real endpoint (OAuth2 password form); returns the response."""
    def _login(email="alice@example.com", password=VALID_PW):
        return client.post("/api/auth/login", data={"username": email, "password": password})
    return _login


@pytest.fixture
def auth_headers(register, login):
    """Register + log in a user; return ready-to-use Authorization headers."""
    def _auth(email="alice@example.com", password=VALID_PW, role="buyer"):
        register(email=email, password=password, role=role)
        token = login(email=email, password=password).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return _auth


# ── M2 listing helpers ───────────────────────────────────────────────────────

# A complete, valid create body (public + private fields). Money as strings —
# the server parses Decimal. Reuse via `make_listing`, override per test.
VALID_LISTING = {
    "type": "saas",
    "headline": "Profitable B2B scheduling SaaS",
    "description": "A small, profitable scheduling tool for clinics.",
    "asking_price": "500000.00",
    "ttm_revenue": "200000.00",
    "ttm_profit": "120000.00",
    "mrr": "18000.00",
    "churn_pct": "2.50",
    "customers": 340,
    "company_name": "Acme Internal Tools LLC",
    "website_url": "https://acme.example.com",
    "detailed_financials": "{\"note\": \"see attached\"}",
}


@pytest.fixture
def make_listing(client):
    """POST a valid listing with the given auth headers; returns the response."""
    def _make(headers, **overrides):
        return client.post("/api/listings", json={**VALID_LISTING, **overrides}, headers=headers)
    return _make


@pytest.fixture
def admin_headers(register, login, session):
    """Register a user, promote them in the DB, then log in.

    Promotion is a direct UPDATE because there is deliberately no endpoint that
    grants admin (M1 decision, unchanged at M3) — seeding a state no API can
    reach is exactly what `testing_guide.md` allows a fixture to do. The token
    is issued *after* promotion here; `test_require_admin.py` covers the
    inverse (token first, promotion after) to prove `is_admin` is re-read from
    the DB per request rather than trusted from the token.
    """
    from sqlalchemy import text

    def _admin(email="admin@example.com", password=VALID_PW):
        register(email=email, password=password, role="buyer")
        session.execute(text('UPDATE "user" SET is_admin = 1 WHERE email = :e'), {"e": email})
        session.commit()
        token = login(email=email, password=password).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _admin


@pytest.fixture
def listing_events(session):
    """Read the audit rows for a listing, oldest first (M3)."""
    from sqlalchemy import text

    def _events(listing_id):
        rows = session.execute(
            text(
                "SELECT actor_id, action, from_status, to_status, reason, created_at "
                "FROM listingevent WHERE listing_id = :i ORDER BY id"
            ),
            {"i": listing_id},
        ).fetchall()
        return [
            {
                "actor_id": r[0],
                "action": r[1],
                "from_status": r[2],
                "to_status": r[3],
                "reason": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    return _events


@pytest.fixture
def force_status(session):
    """Force a listing's status directly in the DB (seeding a state a seller
    can't reach alone — e.g. `live`, which needs admin approval at M3)."""
    from sqlalchemy import text

    def _force(listing_id, status):
        session.execute(
            text("UPDATE listing SET status = :s WHERE id = :i"),
            {"s": status, "i": listing_id},
        )
        session.commit()
    return _force
