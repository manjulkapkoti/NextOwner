"""M7 — offers / LOI (spec 007): B1-B9, C1-C7, E1-E4, S1, S3, S5, S6, S8, X2.

The project's first **bilateral** state machine and its **first money surface**
(spec 007 header). `Offer`/`OfferEvent`, `offer_role_for`, `require_offer_party`,
and `accept`/`decline`/`counter`/`withdraw` do not exist yet, so every test here
either asserts a status the app cannot yet produce or errors reaching a route
that 404s — the red set is the work queue.

Scope: this file owns **B** (the seller's decision on a buyer-proposed offer —
the atomic offer+listing accept, ⭐), **C** (counter mechanics — a new linked
row per spec D1, ⭐), and **E** (the sibling auto-decline sweep on accept, spec
D2). It also owns the security criteria that only make sense once a decision
exists to probe: S1 (IDOR), S3 (mass assignment on counter), S5 (enumeration),
S6 (the race, extending B8), S8 (self-dealing is total and symmetric), and X2
(409 machine codes). Creation (A), withdraw (D), and X1 live in
`test_offers.py`. The two read queues (F/G) plus S2/S4/S7 live in
`test_offer_lists.py`.

Because `POST .../counter`'s own response shape is not pinned down by any
acceptance criterion (only that "a new offer row exists" — a DB-level fact),
these tests never assume which row a `counter` call's body represents. They
find the new row through the read endpoints instead (`GET /my/offers` /
`GET /my/listings/{id}/offers`, matched by `parent_offer_id`), so they hold
regardless of which convention the implementation picks.
"""

from decimal import Decimal

import pytest

from tests.conftest import VALID_OFFER


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


def _find_by_parent(rows, parent_id):
    return next(r for r in rows if r.get("parent_offer_id") == parent_id)


# ── B — the seller's decision on a buyer-proposed offer ⭐ ───────────────────

def test_b1_accept_flips_offer_and_listing_atomically(
    client, auth_headers, live_listing, submitted_offer
):
    """The transaction test: both flips asserted together (security.md §7 M7,
    testing_guide.md §5 M7)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    res = client.post(f"/api/offers/{offer_id}/accept", headers=seller)
    assert res.status_code == 200
    listing_status = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()["status"]
    assert res.json()["status"] == "accepted" and listing_status == "under_offer", (
        "accept must flip the offer AND the listing together, or not at all"
    )


def test_b2_decline_leaves_the_listing_untouched(
    client, auth_headers, live_listing, submitted_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    res = client.post(f"/api/offers/{offer_id}/decline", headers=seller)
    assert res.status_code == 200
    assert res.json()["status"] == "declined"
    listing_status = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()["status"]
    assert listing_status == "live", "only accept touches the listing"


@pytest.mark.parametrize("action", ["accept", "decline", "counter", "withdraw"])
def test_b3_a_stranger_cannot_act_on_the_offer(
    client, auth_headers, live_listing, submitted_offer, action
):
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    body = VALID_OFFER if action == "counter" else None
    res = client.post(f"/api/offers/{offer_id}/{action}", json=body, headers=stranger)
    assert res.status_code == 403


@pytest.mark.parametrize("action", ["accept", "decline", "counter"])
def test_b4_the_proposing_buyer_cannot_decide_their_own_offer(
    client, auth_headers, live_listing, submitted_offer, action
):
    """Decision rights belong to the counterparty, never the proposer (D1)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    body = VALID_OFFER if action == "counter" else None
    res = client.post(f"/api/offers/{offer_id}/{action}", json=body, headers=buyer)
    assert res.status_code == 403


