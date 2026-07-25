"""M8 — saved searches & the alert fan-out (spec 008): A (CRUD), B (fan-out).

Written failing first: the `savedsearch` table, `/api/saved-searches`, and the
publication fan-out do not exist yet, so every test here calls a route that
404s or asserts on a notification nothing writes.

FR-11 is the requirement ("buyers can save a search; new matching listings
trigger an alert"); FR-8 is the propagation half ("state changes propagate to
search and alerts"). The matching predicate deliberately reuses M4's browse
filter model, which is why A7/S5 can be a plain 422 rather than a hand-written
allow-list: an unknown or private column never becomes a filter in the first
place.
"""

from __future__ import annotations

MATCHING = {"type": "saas", "max_price": "600000.00"}
NOT_MATCHING = {"type": "ecommerce"}


def _save(client, headers, name="My search", **filters):
    return client.post(
        "/api/saved-searches",
        json={"name": name, "filters": {**MATCHING, **filters}},
        headers=headers,
    )


def _types(rows) -> list[str]:
    return [r["type"] for r in rows]


# ── A — saved-search CRUD ────────────────────────────────────────────────────


def test_a1_create_stores_the_caller_as_owner(client, auth_headers, user_id, session):
    """A1 — a created search belongs to the caller, from the JWT."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    res = _save(client, buyer)

    assert res.status_code == 201
    from sqlalchemy import text

    owner = session.execute(
        text("SELECT user_id FROM savedsearch WHERE id = :i"), {"i": res.json()["id"]}
    ).scalar_one()
    assert owner == user_id(buyer)


def test_a2_list_excludes_another_users_search(client, auth_headers):
    """A2 — B's list never contains A's saved search."""
    buyer_a = auth_headers(email="a@example.com", role="buyer")
    buyer_b = auth_headers(email="b@example.com", role="buyer")
    created = _save(client, buyer_a).json()["id"]

    ids = [r["id"] for r in client.get("/api/saved-searches", headers=buyer_b).json()]
    assert created not in ids


def test_a3_list_returns_the_callers_searches_newest_first(client, auth_headers):
    """A3 — both of the caller's searches come back, newest first."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    _save(client, buyer, name="First")
    _save(client, buyer, name="Second")

    rows = client.get("/api/saved-searches", headers=buyer).json()
    assert [r["name"] for r in rows] == ["Second", "First"]


def test_a4_deleting_another_users_search_is_404(client, auth_headers):
    """A4 — IDOR: B cannot delete A's saved search."""
    buyer_a = auth_headers(email="a@example.com", role="buyer")
    buyer_b = auth_headers(email="b@example.com", role="buyer")
    search_id = _save(client, buyer_a).json()["id"]

    assert client.delete(f"/api/saved-searches/{search_id}", headers=buyer_b).status_code == 404
    assert [r["id"] for r in client.get("/api/saved-searches", headers=buyer_a).json()] == [search_id]


def test_a5_owner_can_delete_their_search(client, auth_headers):
    """A5 — the owner deletes their own search and it disappears."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    search_id = _save(client, buyer).json()["id"]

    assert client.delete(f"/api/saved-searches/{search_id}", headers=buyer).status_code == 204
    assert client.get("/api/saved-searches", headers=buyer).json() == []


def test_a6_user_id_in_the_body_is_ignored(client, auth_headers, user_id, session):
    """A6 — mass-assignment: a client-supplied `user_id` never wins."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    victim = auth_headers(email="victim@example.com", role="buyer")

    res = client.post(
        "/api/saved-searches",
        json={"name": "mine", "filters": MATCHING, "user_id": user_id(victim)},
        headers=buyer,
    )
    from sqlalchemy import text

    owner = session.execute(
        text("SELECT user_id FROM savedsearch WHERE id = :i"), {"i": res.json()["id"]}
    ).scalar_one()
    assert owner == user_id(buyer)


