"""Shared pytest fixtures — write once, every test stays short.

Each test gets a fresh, empty in-memory SQLite database via
``app.dependency_overrides`` (``docs/testing_guide.md`` §3.4). Tests go through
the real endpoints; only seeding reaches into the session directly.

The auth-dependent fixtures ``as_user`` and ``seed`` land with their milestones
(``as_user`` in M1 once ``/api/auth/*`` exists; ``seed`` factories as their
models/endpoints ship) — added here would just call endpoints that 404.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app


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

    Plain ``TestClient(app)`` (no ``with``) deliberately skips the app's
    startup lifespan so tests never touch the real ``nextowner.db`` file — the
    ``session`` fixture already created the schema on the in-memory engine.
    """
    app.dependency_overrides[get_session] = lambda: session
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
