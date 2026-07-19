"""M4 — the owner's listing view at its new path (spec 004: D1-D3, H1).

Spec decision D1 moved the owner's full view from `GET /api/listings/{id}` to
`GET /api/my/listings/{id}`, so the public browse could take the canonical path.
The move keeps M2's semantics exactly — 404 (never 403) for someone else's
listing, so a draft's existence is never confirmed.

H1 is the guard that makes this a *rename* rather than a quiet loss of
coverage: it asserts the old path no longer serves private fields.
"""


def test_d1_the_owner_sees_their_full_listing_at_the_new_path(
    client, auth_headers, make_listing, force_status
):
    seller = auth_headers(email="owner@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]

    for status in ("draft", "pending_review", "rejected", "paused"):
        force_status(listing_id, status)
        body = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
        assert body["company_name"] == "Acme Internal Tools LLC"
        assert body["owner_id"] and body["status"] == status


def test_d2_someone_elses_listing_is_404_not_403(client, auth_headers, make_listing):
    owner = auth_headers(email="owner@example.com", role="seller")
    listing_id = make_listing(owner).json()["id"]
    attacker = auth_headers(email="attacker@example.com", role="buyer")

    # The route must exist and serve its owner, or the 404 below proves nothing:
    # a missing route 404s for everybody, which would make this test green
    # forever without ever checking ownership.
    assert client.get(f"/api/my/listings/{listing_id}", headers=owner).status_code == 200

    res = client.get(f"/api/my/listings/{listing_id}", headers=attacker)
    assert res.status_code == 404, "403 would confirm the listing exists"


def test_d3_the_owner_route_requires_a_token(client, auth_headers, make_listing):
    owner = auth_headers(email="owner@example.com", role="seller")
    listing_id = make_listing(owner).json()["id"]
    assert client.get(f"/api/my/listings/{listing_id}").status_code == 401


def test_h1_the_old_path_no_longer_serves_private_fields_to_the_owner(
    client, auth_headers, make_listing
):
    """The D1 move, asserted as a removal rather than assumed.

    Six M2/M3 tests were re-pointed to the new path with their assertions
    unchanged. That is only a rename if the old path's private-field behavior is
    actually gone — which is what this asserts.
    """
    seller = auth_headers(email="owner@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]        # a draft

    res = client.get(f"/api/listings/{listing_id}", headers=seller)
    assert res.status_code == 404                          # public route, non-live (C2)
    assert "company_name" not in res.text