def test_a7_unknown_filter_field_is_422(client, auth_headers, session):
    """A7 — an unrecognized filter name is refused at the boundary."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    res = client.post(
        "/api/saved-searches",
        json={"name": "x", "filters": {"type": "saas", "not_a_filter": "x"}},
        headers=buyer,
    )
    assert res.status_code == 422
    from sqlalchemy import text

    assert session.execute(text("SELECT count(*) FROM savedsearch")).scalar_one() == 0


def test_a8_creating_requires_authentication(client):
    """A8 — saving a search is not a public route."""
    assert client.post("/api/saved-searches", json={"name": "x", "filters": {}}).status_code == 401


def test_a9_saved_search_limit_is_enforced(client, auth_headers):
    """A9 — the per-user cap bounds the fan-out cost of a publication."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    statuses = [_save(client, buyer, name=f"search {i}").status_code for i in range(25)]

    assert 409 in statuses
    first_refusal = statuses.index(409)
    assert all(s == 201 for s in statuses[:first_refusal])
    assert all(s == 409 for s in statuses[first_refusal:])


def test_a10_inverted_price_range_is_422(client, auth_headers):
    """A10 — `min_price` above `max_price` is refused rather than stored dead."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    res = client.post(
        "/api/saved-searches",
        json={"name": "x", "filters": {"min_price": "900000.00", "max_price": "100000.00"}},
        headers=buyer,
    )
    assert res.status_code == 422


# ── B — the publication fan-out ──────────────────────────────────────────────


def test_b1_matching_search_gets_a_listing_matched_notification(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """B1 — a matching saved search is alerted when a listing is published."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    _save(client, buyer)

    live_listing(seller)

    assert "listing_matched" in _types(notification_rows(user_id(buyer)))


def test_b2_non_matching_search_is_not_alerted(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """B2 — a search that does not match produces no notification."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    client.post(
        "/api/saved-searches",
        json={"name": "other", "filters": NOT_MATCHING},
        headers=buyer,
    )

    live_listing(seller)

    assert "listing_matched" not in _types(notification_rows(user_id(buyer)))


def test_b3_each_matching_buyer_gets_exactly_one(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """B3 — the fan-out reaches every matching buyer, once each."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer_a = auth_headers(email="a@example.com", role="buyer")
    buyer_b = auth_headers(email="b@example.com", role="buyer")
    _save(client, buyer_a)
    _save(client, buyer_b)

    live_listing(seller)

    for buyer in (buyer_a, buyer_b):
        matched = [t for t in _types(notification_rows(user_id(buyer))) if t == "listing_matched"]
        assert len(matched) == 1


def test_b4_rejection_does_not_fan_out(
    client, auth_headers, admin_headers, make_listing, notification_rows, user_id
):
    """B4 — only publication alerts; a rejected listing reaches no buyer."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    _save(client, buyer)

    listing_id = make_listing(seller).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=seller)
    client.post(
        f"/api/listings/{listing_id}/reject",
        json={"reason": "not enough detail"},
        headers=admin_headers(),
    )

    assert "listing_matched" not in _types(notification_rows(user_id(buyer)))


def test_b5_owner_is_not_alerted_about_their_own_listing(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """B5 — a seller whose own saved search matches is not alerted about it."""
    seller = auth_headers(email="seller@example.com", role="seller")
    _save(client, seller)

    live_listing(seller)

    assert "listing_matched" not in _types(notification_rows(user_id(seller)))


def test_b6_alert_payload_carries_no_private_fields(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """B6 — the alert names a public listing, never its company or owner."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    _save(client, buyer)

    live_listing(seller)

    rows = str([r for r in notification_rows(user_id(buyer)) if r["type"] == "listing_matched"])
    assert "Acme Internal Tools LLC" not in rows
    assert "acme.example.com" not in rows
    assert "seller@example.com" not in rows


def test_b7_republishing_does_not_alert_twice(
    client, auth_headers, admin_headers, live_listing, notification_rows, user_id
):
    """B7 — an edit → `pending_review` → approve cycle does not re-alert.

    The corridor M3 opened: editing a `live` listing demotes it, so a second
    approval is reachable and would otherwise re-run the whole fan-out.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    _save(client, buyer)
    listing_id = live_listing(seller)

    client.put(
        f"/api/listings/{listing_id}",
        json={"headline": "Profitable B2B scheduling SaaS (updated)"},
        headers=seller,
    )
    client.post(f"/api/listings/{listing_id}/submit", headers=seller)
    client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())

    matched = [t for t in _types(notification_rows(user_id(buyer))) if t == "listing_matched"]
    assert len(matched) == 1


def test_b8_alerts_are_forward_only(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """B8 — spec D7: a new search does not backfill listings already live."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    live_listing(seller)
    _save(client, buyer)

    assert "listing_matched" not in _types(notification_rows(user_id(buyer)))
