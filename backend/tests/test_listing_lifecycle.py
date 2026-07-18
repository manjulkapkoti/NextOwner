"""M2 — Listing lifecycle state machine (spec 002 acceptance criteria C1–C8)."""


def test_c1_submit_draft_goes_to_pending_review(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = client.post(f"/api/listings/{listing_id}/submit", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"


def test_c2_submitting_a_non_draft_is_409(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=h)      # now pending_review
    r = client.post(f"/api/listings/{listing_id}/submit", headers=h)  # again
    assert r.status_code == 409
    assert r.json()["code"] == "invalid_transition"


def test_c3_submitting_another_users_listing_is_404(client, auth_headers, make_listing):
    listing_id = make_listing(auth_headers(email="owner@example.com")).json()["id"]
    r = client.post(f"/api/listings/{listing_id}/submit", headers=auth_headers(email="other@example.com"))
    assert r.status_code == 404


def test_c4_pause_a_live_listing(client, auth_headers, make_listing, force_status):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    force_status(listing_id, "live")
    r = client.post(f"/api/listings/{listing_id}/pause", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "paused"


def test_c5_resume_a_paused_listing(client, auth_headers, make_listing, force_status):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    force_status(listing_id, "paused")
    r = client.post(f"/api/listings/{listing_id}/resume", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "live"          # no re-review — pausing isn't a content change


def test_c6_pausing_a_draft_is_409(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = client.post(f"/api/listings/{listing_id}/pause", headers=h)   # a draft isn't live
    assert r.status_code == 409


def test_c7_seller_has_no_path_to_set_live_directly(client, auth_headers, make_listing):
    """Submit only reaches pending_review; publication is admin-only (M3)."""
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=h)
    got = client.get(f"/api/listings/{listing_id}", headers=h).json()
    assert got["status"] == "pending_review"     # never "live"


def test_c8_close_a_listing(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = client.post(f"/api/listings/{listing_id}/close", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
