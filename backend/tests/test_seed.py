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


# ── Buyer + access + chat fixtures (owner request, 2026-07-21) ──────────────
#
# Not tied to spec 004's own criteria (E1-E5 above) — this is dev-convenience
# tooling the owner asked for directly, so a fresh local database has an
# approved access request and a conversation with messages to look at without
# walking request -> approve -> open-chat by hand first.


def test_seed_creates_a_buyer_with_the_nda_already_signed(seed_fn, session):
    from sqlmodel import select

    from app.models import User

    seed_fn(session)

    buyer = session.exec(select(User).where(User.email == "buyer.seed@example.com")).first()
    assert buyer is not None
    assert buyer.is_buyer is True
    assert buyer.nda_signed_at is not None


def test_seed_creates_access_requests_in_three_distinct_states(seed_fn, session):
    from sqlmodel import select

    from app.models import AccessRequest, User

    seed_fn(session)

    buyer = session.exec(select(User).where(User.email == "buyer.seed@example.com")).first()
    requests = list(session.exec(select(AccessRequest).where(AccessRequest.buyer_id == buyer.id)).all())

    assert len(requests) == 3
    assert {r.status for r in requests} == {"approved", "requested", "denied"}
    # Each against a different listing — the unique constraint on
    # (listing_id, buyer_id) would otherwise make this impossible anyway.
    assert len({r.listing_id for r in requests}) == 3


def test_seed_creates_one_conversation_with_messages_for_the_approved_request(seed_fn, session):
    from sqlmodel import select

    from app.models import AccessRequest, Conversation, Message, User

    seed_fn(session)

    buyer = session.exec(select(User).where(User.email == "buyer.seed@example.com")).first()
    approved = session.exec(
        select(AccessRequest).where(AccessRequest.buyer_id == buyer.id, AccessRequest.status == "approved")
    ).first()

    conversation = session.exec(
        select(Conversation).where(
            Conversation.listing_id == approved.listing_id, Conversation.buyer_id == buyer.id
        )
    ).first()
    assert conversation is not None

    messages = list(
        session.exec(select(Message).where(Message.conversation_id == conversation.id)).all()
    )
    assert len(messages) >= 2
    assert any(m.sender_id == buyer.id for m in messages), "the buyer sent at least one message"
    assert any(m.sender_id != buyer.id for m in messages), "the seller sent at least one message"


def test_seed_adds_buyer_fixtures_to_a_database_already_carrying_listings(seed_fn, session):
    """The bug this guards against: an early draft gated the buyer/access/chat
    fixtures behind the *same* early return as the listing marketplace, which
    would make them permanently unreachable on any database seeded before
    this capability existed — `seed()` would see the marketplace marker,
    return 0, and never create the buyer at all. Simulated here by seeding
    once, deleting the buyer-side rows by hand (as if this capability did not
    exist yet), then seeding again."""
    from sqlmodel import delete, select

    from app.models import AccessRequest, Conversation, Message, User

    seed_fn(session)

    buyer = session.exec(select(User).where(User.email == "buyer.seed@example.com")).first()
    session.exec(delete(Message))
    session.exec(delete(Conversation))
    session.exec(delete(AccessRequest))
    session.delete(buyer)
    session.commit()

    created = seed_fn(session)
    assert created == 0, "the marketplace itself must not be reseeded"

    restored_buyer = session.exec(select(User).where(User.email == "buyer.seed@example.com")).first()
    assert restored_buyer is not None
    assert len(list(session.exec(select(AccessRequest)).all())) == 3
    assert len(list(session.exec(select(Conversation)).all())) == 1


def test_seed_twice_does_not_duplicate_the_buyer_or_access_requests(seed_fn, session):
    from sqlmodel import select

    from app.models import AccessRequest, Conversation, User

    seed_fn(session)
    seed_fn(session)

    buyers = list(session.exec(select(User).where(User.email == "buyer.seed@example.com")).all())
    requests = list(session.exec(select(AccessRequest)).all())
    conversations = list(session.exec(select(Conversation)).all())

    assert len(buyers) == 1
    assert len(requests) == 3
    assert len(conversations) == 1