@pytest.mark.parametrize(
    "terminal_action,terminal_actor",
    [("accept", "seller"), ("decline", "seller"), ("counter", "seller"), ("withdraw", "buyer")],
)
def test_b5_deciding_an_already_decided_offer_is_409(
    client, auth_headers, live_listing, submitted_offer, terminal_action, terminal_actor
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    actor = seller if terminal_actor == "seller" else buyer

    body = VALID_OFFER if terminal_action == "counter" else None
    first = client.post(f"/api/offers/{offer_id}/{terminal_action}", json=body, headers=actor)
    assert first.status_code == 200

    retry = client.post(f"/api/offers/{offer_id}/decline", headers=seller)
    assert retry.status_code == 409
    assert retry.json()["code"] == "offer_already_decided"


@pytest.mark.parametrize("action", ["accept", "decline"])
def test_b6_an_admin_who_does_not_own_the_listing_cannot_decide(
    client, auth_headers, admin_headers, live_listing, submitted_offer, action
):
    """Admin is not special-cased on this boundary either (mirrors spec 005 C8)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    admin = admin_headers()

    res = client.post(f"/api/offers/{offer_id}/{action}", headers=admin)
    assert res.status_code == 403


def test_b7_accept_writes_one_audit_row_with_the_deciding_seller_as_actor(
    client, auth_headers, live_listing, submitted_offer, offer_events
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    seller_id = client.get("/api/auth/me", headers=seller).json()["id"]

    client.post(f"/api/offers/{offer_id}/accept", headers=seller)

    accepted = [e for e in offer_events(offer_id) if e["action"] == "accepted"]
    assert len(accepted) == 1
    assert accepted[0]["actor_id"] == seller_id
    assert accepted[0]["from_status"] == "submitted"
    assert accepted[0]["to_status"] == "accepted"


@pytest.mark.parametrize("cause", ["paused_by_seller", "flipped_by_a_different_accept"])
def test_b8_accept_re_checks_listing_status_inside_the_transaction(
    client, auth_headers, live_listing, submitted_offer, force_status, cause
):
    """The listing's status is re-read INSIDE the accept transaction, not
    trusted from when the offer was created (security.md §6 race conditions).

    The second branch forces `under_offer` directly rather than routing through
    a second offer's real accept, so this stays orthogonal to E1-E4's own
    sibling-sweep mechanics (plan.md Build order: B8 must hold even at slice 3,
    before the sweep exists at slice 4) — S6 below is the version of this that
    uses two genuinely live offers.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    if cause == "paused_by_seller":
        client.post(f"/api/listings/{listing_id}/pause", headers=seller)
    else:
        force_status(listing_id, "under_offer")

    res = client.post(f"/api/offers/{offer_id}/accept", headers=seller)
    assert res.status_code == 409


@pytest.mark.parametrize("action", ["accept", "decline", "counter", "withdraw"])
def test_b9_no_credentials_on_any_decision_route_is_401(
    client, auth_headers, live_listing, submitted_offer, action
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    body = VALID_OFFER if action == "counter" else None
    res = client.post(f"/api/offers/{offer_id}/{action}", json=body)
    assert res.status_code == 401


# ── C — counter-offer mechanics ⭐ ─────────────────────────────────────────────

def test_c1_seller_counters_with_new_terms(client, auth_headers, live_listing, submitted_offer):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    counter_body = {**VALID_OFFER, "price": "425000.00", "structure": "70/30 seller financing"}
    res = client.post(f"/api/offers/{offer_id}/counter", json=counter_body, headers=seller)
    assert res.status_code == 200

    rows = client.get("/api/my/offers", headers=buyer).json()
    original = next(r for r in rows if r["id"] == offer_id)
    assert original["status"] == "countered"

    child = _find_by_parent(rows, offer_id)
    assert child["proposed_by_role"] == "seller"
    assert child["status"] == "submitted"
    assert child["listing_id"] == listing_id
    assert Decimal(str(child["price"])) == Decimal("425000.00")
    assert child["structure"] == "70/30 seller financing"


def test_c2_both_rows_appear_in_the_full_history(client, auth_headers, live_listing, submitted_offer):
    """FR-17, user story 8 — nothing hidden, from either party's own read route."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )

    buyer_rows = client.get("/api/my/offers", headers=buyer).json()
    seller_rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()

    for rows in (buyer_rows, seller_rows):
        ids = {r["id"] for r in rows}
        assert offer_id in ids
        original = next(r for r in rows if r["id"] == offer_id)
        assert original["status"] == "countered"
        child = _find_by_parent(rows, offer_id)
        assert child["status"] == "submitted"


def test_c3_buyer_accepting_the_counter_is_also_atomic(
    client, auth_headers, live_listing, submitted_offer
):
    """Proves accept's atomic behavior is identical regardless of which party
    proposed the winning terms."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get("/api/my/offers", headers=buyer).json()
    counter_id = _find_by_parent(rows, offer_id)["id"]

    res = client.post(f"/api/offers/{counter_id}/accept", headers=buyer)
    assert res.status_code == 200
    listing_status = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()["status"]
    assert res.json()["status"] == "accepted" and listing_status == "under_offer"


def test_c4_buyer_declines_the_counter(client, auth_headers, live_listing, submitted_offer):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get("/api/my/offers", headers=buyer).json()
    counter_id = _find_by_parent(rows, offer_id)["id"]
    before_count = len(rows)

    res = client.post(f"/api/offers/{counter_id}/decline", headers=buyer)
    assert res.status_code == 200
    assert res.json()["status"] == "declined"

    after_rows = client.get("/api/my/offers", headers=buyer).json()
    assert len(after_rows) == before_count, "the negotiation ends — no further row is created"


def test_c5_the_chain_extends_past_one_round(client, auth_headers, live_listing, submitted_offer):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get("/api/my/offers", headers=buyer).json()
    seller_counter_id = _find_by_parent(rows, offer_id)["id"]

    res = client.post(
        f"/api/offers/{seller_counter_id}/counter",
        json={**VALID_OFFER, "price": "410000.00"},
        headers=buyer,
    )
    assert res.status_code == 200

    rows = client.get("/api/my/offers", headers=buyer).json()
    seller_counter = next(r for r in rows if r["id"] == seller_counter_id)
    assert seller_counter["status"] == "countered"
    third = _find_by_parent(rows, seller_counter_id)
    assert third["proposed_by_role"] == "buyer"
    assert third["status"] == "submitted"


@pytest.mark.parametrize("action", ["accept", "decline", "counter"])
def test_c6_the_seller_cannot_decide_their_own_counter(
    client, auth_headers, live_listing, submitted_offer, action
):
    """The bilateral half of B4: on a seller-proposed row, decision rights
    belong to the buyer, never the seller who proposed it."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    counter_id = _find_by_parent(rows, offer_id)["id"]

    body = VALID_OFFER if action == "counter" else None
    res = client.post(f"/api/offers/{counter_id}/{action}", json=body, headers=seller)
    assert res.status_code == 403


def test_c7_a_counter_writes_two_audit_rows(
    client, auth_headers, live_listing, submitted_offer, offer_events
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    counter_id = _find_by_parent(rows, offer_id)["id"]

    countered = [e for e in offer_events(offer_id) if e["action"] == "countered"]
    assert len(countered) == 1
    assert countered[0]["from_status"] == "submitted"
    assert countered[0]["to_status"] == "countered"

    submitted = [e for e in offer_events(counter_id) if e["action"] == "submitted"]
    assert len(submitted) == 1
    assert submitted[0]["from_status"] is None
    assert submitted[0]["to_status"] == "submitted"


# ── E — the sibling-offer policy on accept ───────────────────────────────────

def test_e1_accepting_one_offer_auto_declines_an_independent_sibling(
    client, auth_headers, live_listing, granted_access, submitted_offer, offer_events
):
    seller, buyer_a = _seller_and_buyer(auth_headers, buyer_email="buyer-a@example.com")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_a = submitted_offer(listing_id, buyer_a, seller)
    granted_access(listing_id, buyer_b, seller)
    offer_b = client.post(
        f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=buyer_b
    ).json()["id"]
    seller_id = client.get("/api/auth/me", headers=seller).json()["id"]

    client.post(f"/api/offers/{offer_a}/accept", headers=seller)

    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    sibling = next(r for r in rows if r["id"] == offer_b)
    assert sibling["status"] == "declined"

    auto = [e for e in offer_events(offer_b) if e["action"] == "auto_declined"]
    assert len(auto) == 1
    assert auto[0]["actor_id"] == seller_id
    assert auto[0]["from_status"] == "submitted"
    assert auto[0]["to_status"] == "declined"


def test_e2_a_seller_proposed_counter_awaiting_reply_is_also_auto_declined(
    client, auth_headers, live_listing, granted_access, submitted_offer
):
    """The policy applies to every `submitted` row on the listing, regardless
    of who proposed it — not only rows still awaiting the seller."""
    seller, buyer_a = _seller_and_buyer(auth_headers, buyer_email="buyer-a@example.com")
    buyer_c = auth_headers(email="buyer-c@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_a = submitted_offer(listing_id, buyer_a, seller)
    granted_access(listing_id, buyer_c, seller)
    offer_c = client.post(
        f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=buyer_c
    ).json()["id"]
    client.post(
        f"/api/offers/{offer_c}/counter", json={**VALID_OFFER, "price": "300000.00"}, headers=seller
    )
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    counter_c_id = _find_by_parent(rows, offer_c)["id"]

    client.post(f"/api/offers/{offer_a}/accept", headers=seller)

    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    counter_c = next(r for r in rows if r["id"] == counter_c_id)
    assert counter_c["status"] == "declined"


@pytest.mark.parametrize("terminal_action", ["decline", "withdraw"])
def test_e3_an_already_terminal_sibling_is_untouched(
    client, auth_headers, live_listing, granted_access, submitted_offer, offer_events, terminal_action
):
    seller, buyer_a = _seller_and_buyer(auth_headers, buyer_email="buyer-a@example.com")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_a = submitted_offer(listing_id, buyer_a, seller)
    granted_access(listing_id, buyer_b, seller)
    offer_b = client.post(
        f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=buyer_b
    ).json()["id"]

    if terminal_action == "decline":
        client.post(f"/api/offers/{offer_b}/decline", headers=seller)
    else:
        client.post(f"/api/offers/{offer_b}/withdraw", headers=buyer_b)

    client.post(f"/api/offers/{offer_a}/accept", headers=seller)

    expected = {"decline": "declined", "withdraw": "withdrawn"}[terminal_action]
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    sibling = next(r for r in rows if r["id"] == offer_b)
    assert sibling["status"] == expected, "auto-decline only ever reaches rows currently submitted"
    assert not any(e["action"] == "auto_declined" for e in offer_events(offer_b))


def test_e4_the_accepting_buyers_own_prior_history_is_untouched(
    client, auth_headers, live_listing, submitted_offer, offer_events
):
    """Sibling policy resolves live offers; it never rewrites history — even
    the accepting buyer's own earlier countered row in the same chain."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get("/api/my/offers", headers=buyer).json()
    counter_id = _find_by_parent(rows, offer_id)["id"]

    client.post(f"/api/offers/{counter_id}/accept", headers=buyer)

    rows = client.get("/api/my/offers", headers=buyer).json()
    original = next(r for r in rows if r["id"] == offer_id)
    assert original["status"] == "countered", "the buyer's own earlier row must not be rewritten by the sweep"
    assert not any(e["action"] == "auto_declined" for e in offer_events(offer_id))


# ── Security & abuse (this file's slice: S1, S3, S5, S6, S8) ────────────────

def test_s1_idor_guessing_an_unrelated_offer_id_is_403(
    client, auth_headers, live_listing, submitted_offer
):
    seller_a, buyer_a = _seller_and_buyer(
        auth_headers, seller_email="seller-a@example.com", buyer_email="buyer-a@example.com"
    )
    seller_b = auth_headers(email="seller-b@example.com", role="seller")
    listing_id = live_listing(seller_a)
    offer_id = submitted_offer(listing_id, buyer_a, seller_a)

    res = client.post(f"/api/offers/{offer_id}/accept", headers=seller_b)
    assert res.status_code == 403


def test_s3_mass_assignment_on_counter_is_ignored(client, auth_headers, live_listing, submitted_offer):
    seller, buyer = _seller_and_buyer(auth_headers)
    other = auth_headers(email="other@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)
    other_id = client.get("/api/auth/me", headers=other).json()["id"]

    res = client.post(
        f"/api/offers/{offer_id}/counter",
        json={
            **VALID_OFFER,
            "decided_at": "2000-01-01T00:00:00",
            "proposed_by_role": "buyer",
            "buyer_id": other_id,
        },
        headers=seller,
    )
    assert res.status_code == 200

    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    child = _find_by_parent(rows, offer_id)
    assert child["proposed_by_role"] == "seller", "the server derives the role from the endpoint, never the body"
    other_rows = client.get("/api/my/offers", headers=other).json()
    assert not any(r["id"] == child["id"] for r in other_rows), "buyer_id must stay the original buyer"


def test_s5_probing_offer_ids_gives_a_uniform_no_existence_signal(
    client, auth_headers, live_listing, submitted_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    listing_id = live_listing(seller)
    real_id = submitted_offer(listing_id, buyer, seller)

    real_probe = client.post(f"/api/offers/{real_id}/accept", headers=stranger)
    fake_probe = client.post(f"/api/offers/{real_id + 987_654}/accept", headers=stranger)

    assert real_probe.status_code == fake_probe.status_code == 403
    assert real_probe.json().get("code") == fake_probe.json().get("code")


def test_s6_two_concurrent_accepts_yield_exactly_one_winner(
    client, auth_headers, live_listing, granted_access, submitted_offer
):
    """Extends B8. A true OS-thread race isn't meaningful in this harness:
    `conftest.py`'s `client` fixture binds every request in a test to the
    **same** SQLAlchemy `Session` object (`get_session` is overridden to
    `lambda: session`), so two real threads would race on one non-thread-safe
    Session rather than two independent DB transactions — the same limitation
    `test_chat.py::test_f5` documents and works around by simulating the
    interleaving deterministically instead of on real scheduler timing.

    This does the same: issues both accepts back-to-back against two genuinely
    live `submitted` offers (rather than B8's forced status) and asserts the
    invariant the transaction is supposed to guarantee regardless of ordering —
    never two accepted offers on one listing.
    """
    seller, buyer_a = _seller_and_buyer(auth_headers, buyer_email="buyer-a@example.com")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_a = submitted_offer(listing_id, buyer_a, seller)
    granted_access(listing_id, buyer_b, seller)
    offer_b = client.post(
        f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=buyer_b
    ).json()["id"]

    res_a = client.post(f"/api/offers/{offer_a}/accept", headers=seller)
    res_b = client.post(f"/api/offers/{offer_b}/accept", headers=seller)

    assert sorted([res_a.status_code, res_b.status_code]) == [200, 409], (
        "exactly one accept must win, the other must 409"
    )
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    accepted = [r for r in rows if r["status"] == "accepted"]
    assert len(accepted) == 1, "never two accepted offers on one listing"


def test_s8_decision_rights_and_withdrawal_rights_are_disjoint_opposites(
    client, auth_headers, live_listing, submitted_offer
):
    """Consolidates B4/C6 (proposer can never decide) and D2/D3 (counterparty
    can never withdraw) across both a buyer-proposed row and a seller-proposed
    counter, in one place, as its own named invariant."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    for action in ("accept", "decline", "counter"):
        body = VALID_OFFER if action == "counter" else None
        res = client.post(f"/api/offers/{offer_id}/{action}", json=body, headers=buyer)
        assert res.status_code == 403, f"buyer (proposer) must not {action} their own offer"
    assert client.post(f"/api/offers/{offer_id}/withdraw", headers=seller).status_code == 403, (
        "seller (counterparty) must not withdraw the buyer's offer"
    )

    client.post(
        f"/api/offers/{offer_id}/counter", json={**VALID_OFFER, "price": "425000.00"}, headers=seller
    )
    rows = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).json()
    counter_id = _find_by_parent(rows, offer_id)["id"]

    for action in ("accept", "decline", "counter"):
        body = VALID_OFFER if action == "counter" else None
        res = client.post(f"/api/offers/{counter_id}/{action}", json=body, headers=seller)
        assert res.status_code == 403, f"seller (proposer) must not {action} their own counter"
    assert client.post(f"/api/offers/{counter_id}/withdraw", headers=buyer).status_code == 403, (
        "buyer (counterparty) must not withdraw the seller's counter"
    )


# ── Errors & failure modes (this file's slice: X2) ───────────────────────────

def test_x2_409_responses_carry_the_exact_machine_code(
    client, auth_headers, live_listing, submitted_offer, make_offer
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    dup = make_offer(listing_id, buyer)          # still submitted — offer_already_active
    assert dup.status_code == 409
    assert dup.json()["code"] == "offer_already_active"

    client.post(f"/api/offers/{offer_id}/decline", headers=seller)
    retry = client.post(f"/api/offers/{offer_id}/decline", headers=seller)   # offer_already_decided
    assert retry.status_code == 409
    assert retry.json()["code"] == "offer_already_decided"

    client.post(f"/api/listings/{listing_id}/pause", headers=seller)
    third = make_offer(listing_id, buyer)        # listing_not_live
    assert third.status_code == 409
    assert third.json()["code"] == "listing_not_live"
