"""Database engine + session dependency.

The connection string comes from `settings` (env), so the SQLite→Postgres move
(Article 1) is a config change, not a code change. The API is the only door to
this database (Article 2 #1) — nothing outside a FastAPI dependency imports
`engine` directly.
"""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# ``check_same_thread=False`` lets the TestClient's threadpool share a connection;
# it's SQLite-specific and harmless for Postgres (which ignores connect_args here).
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)


def init_db() -> None:
    """Create tables from the SQLModel metadata (called on app startup)."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped DB session.

    Tests override this (``app.dependency_overrides``) with an in-memory engine,
    so every test gets a fresh, isolated database.
    """
    with Session(engine) as session:
        yield session
