"""M7 — offers / LOI (spec 007): offer creation (A1-A8), withdraw (D1-D4), X1.

`Offer`, `OfferEvent`, `require_approved_buyer`, and every `/offers` route do
not exist yet, so every test here either asserts a status the app cannot yet
produce, or errors inside a fixture that calls a route that 404s (or imports a
model that doesn't exist). Both are runtime failures, not collection failures —
the red set is the work queue (mirrors `test_nda_gate.py`'s own framing).

Scope: this file owns **A** (creating an offer — `require_approved_buyer`,
D3/D6/D7) and **D** (withdraw — D4, the proposer-only mirror of B/C's
counterparty-only rule), plus **X1** (422 on a malformed offer/counter body).
**B**/**C** (the seller's decision + counter mechanics, the atomic accept, the
bilateral rights) and **E** (the sibling auto-decline sweep) live in
`test_offer_decisions.py`, along with S1/S3/S5/S6/S8/X2. **F**/**G** (the two
read queues) live in `test_offer_lists.py`, along with S2/S4/S7.
"""

import pytest

from tests.conftest import VALID_OFFER


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


# ── A — creating an offer (FR-17, D3, D6, D7) ────────────────────────────────

def test_a1_approved_buyer_creates_an_offer_on_a_live_listing(
    client, auth_headers, live_listing, granted_access, make_offer, offer_events
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)
    buyer_id = client.get("/api/auth/me", headers=buyer).json()["id"]

    res = make_offer(listing_id, buyer)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "submitted"
    assert body["proposed_by_role"] == "buyer"
    assert body["parent_offer_id"] is None

    # buyer_id is never on OfferRead (mirrors AccessRequestRead's minimalism) —
    # prove it's *this* caller's offer via the caller-scoped list instead.
    rows = client.get("/api/my/offers", headers=buyer).json()
    assert any(r["id"] == body["id"] for r in rows)

    events = offer_events(body["id"])
    assert len(events) == 1
    assert events[0]["action"] == "submitted"
    assert events[0]["from_status"] is None
    assert events[0]["to_status"] == "submitted"
    assert events[0]["actor_id"] == buyer_id


@pytest.mark.parametrize("state", ["none", "requested", "denied", "revoked"])
def test_a2_buyer_without_approved_access_is_403(
    client, auth_headers, live_listing, request_access, granted_access, make_offer, state
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)

    if state == "requested":
        request_access(listing_id, buyer)
    elif state == "denied":
        req_id = request_access(listing_id, buyer).json()["id"]
        client.post(f"/api/access-requests/{req_id}/deny", headers=seller)
    elif state == "revoked":
        req_id = granted_access(listing_id, buyer, seller)
        client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    # state == "none": no request of any kind — the same fact require_private_access gates.

    res = make_offer(listing_id, buyer)
    assert res.status_code == 403
    assert res.json()["code"] == "nda_access_required"


