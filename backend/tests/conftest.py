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

import anyio.from_thread
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app

TEST_JWT_SECRET = os.environ["JWT_SECRET"]
TEST_JWT_ALG = os.environ["JWT_ALGORITHM"]


def bearer_token(headers: dict) -> str:
    """The raw JWT out of an `Authorization` header dict.

    WebSocket handshakes carry the token as a query parameter (spec 006 D6 —
    browsers cannot attach a custom header to a WS handshake), so chat tests
    need the bare string `auth_headers` never hands back on its own.
    """
    return headers["Authorization"].removeprefix("Bearer ")
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

    Every request is pinned to one shared ``anyio`` portal (M6, spec 006) —
    without this, Starlette's ``TestClient`` gives each ``websocket_connect()``
    call its *own* independent portal/event loop (``_portal_factory`` only
    reuses ``self.portal`` when it's already set; plain instantiation leaves it
    ``None``). A single connection works fine either way, but two connections
    open at once in one test (any dual-socket chat test) each end up on a
    different event loop — and this app's WebSocket handler broadcasts to
    every registered socket for a conversation via ``chat_broker.publish()``,
    which means a message sent on one connection is delivered by ``await``ing
    the *other* connection's `send()` from a coroutine running on the *first*
    connection's loop. That's a cross-event-loop call Python's asyncio primitives
    were never built for, and it hangs forever rather than erroring — real
    production never hits this, because one process serves every connection on
    one loop, exactly what pinning `client.portal` here reproduces for tests.
    Setting the attribute directly (never ``with TestClient(app) as c:``) is
    what avoids re-triggering the lifespan this fixture already opts out of.
    """
    app.dependency_overrides[get_session] = lambda: session
    # raise_server_exceptions=False so the 500 handler's *response* reaches the
    # test (G1/G3) instead of the exception re-raising through TestClient.
    c = TestClient(app, raise_server_exceptions=False)
    with anyio.from_thread.start_blocking_portal(**c.async_backend) as portal:
        c.portal = portal
        yield c
        c.portal = None
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
    try:
        from app.routers import chat as chat_router

        chat_router._chat_rate_limiter.backend = InMemoryRateLimiterBackend()
    except ImportError:
        pass  # M6 slice 1 hasn't landed yet — nothing to reset
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
    can't reach alone — e.g. `live`, which needs admin approval at M3).

    **Does not set `published_at`** — it forces one column. M5's gate keys its
    404-vs-403 existence rule on `published_at` (spec 005 D1), so a listing that
    must be *genuinely* published belongs to `live_listing` below, which walks
    the real admin path. Forcing `status="live"` here leaves `published_at` null,
    which is a state the product never produces.
    """
    from sqlalchemy import text

    def _force(listing_id, status):
        session.execute(
            text("UPDATE listing SET status = :s WHERE id = :i"),
            {"s": status, "i": listing_id},
        )
        session.commit()
    return _force


# ── M5 NDA + access-gate helpers ─────────────────────────────────────────────
#
# M5 needs almost no DB seeding: every state in the access-request machine
# (requested / approved / denied / revoked) is reachable through real endpoints,
# so these fixtures compose the product's own routes. That is the testing_guide
# ideal — a fixture that forges a state can hide a transition the product can't
# actually perform.


@pytest.fixture
def sign_nda(client):
    """Sign the platform NDA as the given user (spec 005 A1)."""
    def _sign(headers):
        return client.post("/api/auth/nda", headers=headers)
    return _sign


@pytest.fixture
def live_listing(client, make_listing, admin_headers):
    """A genuinely published listing: create → submit → admin approve.

    Walks the real M2 + M3 path rather than forcing columns, so `published_at`
    is set the way the product sets it. M5's gate distinguishes "never
    published" (404 — still a secret) from "published" (403 — ask for access),
    and a forced status would leave that untestable (spec 005 D1).
    """
    def _live(owner_headers, **overrides):
        listing_id = make_listing(owner_headers, **overrides).json()["id"]
        client.post(f"/api/listings/{listing_id}/submit", headers=owner_headers)
        client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())
        return listing_id
    return _live


@pytest.fixture
def request_access(client, sign_nda):
    """Sign the NDA (if needed) and request access to a listing (spec 005 B1)."""
    def _request(listing_id, buyer_headers, sign=True):
        if sign:
            sign_nda(buyer_headers)
        return client.post(
            f"/api/listings/{listing_id}/access-request", headers=buyer_headers
        )
    return _request


@pytest.fixture
def granted_access(client, request_access):
    """Drive a request all the way to `approved` through the real endpoints.

    Returns the access-request id, so a test can carry on to deny/revoke.
    """
    def _grant(listing_id, buyer_headers, seller_headers):
        req_id = request_access(listing_id, buyer_headers).json()["id"]
        client.post(f"/api/access-requests/{req_id}/approve", headers=seller_headers)
        return req_id
    return _grant


@pytest.fixture
def access_events(session):
    """Read the append-only audit rows for an access request, oldest first.

    Mirrors `listing_events` (M3). Spec 005 C10 is the reason this table exists:
    a revocation must not overwrite *when* access was granted, so the test reads
    the history rather than the row's current `decided_at`.
    """
    from sqlalchemy import text

    def _events(access_request_id):
        rows = session.execute(
            text(
                "SELECT actor_id, action, from_status, to_status, created_at "
                "FROM accessrequestevent WHERE access_request_id = :i ORDER BY id"
            ),
            {"i": access_request_id},
        ).fetchall()
        return [
            {
                "actor_id": r[0],
                "action": r[1],
                "from_status": r[2],
                "to_status": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]

    return _events


# ── M6 chat helpers ──────────────────────────────────────────────────────────


@pytest.fixture
def chat_conversation(client, session, granted_access):
    """Walk M5's real approval path, then read back the `Conversation` row M6's
    approve endpoint creates (spec 006 A1). Returns the conversation id.

    Reads the row directly rather than through an endpoint — there is no
    product route that answers "what is the conversation id for this listing
    and this buyer" (by design: entry to chat is the conversation list,
    spec 006 D5), so a fixture reaching past the API here is exactly the
    testing_guide exception for setup, not a hidden transition.
    """

    def _make(listing_id, buyer_headers, seller_headers):
        granted_access(listing_id, buyer_headers, seller_headers)
        from app.models import Conversation

        buyer_id = client.get("/api/auth/me", headers=buyer_headers).json()["id"]
        conversation = session.exec(
            select(Conversation).where(
                Conversation.listing_id == listing_id,
                Conversation.buyer_id == buyer_id,
            )
        ).first()
        return conversation.id if conversation is not None else None

    return _make
