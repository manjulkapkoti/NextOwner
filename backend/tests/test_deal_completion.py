"""M12 — deal completion: the happy paths, the state machine, the audit rows.

Spec `specs/012-deal-completion/spec.md` families **A** (mark sold), **B**
(re-list), **C** (illegal transitions + atomicity), **D** (audit rows) and
**E** (notifications). The forbidden paths live in
`test_deal_completion_security.py` — they were written first (`testing_guide.md`
§1), and this file assumes they hold.

The thing this milestone is really guarding: **the recorded sale price is
server-derived from the accepted offer** (Article 2 #4). Every A-family test
here exists to make a client-supplied price impossible to believe.
"""

from decimal import Decimal

import pytest


def _seller_and_buyer(auth_headers):
    return (
        auth_headers(email="seller@example.com", role="seller"),
        auth_headers(email="buyer@example.com", role="buyer"),
    )


# ── A — marking a deal sold ──────────────────────────────────────────────────


def test_a1_seller_marks_under_offer_listing_sold(client, auth_headers, under_offer_listing):
    """A1 — `under_offer → sold`, with a server-stamped `sold_at`."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "sold"
    assert body["sold_at"] is not None


def test_a2_final_price_is_the_accepted_offers_price_not_the_asking_price(
    client, auth_headers, under_offer_listing
):
    """A2 — the recorded price is the accepted offer's, to the cent (spec D4).

    `VALID_LISTING`'s asking price is 500000.00; this offer deliberately is not.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer, price="123456.78")

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 200, res.text
    assert Decimal(res.json()["final_price"]) == Decimal("123456.78")
    assert Decimal(res.json()["asking_price"]) == Decimal("500000.00")


def test_a3_accepted_offer_becomes_completed_and_keeps_its_decided_at(
    client, auth_headers, under_offer_listing, offer_status, session
):
    """A3 — the offer reaches `completed`; `decided_at` still records the accept."""
    from sqlalchemy import text

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer)
    decided_at_before = session.execute(
        text("SELECT decided_at FROM offer WHERE id = :i"), {"i": offer_id}
    ).first()[0]

    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert offer_status(offer_id) == "completed"
    decided_at_after = session.execute(
        text("SELECT decided_at FROM offer WHERE id = :i"), {"i": offer_id}
    ).first()[0]
    assert decided_at_after == decided_at_before


def test_a4_final_price_follows_an_accepted_seller_counter(
    client, auth_headers, live_listing, submitted_offer
):
    """A4 — the derivation follows the *accepted row*, not the thread's root.

    The buyer opens at 450000, the seller counters at 610000.00, the buyer
    accepts the counter. The sale closed at the counter's price (M7 D1's chain).
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    root_id = submitted_offer(listing_id, buyer, seller, price="450000.00")

    counter = client.post(
        f"/api/offers/{root_id}/counter",
        json={
            "price": "610000.00",
            "structure": "all cash",
            "contingencies": None,
            "proposed_close_date": "2026-11-01",
        },
        headers=seller,
    )
    assert counter.status_code in (200, 201), counter.text
    counter_id = counter.json()["id"]
    accepted = client.post(f"/api/offers/{counter_id}/accept", headers=buyer)
    assert accepted.status_code == 200, accepted.text

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 200, res.text
    assert Decimal(res.json()["final_price"]) == Decimal("610000.00")


def test_a5_sold_listing_surfaces_the_sale_on_both_owner_routes(
    client, auth_headers, under_offer_listing
):
    """A5 — `final_price`/`sold_at` on the owner's detail *and* summary rows."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer, price="777000.00")
    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    detail = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
    assert Decimal(detail["final_price"]) == Decimal("777000.00")
    assert detail["sold_at"] is not None

    row = next(
        r for r in client.get("/api/my/listings", headers=seller).json()
        if r["id"] == listing_id
    )
    assert Decimal(row["final_price"]) == Decimal("777000.00")
    assert row["sold_at"] is not None


def test_a6_an_unsold_listing_carries_no_sale_fields(client, auth_headers, make_listing):
    """A6 — both columns are null until `mark-sold` writes them."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]

    body = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()

    assert body["final_price"] is None
    assert body["sold_at"] is None


# ── B — the deal fell through: re-list ───────────────────────────────────────


def test_b1_seller_relists_an_under_offer_listing(client, auth_headers, under_offer_listing):
    """B1 — `under_offer → live`."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    res = client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "live"


