"""M2 — Edit a listing (spec 002 acceptance criteria B1–B4)."""


def test_b1_owner_edits_own_draft(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = client.put(f"/api/listings/{listing_id}", json={"headline": "Updated headline"}, headers=h)
    assert r.status_code == 200
    assert r.json()["headline"] == "Updated headline"


def test_b2_editing_another_users_listing_is_404(client, auth_headers, make_listing):
    owner = auth_headers(email="owner@example.com")
    listing_id = make_listing(owner).json()["id"]
    attacker = auth_headers(email="attacker@example.com")
    r = client.put(f"/api/listings/{listing_id}", json={"headline": "hijacked"}, headers=attacker)
    assert r.status_code == 404          # owner-scoped: no existence leak


def test_b3_editing_a_live_listing_returns_it_to_pending_review(client, auth_headers, make_listing, force_status):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    force_status(listing_id, "live")     # seed a live listing (admin does this at M3)
    r = client.put(f"/api/listings/{listing_id}", json={"headline": "Changed after going live"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"   # no bait-and-switch behind curation


def test_b4_owner_id_and_status_ignored_on_edit(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = client.put(
        f"/api/listings/{listing_id}",
        json={"owner_id": 99999, "status": "live", "headline": "ok"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"            # status not client-settable
