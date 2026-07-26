"""M9 — the watchlist core (spec 009): W — add / remove / list (FR-12, F10).

Written failing first: the `watchlistentry` table and the three routes
(`POST /api/watchlist/{listing_id}`, `GET /api/watchlist`,
`DELETE /api/watchlist/{listing_id}`) do not exist yet, so every test here
calls a route that 404s.

The forbidden-path half — cross-user scoping, the non-`live` and
never-watchlisted 404s, the schema-leak assertion, the 401s and the 422/500
contract — lives in `test_watchlist_security.py`. This file is the happy path
plus the two behaviours that are easy to get subtly wrong: D1's idempotent add
(a repeat `POST` is 200 and must not create a second row) and D3's
filtered-to-`live` list (a listing that leaves `live` is *omitted*, not
deleted — W7 and W8 are one story split across two criteria).
"""

from __future__ import annotations


def _add(client, headers, listing_id):
    """Favorite a listing — the route takes no body (spec 009 S4)."""
    return client.post(f"/api/watchlist/{listing_id}", headers=headers)


def _watchlist(client, headers):
    """The caller's own watchlist. Asserts the 200 so a failing list route
    surfaces as a status assertion rather than a `TypeError` on the error body."""
    res = client.get("/api/watchlist", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _ids(rows) -> list[int]:
    return [r["listing_id"] for r in rows]


# ── W — watchlist core (add / remove / list) ─────────────────────────────────


def test_w1_adding_a_live_listing_returns_201_and_appears_in_the_watchlist(
    client, auth_headers, live_listing
):
    """W1 — the add path: 201, and the listing is on the caller's watchlist."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)

    res = _add(client, buyer, listing_id)

    assert res.status_code == 201
    assert listing_id in _ids(_watchlist(client, buyer))


def test_w2_removing_an_entry_returns_204_and_it_disappears(
    client, auth_headers, live_listing
):
    """W2 — the remove path: 204, and the listing is gone from the list."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    _add(client, buyer, listing_id)

    res = client.delete(f"/api/watchlist/{listing_id}", headers=buyer)

    assert res.status_code == 204
    assert listing_id not in _ids(_watchlist(client, buyer))


def test_w3_list_returns_every_entry_newest_added_first(
    client, auth_headers, live_listing
):
    """W3 — all of the caller's `live` entries, ordered newest-added-first."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    first = live_listing(seller, headline="First listing on the watchlist")
    second = live_listing(seller, headline="Second listing on the watchlist")
    third = live_listing(seller, headline="Third listing on the watchlist")

    for listing_id in (first, second, third):        # deliberate add order
        _add(client, buyer, listing_id)

    rows = _watchlist(client, buyer)
    assert _ids(rows) == [third, second, first]
    assert [r["headline"] for r in rows] == [
        "Third listing on the watchlist",
        "Second listing on the watchlist",
        "First listing on the watchlist",
    ]


def test_w4_adding_twice_is_idempotent_and_creates_no_duplicate(
    client, auth_headers, live_listing
):
    """W4 — D1: a repeat add is 200 (not 201) and leaves exactly one entry.

    The count is the assertion that matters — a second row would satisfy mere
    presence while breaking the toggle a double-clicked heart icon produces.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)

    assert _add(client, buyer, listing_id).status_code == 201
    assert _add(client, buyer, listing_id).status_code == 200

    rows = _watchlist(client, buyer)
    assert len([r for r in rows if r["listing_id"] == listing_id]) == 1


def test_w7_a_paused_listing_drops_out_of_the_watchlist(
    client, auth_headers, live_listing
):
    """W7 — D3: leaving `live` silently removes it from the *view*.

    That the underlying row survives is W8's assertion, not this one.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    _add(client, buyer, listing_id)

    client.post(f"/api/listings/{listing_id}/pause", headers=seller)

    assert listing_id not in _ids(_watchlist(client, buyer))


def test_w8_a_resumed_listing_reappears_without_being_re_added(
    client, auth_headers, live_listing
):
    """W8 — D3's other half: the row was never deleted, only filtered out.

    No second `POST /api/watchlist/{id}` happens between pause and resume —
    that absence is the whole point of the test.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    _add(client, buyer, listing_id)

    client.post(f"/api/listings/{listing_id}/pause", headers=seller)
    assert listing_id not in _ids(_watchlist(client, buyer))

    client.post(f"/api/listings/{listing_id}/resume", headers=seller)

    assert listing_id in _ids(_watchlist(client, buyer))


def test_w12_a_seller_may_watchlist_another_sellers_listing(
    client, auth_headers, live_listing
):
    """W12 — D4: no role gate; a competitor's `live` listing is watchlistable."""
    seller_a = auth_headers(email="seller-a@example.com", role="seller")
    seller_b = auth_headers(email="seller-b@example.com", role="seller")
    listing_id = live_listing(seller_a)

    res = _add(client, seller_b, listing_id)

    assert res.status_code == 201
    assert listing_id in _ids(_watchlist(client, seller_b))
