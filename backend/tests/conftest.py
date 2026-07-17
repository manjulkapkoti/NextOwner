"""Shared pytest fixtures — write once, every test stays short.

Each test gets a fresh, empty in-memory SQLite database via
``app.dependency_overrides`` (``docs/testing_guide.md`` §3.4). Tests go through
the real endpoints; only seeding (making a user admin, forging tokens) reaches
past them.

The JWT secret is pinned **before** the app imports its settings, so the app and
the token-forging tests (C2–C4) agree on signing key + algorithm.
"""

import os

# Must precede `import app.main` — pydantic-settings reads the environment at
# import time. A fixed test secret lets C3/C4 forge tokens the app will verify.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

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
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ── M1 auth helpers ──────────────────────────────────────────────────────────

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
