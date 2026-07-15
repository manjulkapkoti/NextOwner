"""Database engine + session dependency.

SQLite locally (``nextowner.db``); a connection-string swap moves this to
Postgres later with no code change (constitution Article 1). The API is the
only door to this database (Article 2 #1) — nothing outside a FastAPI
dependency should import ``engine`` directly.
"""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

# ``check_same_thread=False`` lets the TestClient's threadpool share a
# connection; production uses a real connection pool per request.
DATABASE_URL = "sqlite:///nextowner.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create tables from the SQLModel metadata (called on app startup)."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped DB session.

    Tests override this (``app.dependency_overrides``) with an in-memory
    engine, so every test gets a fresh, isolated database.
    """
    with Session(engine) as session:
        yield session
