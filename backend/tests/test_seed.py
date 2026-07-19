"""M4 — the seed script (spec 004: E1-E3).

Seeded supply is not optional polish: an empty marketplace tells a visitor the
product is dead (`milestones.md` § Scope fold-ins → M4, research synthesis risk
#1). The script is importable as `seed(session)` so it can be tested against the
per-test in-memory database rather than the developer's real `nextowner.db`.
"""

import sys
from pathlib import Path

import pytest

# The seed package lives at the repo root, beside `backend/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def seed_fn():
    from seed.seed import seed
    return seed


def test_e1_seed_creates_a_browsable_marketplace(seed_fn, session):
    from sqlmodel import select

    from app.models import Listing, ListingPrivate

    seed_fn(session)

    listings = list(session.exec(select(Listing)).all())
    live = [x for x in listings if x.status == "live"]

    assert len(listings) >= 30, "the marketplace must look populated"
    assert len(live) >= 25, "most seeded listings should be publicly browsable"
    assert all(x.published_at is not None for x in live), "a live listing carries published_at"
    assert len({x.type for x in listings}) > 1, "more than one business type"

    for listing in listings:
        assert session.get(ListingPrivate, listing.id) is not None, (
            "every listing needs its private row — the split is the schema, not an option"
        )


def test_e2_seeding_twice_does_not_duplicate(seed_fn, session):
    from sqlmodel import select

    from app.models import Listing

    seed_fn(session)
    first = len(list(session.exec(select(Listing)).all()))
    seed_fn(session)
    assert len(list(session.exec(select(Listing)).all())) == first


def test_e4_the_cli_refuses_a_database_that_is_not_local_sqlite(monkeypatch):
    """The seed sellers' password is a constant in this repo (spec 004 E4).

    Fine for a throwaway local file, unacceptable anywhere else — so the CLI
    must refuse rather than trust the operator to notice.

    Asserts the *property* (nothing was written), not just that it exited: the
    re-verification round pointed out that `pytest.raises(SystemExit)` alone
    would still pass if a future edit performed a write before reaching the
    guard, while E4's wording promises "exits without writing anything".
    """
    import seed.seed as seed_module

    from app.config import settings

    writes: list[object] = []
    monkeypatch.setattr(seed_module, "seed", lambda *a, **kw: writes.append(a))

    original = settings.database_url
    settings.database_url = "postgresql://user:pw@db.internal/nextowner"
    try:
        with pytest.raises(SystemExit):
            seed_module.main()
    finally:
        settings.database_url = original

    assert writes == [], "the seed write ran despite a non-SQLite database"


def test_e5_the_write_function_itself_refuses_a_non_sqlite_session(seed_fn, session, monkeypatch):
    """The guard travels with the capability, not just the CLI (spec 004 E5).

    Guarding only `main()` left `seed(session)` open to any other caller — a
    startup hook, a migration step, or the two-line pattern in this file's own
    fixture. Found by the branch review's bounded re-verification round.
    """
    from unittest.mock import Mock

    monkeypatch.setattr(
        session, "get_bind", lambda: Mock(url=Mock(drivername="postgresql"))
    )
    with pytest.raises(SystemExit):
        seed_fn(session)


def test_e3_seeded_listings_leak_nothing_through_the_public_api(seed_fn, session, client):
    seed_fn(session)
    blob = client.get("/api/listings?limit=50").text
    for leak in ("company_name", "website_url", "detailed_financials", "owner_id"):
        assert leak not in blob