def test_b2_relist_moves_the_accepted_offer_to_lapsed(
    client, auth_headers, under_offer_listing, offer_status
):
    """B2 — `accepted → lapsed`, not `declined` and not left `accepted` (D5)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer)

    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    assert offer_status(offer_id) == "lapsed"


def test_b3_relisted_listing_returns_to_public_browse_with_its_original_published_at(
    client, auth_headers, under_offer_listing
):
    """B3 — back on the marketplace; `published_at` records *first* publication (D7)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)
    published_at = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "published_at"
    ]

    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    page = client.get("/api/listings").json()
    assert listing_id in [row["id"] for row in page["items"]]
    after = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
    assert after["published_at"] == published_at


def test_b4_relist_does_not_revive_auto_declined_siblings(
    client, auth_headers, live_listing, submitted_offer, under_offer_listing,
    offer_status, offer_events,
):
    """B4 — M7's auto-decline stands; re-list never un-declines (spec D6)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    rival_a = auth_headers(email="rival-a@example.com", role="buyer")
    rival_b = auth_headers(email="rival-b@example.com", role="buyer")

    listing_id = live_listing(seller)
    sib_a = submitted_offer(listing_id, rival_a, seller, price="400000.00")
    sib_b = submitted_offer(listing_id, rival_b, seller, price="410000.00")
    under_offer_listing(seller, buyer, listing_id=listing_id)
    assert offer_status(sib_a) == "declined" and offer_status(sib_b) == "declined"
    events_before = len(offer_events(sib_a)) + len(offer_events(sib_b))

    # Asserted, not fired-and-forgotten: a `relist` that 404s also leaves the
    # siblings untouched, which made this test pass before M12 existed at all
    # (caught by the red-set check — constitution Article 3 §2).
    assert client.post(
        f"/api/listings/{listing_id}/relist", headers=seller
    ).status_code == 200

    assert offer_status(sib_a) == "declined"
    assert offer_status(sib_b) == "declined"
    assert len(offer_events(sib_a)) + len(offer_events(sib_b)) == events_before


def test_b5_a_relisted_listing_can_be_sold_again_to_a_different_buyer(
    client, auth_headers, under_offer_listing, session
):
    """B5 — the at-most-one-`accepted`-offer-per-listing invariant D5 protects."""
    from sqlalchemy import text

    seller, buyer = _seller_and_buyer(auth_headers)
    second_buyer = auth_headers(email="buyer-two@example.com", role="buyer")
    listing_id, _ = under_offer_listing(seller, buyer)
    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    _, second_offer = under_offer_listing(seller, second_buyer, listing_id=listing_id)

    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "under_offer"
    accepted = session.execute(
        text("SELECT id FROM offer WHERE listing_id = :i AND status = 'accepted'"),
        {"i": listing_id},
    ).fetchall()
    assert [r[0] for r in accepted] == [second_offer]


def test_b6_reselling_records_the_second_offers_price(
    client, auth_headers, under_offer_listing
):
    """B6 — the close after a re-list derives from the *second* accepted offer."""
    seller, buyer = _seller_and_buyer(auth_headers)
    second_buyer = auth_headers(email="buyer-two@example.com", role="buyer")
    listing_id, _ = under_offer_listing(seller, buyer, price="300000.00")
    client.post(f"/api/listings/{listing_id}/relist", headers=seller)
    under_offer_listing(seller, second_buyer, listing_id=listing_id, price="355000.55")

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 200, res.text
    assert Decimal(res.json()["final_price"]) == Decimal("355000.55")


# ── C — illegal transitions and atomicity ────────────────────────────────────

_NON_UNDER_OFFER = ["draft", "pending_review", "live", "paused", "closed", "rejected", "sold"]


@pytest.mark.parametrize("status", _NON_UNDER_OFFER)
def test_c1_mark_sold_from_any_other_state_is_409(
    client, auth_headers, make_listing, force_status, status
):
    """C1 — only `under_offer` may be sold."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]
    force_status(listing_id, status)

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 409, f"{status}: {res.text}"
    assert res.json()["code"] == "invalid_transition"


