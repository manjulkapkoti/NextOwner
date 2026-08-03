"""Promote an existing user to admin (spec 013 D5/D6).

**There is deliberately no HTTP path that grants admin.** That has been true
since M1 and unchanged at M3, and `backend/tests/conftest.py` promotes with a
direct ``UPDATE`` for the same reason. The E2E has the same need, and solving it
with an env-flag-gated bootstrap route would be exactly the "test-only backdoor
in prod" `security.md` §6 names as a threat: a flag misread in one environment
grants admin over HTTP forever. This is a CLI. It needs filesystem and database
access, and it adds zero route surface.

Three refusals, each with its own reason:

- **It cannot create a principal** (H2). It only ever flips ``is_admin`` on a row
  that already exists, so the operator must first register through the real
  endpoint — which is rate-limited, validated and logged. This is the guard that
  matters most, and it is stronger than any check on the database's name.
- **It cannot touch a non-SQLite database** (H3), checked before anything opens a
  connection. A Postgres URL means something closer to production, and that path
  deserves a deliberate decision rather than this script. `seed/seed.py` carries
  the same guard.
- **It cannot run by accident** (H4). ``NEXTOWNER_ALLOW_ADMIN_PROMOTION=1`` must
  be set explicitly.

What is *not* claimed: this is not a defence against someone who already holds
shell access and the database file — nothing at this layer can be. It defends
against the two realistic failures, which are a script run in the wrong
directory and a CI job pointed at the wrong environment.

Usage:  NEXTOWNER_ALLOW_ADMIN_PROMOTION=1 python -m seed.make_admin someone@example.com
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Import the app as `app`, exactly as the backend, its tests and seed.py do.
# Importing it as `backend.app` would load a *second* copy of the module, and
# the `User` class here would then be a different object from the one the
# running app registered with SQLModel's metadata.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

OPT_IN_ENV = "NEXTOWNER_ALLOW_ADMIN_PROMOTION"


def _fail(message: str) -> None:
    """Exit non-zero with a plain-English reason on stderr.

    Not the HTTP error contract: this is a CLI, and its audience is an operator
    reading a terminal or a CI log, not a browser.
    """
    raise SystemExit(f"Refusing to promote: {message}")


def promote(email: str) -> None:
    # 1. The explicit opt-in, checked first because it is the "may this run at
    #    all" question and costs nothing to answer.
    if os.environ.get(OPT_IN_ENV) != "1":
        _fail(
            f"{OPT_IN_ENV} is not set to 1.\n"
            "Granting admin is the highest privilege in the product, so it takes a "
            f"deliberate act:\n\n    {OPT_IN_ENV}=1 python -m seed.make_admin {email}\n"
        )

    # 2. The database, checked BEFORE importing anything that opens a connection
    #    — `app.db` builds its engine at import time, so this order is load-
    #    bearing rather than stylistic.
    from app.config import settings  # noqa: PLC0415 — deliberately after the guard
    from sqlalchemy.engine.url import make_url  # noqa: PLC0415 — parses only, opens nothing

    database_url = settings.database_url
    # Parsed with SQLAlchemy's own parser, not by string slicing. The first
    # version tested `startswith("sqlite")` here and `startswith("sqlite:///")`
    # below, so `sqlite+pysqlite:///new.db` passed the first and skipped the
    # second entirely — creating a zero-byte file and dying in a raw
    # OperationalError traceback instead of this script's plain refusal. One
    # parser, used by both checks, is what closes that (appsec pass, 2026-08-03).
    try:
        url = make_url(database_url)
    except Exception:  # noqa: BLE001 — any parse failure is a refusal
        _fail(f"DATABASE_URL is not a URL SQLAlchemy can parse: {database_url!r}")

    if url.get_backend_name() != "sqlite":
        _fail(
            f"DATABASE_URL is not a local SQLite database ({url.get_backend_name()}://…).\n"
            "A non-SQLite URL means something closer to production, and granting admin "
            "there deserves a deliberate decision rather than this script."
        )

    # 3. The row must already exist. A database file that was never created
    #    cannot hold one, and saying so plainly beats a "no such table" traceback.
    #    It also keeps H2's promise literally true: this script creates nothing,
    #    not even an empty file.
    db_path = Path(url.database) if url.database and url.database != ":memory:" else None
    if db_path is not None and not db_path.exists():
        _fail(
            f"there is no database at {db_path.resolve()}.\n"
            f"{email} must register through the API first — this script only promotes an "
            "account that already exists, and never creates one."
        )

    from app.db import engine  # noqa: PLC0415 — deliberately after the guards
    from app.models import User  # noqa: PLC0415
    from sqlmodel import Session, select  # noqa: PLC0415

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            _fail(
                f"no user with the email {email}.\n"
                "They must register through the API first — this script only promotes an "
                "account that already exists, and never creates one."
            )

        if user.is_admin:
            print(f"{email} is already an admin — nothing to do.")
            return

        user.is_admin = True
        session.add(user)
        session.commit()

    # Printed, not silent: a CI log should record what was granted and to whom.
    print(f"Promoted {email} to admin.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m seed.make_admin <email>")
    promote(sys.argv[1])


if __name__ == "__main__":
    main()
