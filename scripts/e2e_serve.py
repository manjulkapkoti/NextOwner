"""Start the API for the golden-path E2E run, against a database deleted first.

Spec 013 D7 (H1): the run is hermetic. It writes to a dedicated ``e2e.db`` and
must never touch the developer's ``nextowner.db``.

**Why this is a script and not two commands in the Playwright config.** The
delete has to happen *before* uvicorn opens the file, and Playwright's
``webServer`` and ``globalSetup`` do not give that ordering as a guarantee you
can read off the config — ``webServer`` entries start in parallel with each
other, and deleting a SQLite file a running server already holds open is the
worst of both worlds: on Windows it fails outright, and on Linux it silently
succeeds while the server keeps writing to an unlinked inode nobody can read.
Doing both steps in one process makes the order a fact of the code rather than
an assumption about the runner.

Usage (from ``backend/``):  python ../scripts/e2e_serve.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The one database this script is allowed to delete is named by DATABASE_URL,
# and it must be an obviously-throwaway SQLite file. Both halves matter: the
# first keeps the config the single source of truth for where the run writes,
# the second is what stops a mis-set environment variable from deleting real
# data (`seed/seed.py` carries the same non-SQLite refusal, for the same
# reason).
DEFAULT_PORT = 8001


def _sqlite_path(database_url: str) -> Path:
    """The file a SQLite URL points at, or exit with the reason it is refused."""
    if not database_url.startswith("sqlite:///"):
        raise SystemExit(
            f"Refusing to run: DATABASE_URL is {database_url!r}, not a local SQLite file.\n"
            "This script DELETES the database it is pointed at before starting."
        )

    raw = database_url[len("sqlite:///") :]
    if not raw or raw == ":memory:":
        raise SystemExit("Refusing to run: DATABASE_URL names no file on disk.")

    path = Path(raw)
    # Guard on the *name*, not on the resolved location: a run pointed at the
    # developer's database would still pass every G criterion while destroying
    # local data, which is exactly the failure H1 exists to make impossible.
    if path.name == "nextowner.db":
        raise SystemExit(
            "Refusing to run: DATABASE_URL points at nextowner.db, the developer's "
            "own database. The golden path deletes what it is given (spec 013 D7)."
        )
    if "e2e" not in path.name:
        raise SystemExit(
            f"Refusing to run: {path.name!r} is not an e2e database. Name it so the "
            "next person reading a `rm` in a script can tell it is throwaway."
        )
    return path


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("Refusing to run: DATABASE_URL is not set.")

    db_path = _sqlite_path(database_url)

    # Delete the database *and* its sidecars. A stale -wal alongside a deleted
    # main file is not an empty database; it is a partially-restored one, which
    # would make "unique headline" (D10) quietly stop holding on the second run.
    for path in (db_path, Path(f"{db_path}-journal"), Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        path.unlink(missing_ok=True)

    print(f"[e2e] hermetic database: {db_path.resolve()} (deleted, will be recreated)", flush=True)

    # Imported after the delete so nothing can open the file first, and inside
    # main() so the refusals above cost nothing to reach.
    import uvicorn

    port = int(os.environ.get("E2E_API_PORT", DEFAULT_PORT))
    # In-process, not a child: Playwright terminates this pid at the end of the
    # run, and a uvicorn spawned as a subprocess could outlive it holding the
    # port. `app.main:app` creates the tables on startup (lifespan → init_db).
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    sys.exit(main())