@pytest.mark.parametrize("status", _NON_UNDER_OFFER)
def test_c2_relist_from_any_other_state_is_409(
    client, auth_headers, make_listing, force_status, status
):
    """C2 — only `under_offer` may be re-listed. `sold` included: no un-sell."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]
    force_status(listing_id, status)

    res = client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    assert res.status_code == 409, f"{status}: {res.text}"
    assert res.json()["code"] == "invalid_transition"


def test_c3_a_refused_mark_sold_writes_nothing(
    client, auth_headers, under_offer_listing, offer_status, listing_events, offer_events
):
    """C3 — the second close is refused and leaves every row exactly as it was.

    The log records what happened, not what was tried — the rule `_transition`
    and `_record` already keep, re-asserted for the two new transitions.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer, price="480000.00")
    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)
    before = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
    listing_event_count = len(listing_events(listing_id))
    offer_event_count = len(offer_events(offer_id))

    again = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert again.status_code == 409
    after = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
    assert after["status"] == before["status"] == "sold"
    assert after["final_price"] == before["final_price"]
    assert after["sold_at"] == before["sold_at"]
    assert offer_status(offer_id) == "completed"
    assert len(listing_events(listing_id)) == listing_event_count
    assert len(offer_events(offer_id)) == offer_event_count


def test_c4_under_offer_with_no_accepted_offer_is_409_not_500(
    client, auth_headers, under_offer_listing, force_offer_status
):
    """C4 — a data anomaly answers with the contract, never a NoneType traceback."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer)
    force_offer_status(offer_id, "withdrawn")     # unreachable via the product

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "no_accepted_offer"
    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "under_offer"


def test_c5_concurrent_mark_sold_closes_the_deal_exactly_once(
    client, auth_headers, under_offer_listing, listing_events, offer_events, user_id, session
):
    """C5 — compare-and-swap, not read-then-write (`security.md` §6 races).

    Constructed exactly like `test_offer_accept_race.py`, and for the same
    reason: every HTTP call in a test shares ONE `Session` (conftest's `client`
    override), so "two requests" through the client are serialized and a
    read-then-write TOCTOU would pass. Production hands each request its own
    `Session` (`app/db.py`), so the second identity map is the whole point —
    request B's reads land before request A's write commits, and only a
    conditional UPDATE checked by rowcount can refuse B.
    """
    from sqlmodel import Session

    from app.errors import InvalidTransition
    from app.models import Listing, User
    from app.routers.listings import mark_listing_sold

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer)
    seller_id = user_id(seller)

    session_b = Session(session.get_bind())
    seller_view_a, seller_view_b = session.get(User, seller_id), session_b.get(User, seller_id)
    listing_a, listing_b = session.get(Listing, listing_id), session_b.get(Listing, listing_id)
    assert listing_b.status == "under_offer", "sanity: B's stale read caught the live state"

    result_a = mark_listing_sold(listing=listing_a, user=seller_view_a, session=session)
    assert result_a.status == "sold"

    try:
        mark_listing_sold(listing=listing_b, user=seller_view_b, session=session_b)
        raced = True
    except InvalidTransition:
        raced = False
    finally:
        session_b.close()

    assert raced is False, "B's concurrent close must be refused (409), not honored"
    assert [e["action"] for e in listing_events(listing_id)].count("sold") == 1
    assert [e["action"] for e in offer_events(offer_id)].count("completed") == 1


# ── D — audit rows ───────────────────────────────────────────────────────────


def test_d1_mark_sold_writes_a_listing_event(
    client, auth_headers, under_offer_listing, listing_events, user_id
):
    """D1 — `action="sold"`, `under_offer → sold`, actor from the JWT."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    event = [e for e in listing_events(listing_id) if e["action"] == "sold"]
    assert len(event) == 1
    assert event[0]["from_status"] == "under_offer"
    assert event[0]["to_status"] == "sold"
    assert event[0]["actor_id"] == user_id(seller)


