"""Shared pytest fixtures — write once, every test stays short.

Each test gets a fresh, empty in-memory SQLite database via
``app.dependency_overrides`` (``docs/testing_guide.md`` §3.4). Tests go through
the real endpoints; only seeding (making a user admin, forging tokens) reaches
past them.

The JWT secret is pinned **before** the app imports its settings, so the app and
the token-forging tests (C2–C4) agree on signing key + algorithm.
"""

import os
import re
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

    **Migrated per spec pre-011 D4**: once `ratelimit.reset_all()` exists (the
    registry every `RateLimiter` self-registers into), this fixture uses it and
    stops naming limiters one by one — the whole point of the registry is that
    a newly-added limiter is reset automatically, with no second edit here.
    Until that seam lands, this falls back to the by-name reset that predates
    it, so `test_rate_limits.py` can be written now without breaking every
    other test in the suite before `reset_all()` exists.
    """
    from app import ratelimit

    if hasattr(ratelimit, "reset_all"):
        ratelimit.reset_all()
        yield
        return

    from app.ratelimit import InMemoryRateLimiterBackend
    from app.routers import auth as auth_router

    auth_router._login_limiter.backend = InMemoryRateLimiterBackend()
    auth_router._register_limiter.backend = InMemoryRateLimiterBackend()
    for limiter in ("_forgot_password_limiter",):     # M8 — mails a third party on demand
        if hasattr(auth_router, limiter):
            getattr(auth_router, limiter).backend = InMemoryRateLimiterBackend()
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


# ── M7 offer helpers ─────────────────────────────────────────────────────────
#
# Offers need almost no DB seeding either, same rationale as M5's access-gate
# fixtures above: every state this milestone's negotiation reaches (submitted,
# accepted, declined, withdrawn, countered) is produced by the product's own
# endpoints, so composing them here — never forging a row `Offer(status=...)`
# directly — means a fixture can never grant a test a state the app itself
# cannot reach.

# A complete, valid offer/counter body (spec 007 D6). `price` as a string —
# the server parses Decimal, mirroring `VALID_LISTING`'s money fields.
VALID_OFFER = {
    "price": "450000.00",
    "structure": "all cash",
    "contingencies": "subject to financing and standard due diligence",
    "proposed_close_date": "2026-10-01",
}


@pytest.fixture
def make_offer(client):
    """POST an offer on a listing with the given (already-approved) buyer's
    headers; returns the response. Mirrors `make_listing`."""
    def _make(listing_id, headers, **overrides):
        return client.post(
            f"/api/listings/{listing_id}/offers",
            json={**VALID_OFFER, **overrides},
            headers=headers,
        )
    return _make


@pytest.fixture
def submitted_offer(client, granted_access, make_offer):
    """Drive a `live` listing + a buyer all the way to a `submitted` offer
    through the real endpoints (spec 007 A1) — compose `granted_access` (NDA
    sign + request + approve) then `POST .../offers`. Mirrors `granted_access`'s
    own shape: takes an already-`live` listing id, buyer headers, seller
    headers; returns the new offer's id, so a test can carry on to
    accept/decline/counter/withdraw it.
    """
    def _submit(listing_id, buyer_headers, seller_headers, **overrides):
        granted_access(listing_id, buyer_headers, seller_headers)
        res = make_offer(listing_id, buyer_headers, **overrides)
        return res.json()["id"]
    return _submit


@pytest.fixture
def offer_events(session):
    """Read the append-only audit rows for an offer, oldest first.

    Mirrors `listing_events`/`access_events` exactly. Unlike `AccessRequestEvent`,
    `OfferEvent` also logs *creation* (`action="submitted"`, `from_status=null`) —
    plan.md § Schema deltas explains why: this table doubles as the negotiation's
    own narrative (FR-17's "both parties see offer history"), not merely a record
    of values a later transition would otherwise overwrite.
    """
    from sqlalchemy import text

    def _events(offer_id):
        rows = session.execute(
            text(
                "SELECT actor_id, action, from_status, to_status, created_at "
                "FROM offerevent WHERE offer_id = :i ORDER BY id"
            ),
            {"i": offer_id},
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


# ── M8 notification / email / token helpers ──────────────────────────────────
#
# The email port (spec 008 D9) is swapped for a recorder in every test, so the
# suite never opens an SMTP socket (F6). Same shape as `_fresh_rate_limiters`
# above: module-level state reset per test, guarded by `hasattr` so the suite
# still collects on the slices where `app.mailer` does not exist yet.


class RecordingEmailSender:
    """Test double for `EmailSender` — records instead of sending.

    `should_raise` lets F4/X3 prove that a failing transport never fails the
    business action: the domain call must still return its normal 2xx and the
    in-app notification must still exist.
    """

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.should_raise = False

    def send(self, to: str, subject: str, body: str) -> None:
        if self.should_raise:
            raise RuntimeError("smtp unavailable")
        self.sent.append({"to": to, "subject": subject, "body": body})

    def to(self, address: str) -> list[dict]:
        return [m for m in self.sent if m["to"] == address]


@pytest.fixture(autouse=True)
def outbox():
    """Swap the module-level mailer for a recorder; yield it for assertions.

    **Both seams are swapped, and the dispatcher one is load-bearing.**
    Production runs sends on a worker pool (`ThreadDispatcher`) so a blocking
    SMTP call never sits on the request thread — or, worse, on the `async`
    WebSocket handler's event loop. Under that dispatcher a test asserting
    `outbox.sent` immediately after a request would race the worker and flake.
    `InlineDispatcher` makes the send happen before the request returns, which
    is what every F/G/H assertion depends on.
    """
    recorder = RecordingEmailSender()
    try:
        from app import mailer as mailer_module
    except ImportError:
        yield recorder                      # slice 1 hasn't landed — nothing to swap
        return
    original_mailer = mailer_module.mailer
    original_dispatcher = mailer_module.dispatcher
    mailer_module.mailer = recorder
    mailer_module.dispatcher = mailer_module.InlineDispatcher()
    yield recorder
    mailer_module.mailer = original_mailer
    mailer_module.dispatcher = original_dispatcher


@pytest.fixture
def inbox(client):
    """The caller's own notifications, through the real endpoint."""
    def _inbox(headers, **params):
        return client.get("/api/notifications", headers=headers, params=params)
    return _inbox


@pytest.fixture
def notification_rows(session):
    """Raw notification rows for a recipient, oldest first.

    Reads the table directly because C14/C15 assert on what was **stored** —
    a response model that omits a field would hide a row that still carries it,
    which is exactly the leak those criteria exist to catch.
    """
    from sqlalchemy import text

    def _rows(recipient_id):
        rows = session.execute(
            text(
                "SELECT id, type, title, listing_id, conversation_id, offer_id, "
                "read_at, created_at FROM notification WHERE recipient_id = :r ORDER BY id"
            ),
            {"r": recipient_id},
        ).mappings().all()
        return [dict(r) for r in rows]

    return _rows


@pytest.fixture
def user_id(client):
    """The id behind a set of auth headers (via the real /me route)."""
    def _id(headers):
        return client.get("/api/auth/me", headers=headers).json()["id"]
    return _id


@pytest.fixture
def token_rows(session):
    """Raw rows from either token table — G7 asserts the raw token is absent."""
    from sqlalchemy import text

    def _rows(table):
        rows = session.execute(
            text(
                f"SELECT id, user_id, token_hash, expires_at, used_at "  # noqa: S608 - fixed literals
                f"FROM {table} ORDER BY id"
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    return _rows


@pytest.fixture
def expire_token(session):
    """Backdate a token's expiry — the only way to reach "expired" without
    sleeping. Seeding a clock, not forging a transition (testing_guide §3.4)."""
    from sqlalchemy import text

    def _expire(table, token_id):
        session.execute(
            text(f"UPDATE {table} SET expires_at = :e WHERE id = :i"),  # noqa: S608
            {"e": "2000-01-01 00:00:00", "i": token_id},
        )
        session.commit()
    return _expire


def _token_from(message: dict, path: str) -> str:
    """Pull a one-time token out of a dispatched email's link.

    Anchored on the **path** as well as the parameter, so a test cannot
    accidentally redeem a reset token where it meant a verification one — the
    cross-purpose confusion spec D4 exists to make impossible (H5/H6).
    """
    match = re.search(rf"{re.escape(path)}\?token=([A-Za-z0-9_\-]+)", message["body"])
    assert match, f"no {path} link in the email body: {message['body']!r}"
    return match.group(1)


def reset_token_from(message: dict) -> str:
    return _token_from(message, "/reset-password")


def verification_token_from(message: dict) -> str:
    return _token_from(message, "/verify-email")


@pytest.fixture
def verify_email(client, outbox):
    """Walk a user through real email verification; returns their headers.

    Composes the product's own routes (register already mailed the token) rather
    than stamping `email_verified_at` directly — a fixture that forges the state
    would hide a verification flow the app cannot actually perform.
    """
    def _verify(headers):
        address = client.get("/api/auth/me", headers=headers).json()["email"]
        token = verification_token_from(outbox.to(address)[-1])
        client.post("/api/auth/verify-email", json={"token": token})
        return headers
    return _verify


# ── M10 buyer-verification helpers ───────────────────────────────────────────
#
# Note the naming: `verify_email` above is M8's *email* verification (a token
# redemption); everything below is M10's *buyer* verification (a proof-of-funds
# document reviewed by an admin). Two unrelated state machines that both got
# called "verification" in prose — the fixtures keep them apart by name so a
# test cannot reach for the wrong one.
#
# Same discipline as the M5/M7 fixtures: compose the product's own routes, never
# forge a `verification_status` column directly. Every state this milestone
# reaches (unverified → pending → verified | rejected, and back to pending on
# resubmission) is produced by a real endpoint, so a fixture cannot hand a test
# a state the app itself cannot reach.

# A minimal well-formed PDF — the magic-byte check M2 already enforces
# (`test_listing_upload.py::test_d7`) applies verbatim to this route (spec 010 D5),
# so an upload's bytes must actually match its declared content type.
VALID_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def submit_verification(client):
    """Upload a proof-of-funds document as the given caller (spec 010 V1).

    Mirrors `test_listing_upload.py`'s `_upload` helper — same multipart shape,
    a different route — because M10 deliberately reuses M2's upload pipeline
    rather than building a second one (spec 010 D5).
    """
    def _submit(
        headers,
        filename="proof-of-funds.pdf",
        content=VALID_PDF,
        content_type="application/pdf",
    ):
        return client.post(
            "/api/verification/documents",
            files={"file": (filename, content, content_type)},
            headers=headers,
        )
    return _submit


@pytest.fixture
def pending_verification(client, submit_verification, user_id):
    """A buyer with a `pending` submission; returns `(user_id, document_id)`.

    The document id is returned because three criteria (S4, S5, S9) address the
    gated download route and would otherwise have to re-derive it from
    `GET /api/verification`.
    """
    def _pending(buyer_headers):
        res = submit_verification(buyer_headers)
        assert res.status_code == 201, res.text
        return user_id(buyer_headers), res.json()["id"]
    return _pending


@pytest.fixture
def verified_buyer(client, pending_verification, admin_headers):
    """Drive a buyer all the way to `verified` through the real admin route.

    Returns `(user_id, document_id)` like `pending_verification`, so a test can
    carry on to the `verified → rejected` revoke path (V14) or to D3's
    already-verified 409 (V7).
    """
    def _verified(buyer_headers, admin=None):
        buyer_id, document_id = pending_verification(buyer_headers)
        approved = client.post(
            f"/api/admin/verifications/{buyer_id}/approve",
            headers=admin or admin_headers(),
        )
        assert approved.status_code == 200, approved.text
        return buyer_id, document_id
    return _verified


@pytest.fixture
def verification_events(session):
    """Read the append-only audit rows for a buyer, oldest first.

    Mirrors `listing_events`/`access_events`/`offer_events`. Spec 010 D6 is the
    reason this table exists: `User.verification_reason` holds only the *current*
    decision, so a rejection reason is overwritten the moment a resubmission is
    approved — the history has to be read from here, not from the row.
    """
    from sqlalchemy import text

    def _events(user_id_value):
        rows = session.execute(
            text(
                "SELECT actor_id, action, from_status, to_status, reason, created_at "
                "FROM buyerverificationevent WHERE user_id = :i ORDER BY id"
            ),
            {"i": user_id_value},
        ).mappings().all()
        return [dict(r) for r in rows]

    return _events