@pytest.mark.parametrize(
    "status", ["draft", "pending_review", "paused", "under_offer", "rejected", "closed"]
)
def test_a3_offer_on_a_non_live_listing_is_409(
    client, auth_headers, live_listing, granted_access, make_offer, force_status, status
):
    """Approved access is granted on a genuinely `live` listing (so `published_at`
    is set the way the product sets it — `require_approved_buyer`'s 404 check
    must not fire), then the status is forced to each of the six non-`live`
    values so the gate's own status guard is what's under test, isolated from
    whichever real transition would normally produce that status."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)
    force_status(listing_id, status)

    res = make_offer(listing_id, buyer)
    assert res.status_code == 409
    assert res.json()["code"] == "listing_not_live"


def test_a4_owner_cannot_offer_on_their_own_listing(client, auth_headers, live_listing, make_offer):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)

    res = make_offer(listing_id, seller)
    assert res.status_code == 403


def test_a5_never_published_listing_is_404(client, auth_headers, make_listing, make_offer):
    """Mirrors spec 005 D1 — an unpublished listing's existence is still a
    secret. Asserts the machine `code`, not just the status: an unmounted route
    also 404s (Starlette's own bare `{"detail": "Not Found"}`), which would
    satisfy a status-only assertion vacuously before the gate exists (the trap
    `test_nda_gate.py::test_d8`'s docstring names)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = make_listing(seller).json()["id"]      # never submitted, never approved

    res = make_offer(listing_id, buyer)
    assert res.status_code == 404
    assert res.json()["code"] == "not_found"


def test_a6_mass_assignment_on_create_is_ignored(
    client, auth_headers, live_listing, granted_access, make_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    other = auth_headers(email="other-buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)
    other_id = client.get("/api/auth/me", headers=other).json()["id"]

    res = make_offer(
        listing_id,
        buyer,
        status="accepted",
        buyer_id=other_id,
        proposed_by_role="seller",
        decided_at="2000-01-01T00:00:00",
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "submitted", "client-sent status must be ignored"
    assert body["proposed_by_role"] == "buyer", "client-sent proposed_by_role must be ignored"
    assert body.get("decided_at") is None, "a fresh offer is never pre-decided"

    mine = client.get("/api/my/offers", headers=buyer).json()
    assert any(r["id"] == body["id"] for r in mine), "the offer belongs to the real caller"
    forged_owner = client.get("/api/my/offers", headers=other).json()
    assert not any(r["id"] == body["id"] for r in forged_owner), "buyer_id must never come from the body"


def test_a7_a_second_active_offer_on_the_same_listing_is_409(
    client, auth_headers, live_listing, granted_access, make_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)

    first = make_offer(listing_id, buyer)
    assert first.status_code == 201

    second = make_offer(listing_id, buyer)
    assert second.status_code == 409
    assert second.json()["code"] == "offer_already_active"


def test_a8_no_credentials_is_401(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)

    res = client.post(f"/api/listings/{listing_id}/offers", json=VALID_OFFER)
    assert res.status_code == 401


# ── D — withdraw (D4) ─────────────────────────────────────────────────────────

def test_d1_buyer_withdraws_their_own_submitted_offer(
    client, auth_headers, live_listing, submitted_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    res = client.post(f"/api/offers/{offer_id}/withdraw", headers=buyer)
    assert res.status_code == 200
    assert res.json()["status"] == "withdrawn"


def test_d2_seller_cannot_withdraw_the_buyers_offer(
    client, auth_headers, live_listing, submitted_offer
):
    """Withdraw belongs to the proposer — the opposite rule from
    accept/decline/counter, which belong to the counterparty."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    res = client.post(f"/api/offers/{offer_id}/withdraw", headers=seller)
    assert res.status_code == 403


def test_d3_buyer_cannot_withdraw_the_sellers_counter(
    client, auth_headers, live_listing, submitted_offer
):
    """Symmetric to D2: the buyer did not propose the seller's counter, so
    withdrawing it (rather than declining it) is not theirs to do."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter",
        json={**VALID_OFFER, "price": "425000.00"},
        headers=seller,
    )
    rows = client.get("/api/my/offers", headers=buyer).json()
    counter_id = next(r["id"] for r in rows if r.get("parent_offer_id") == offer_id)

    res = client.post(f"/api/offers/{counter_id}/withdraw", headers=buyer)
    assert res.status_code == 403


def test_d4_withdrawing_an_already_decided_offer_is_409(
    client, auth_headers, live_listing, submitted_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(f"/api/offers/{offer_id}/decline", headers=seller)   # now terminal

    res = client.post(f"/api/offers/{offer_id}/withdraw", headers=buyer)
    assert res.status_code == 409
    assert res.json()["code"] == "offer_already_decided"


# ── Errors & failure modes (this file's slice: X1) ───────────────────────────

def test_x1_malformed_offer_body_is_422(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)

    bad_bodies = [
        {**VALID_OFFER, "price": "-100.00"},                              # negative price
        {k: v for k, v in VALID_OFFER.items() if k != "price"},           # missing price
        {k: v for k, v in VALID_OFFER.items() if k != "proposed_close_date"},  # missing close date
        {**VALID_OFFER, "price": "not-a-number"},                         # wrong type
    ]
    for body in bad_bodies:
        res = client.post(f"/api/listings/{listing_id}/offers", json=body, headers=buyer)
        assert res.status_code == 422, f"body {body!r} should be 422, got {res.status_code}"