def test_d2_mark_sold_writes_an_offer_event(
    client, auth_headers, under_offer_listing, offer_events, user_id
):
    """D2 — `action="completed"`, `accepted → completed`, actor is the seller."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer)

    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    event = [e for e in offer_events(offer_id) if e["action"] == "completed"]
    assert len(event) == 1
    assert event[0]["from_status"] == "accepted"
    assert event[0]["to_status"] == "completed"
    assert event[0]["actor_id"] == user_id(seller)


def test_d3_relist_writes_a_listing_event(
    client, auth_headers, under_offer_listing, listing_events
):
    """D3 — `action="fell_through"`, the name spec 003's plan predicted."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    event = [e for e in listing_events(listing_id) if e["action"] == "fell_through"]
    assert len(event) == 1
    assert event[0]["from_status"] == "under_offer"
    assert event[0]["to_status"] == "live"


def test_d4_relist_writes_an_offer_event(
    client, auth_headers, under_offer_listing, offer_events
):
    """D4 — `action="lapsed"`, `accepted → lapsed`."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, offer_id = under_offer_listing(seller, buyer)

    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    event = [e for e in offer_events(offer_id) if e["action"] == "lapsed"]
    assert len(event) == 1
    assert event[0]["from_status"] == "accepted"
    assert event[0]["to_status"] == "lapsed"


def test_d5_refused_attempts_write_no_audit_rows(
    client, auth_headers, under_offer_listing, make_listing, force_status,
    listing_events, offer_events,
):
    """D5 — a 409 (wrong state) and a 404 (wrong caller) both leave the log alone."""
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="seller")
    listing_id, offer_id = under_offer_listing(seller, buyer)
    listing_event_count = len(listing_events(listing_id))
    offer_event_count = len(offer_events(offer_id))

    wrong_state_id = make_listing(seller).json()["id"]
    force_status(wrong_state_id, "live")
    assert client.post(
        f"/api/listings/{wrong_state_id}/relist", headers=seller
    ).status_code == 409
    assert client.post(
        f"/api/listings/{listing_id}/mark-sold", headers=stranger
    ).status_code == 404

    assert len(listing_events(wrong_state_id)) == 0
    assert len(listing_events(listing_id)) == listing_event_count
    assert len(offer_events(offer_id)) == offer_event_count


# ── E — notifications (M8 projection) ────────────────────────────────────────


def test_e1_mark_sold_notifies_the_buyer_and_not_the_seller(
    client, auth_headers, under_offer_listing, notification_rows, user_id
):
    """E1 — the counterparty is told; nobody is notified of their own action."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)
    seller_before = len(notification_rows(user_id(seller)))

    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    buyer_types = [n["type"] for n in notification_rows(user_id(buyer))]
    assert buyer_types.count("offer_completed") == 1
    assert len(notification_rows(user_id(seller))) == seller_before


def test_e2_relist_notifies_only_the_buyer_whose_offer_lapsed(
    client, auth_headers, live_listing, submitted_offer, under_offer_listing,
    notification_rows, user_id,
):
    """E2 — the auto-declined rivals hear nothing new; their thread ended at M7."""
    seller, buyer = _seller_and_buyer(auth_headers)
    rival = auth_headers(email="rival@example.com", role="buyer")
    listing_id = live_listing(seller)
    submitted_offer(listing_id, rival, seller, price="400000.00")
    under_offer_listing(seller, buyer, listing_id=listing_id)
    rival_before = len(notification_rows(user_id(rival)))

    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    assert [n["type"] for n in notification_rows(user_id(buyer))].count("offer_lapsed") == 1
    assert len(notification_rows(user_id(rival))) == rival_before


def test_e3_recipient_is_the_buyer_even_when_the_seller_proposed_the_accepted_terms(
    client, auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """E3 — role-based, not `proposed_by_role`-based (spec D9).

    The accepted row here is a *seller* counter, so M7's proposer rule would
    send the close notification to the seller. It must go to the buyer.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    root_id = submitted_offer(listing_id, buyer, seller)
    counter_id = client.post(
        f"/api/offers/{root_id}/counter",
        json={
            "price": "610000.00",
            "structure": "all cash",
            "contingencies": None,
            "proposed_close_date": "2026-11-01",
        },
        headers=seller,
    ).json()["id"]
    client.post(f"/api/offers/{counter_id}/accept", headers=buyer)
    seller_before = len(notification_rows(user_id(seller)))

    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert [n["type"] for n in notification_rows(user_id(buyer))].count("offer_completed") == 1
    assert len(notification_rows(user_id(seller))) == seller_before
