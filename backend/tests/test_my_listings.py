"""M2 — The seller dashboard (spec 002 acceptance criteria F1–F2)."""


def test_f1_my_listings_returns_only_callers_listings_including_drafts(client, auth_headers, make_listing):
    h = auth_headers()
    make_listing(h, headline="First")
    make_listing(h, headline="Second")
    r = client.get("/api/my/listings", headers=h)
    assert r.status_code == 200
    headlines = {row["headline"] for row in r.json()}
    assert {"First", "Second"} <= headlines          # drafts included


def test_f2_my_listings_never_shows_another_users_listings(client, auth_headers, make_listing):
    make_listing(auth_headers(email="owner@example.com"), headline="Owner's private draft")
    other = client.get("/api/my/listings", headers=auth_headers(email="other@example.com"))
    assert other.status_code == 200
    headlines = {row["headline"] for row in other.json()}
    assert "Owner's private draft" not in headlines
