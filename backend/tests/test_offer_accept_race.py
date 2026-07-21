"""M7 / spec 007 — regression pin for the atomic accept under REAL concurrency
(S6/B8, `security.md` §6 race conditions).

Originated as the independent appsec review's proof-of-concept on
`feat/007-offers`: it demonstrated that `accept_offer`'s guard was a
read-then-write TOCTOU, not a compare-and-swap, so two concurrent accepts could
both pass a stale snapshot check and both commit — two `accepted` offers on one
listing, the exact invariant spec 007 S6 names as the crown jewel.
`test_offer_decisions.py::test_s6_...` cannot catch it: every request in a test
shares ONE `Session` (`conftest.py`'s `client` override), so its "concurrent"
calls are serialized; production's `get_session()` hands each request its own
`Session(engine)` (`app/db.py`), with its own identity map.

This reproduces that window deterministically — two independently-created
`Session` objects (what two concurrent requests get) calling the actual shipped
`accept_offer`, with B's reads landing before A's write commits. It FAILED
before the fix and PASSES after it: `accept_offer` now compare-and-swaps
(`UPDATE ... WHERE id=:id AND status='submitted'`, and the listing `... AND
status='live'`, each checked by rowcount), so B's second accept finds the row
already moved and 409s instead of silently overwriting A's sibling sweep. Kept
as a permanent pin — do not delete it, and do not weaken it to a single-session
test: the single-session case is already covered by S6, and the whole point
here is the *second* identity map.
"""

from sqlmodel import Session

from app.models import Listing, Offer, User
from app.routers.offers import accept_offer
from tests.conftest import VALID_OFFER


def test_two_independent_sessions_racing_accept_yield_exactly_one_winner(
    client, auth_headers, live_listing, granted_access, session
):
    seller = auth_headers(email="race-seller@example.com", role="seller")
    buyer_a = auth_headers(email="race-buyer-a@example.com", role="buyer")
    buyer_b = auth_headers(email="race-buyer-b@example.com", role="buyer")
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer_a, seller)
    granted_access(listing_id, buyer_b, seller)

    offer_a_id = client.post(
        f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=buyer_a
    ).json()["id"]
    offer_b_id = client.post(
        f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=buyer_b
    ).json()["id"]
    seller_id = client.get("/api/auth/me", headers=seller).json()["id"]

    # `session` is the one Session object every HTTP call in this test shares
    # (conftest's `client` fixture) — it plays "request A's session," exactly as
    # it would in production. `session_b` is a SECOND, independent Session bound
    # to the same engine — exactly what a second, concurrent request gets from
    # `get_session()`. Nothing here uses a different engine or DB: only the
    # number of live Session objects (identity maps) changes, the one variable
    # that matters.
    session_b = Session(session.get_bind())

    seller_view_a = session.get(User, seller_id)
    seller_view_b = session_b.get(User, seller_id)
    off_a = session.get(Offer, offer_a_id)
    off_b = session_b.get(Offer, offer_b_id)

    # Request B's reads land here — before request A's accept has run at all.
    # Realistic: nothing slow separates `require_offer_party`'s offer-load from
    # `accept_offer`, so two nearly-simultaneous requests' reads interleave
    # before either write lands.
    listing_view_b = session_b.get(Listing, off_b.listing_id)
    assert listing_view_b.status == "live", "sanity: B's stale read captured a live listing"

    # Request A completes in full — the shipped function, unmodified — and
    # commits: offer A -> accepted, listing -> under_offer, and (per spec D2) its
    # own sibling sweep marks offer B `declined` in the SAME transaction.
    result_a = accept_offer(offer_and_role=(off_a, "seller"), user=seller_view_a, session=session)
    assert result_a.status == "accepted"

    # Request B, holding a session whose identity map was populated BEFORE A's
    # commit, still sees `off_b`/`listing_view_b` as the stale "submitted"/"live"
    # snapshot. With the compare-and-swap fix, `accept_offer`'s conditional
    # UPDATEs re-check against committed DB state at write time, so B is refused
    # (409) rather than overwriting A's sibling sweep.
    from app.errors import InvalidTransition

    try:
        accept_offer(offer_and_role=(off_b, "seller"), user=seller_view_b, session=session_b)
        raced = True
    except InvalidTransition:
        raced = False
    finally:
        session_b.close()

    assert raced is False, "B's concurrent accept must be refused (409), not honored"

    # The invariant spec 007 S6/B8 name as the crown jewel: never two accepted
    # offers on one listing. Read back through the real endpoint, past any
    # session-local staleness, as an independent verifier would.
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    accepted = [r for r in rows if r["status"] == "accepted"]
    assert len(accepted) == 1, (
        f"S6/B8 invariant: expected exactly one accepted offer on the listing, "
        f"found {len(accepted)}: {accepted}"
    )
