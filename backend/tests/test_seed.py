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


def test_e3_seeded_listings_leak_nothing_through_the_public_api(seed_fn, session, client):
    seed_fn(session)
    blob = client.get("/api/listings?limit=50").text
    for leak in ("company_name", "website_url", "detailed_financials", "owner_id"):
        assert leak not in blob
