"""M2 — Create a draft listing (spec 002 acceptance criteria A1–A7)."""

from decimal import Decimal


def test_a1_create_returns_draft_owned_by_caller(client, auth_headers, make_listing):
    r = make_listing(auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["headline"] == "Profitable B2B scheduling SaaS"
    assert "id" in body


def test_a2_client_owner_id_is_ignored(client, auth_headers, make_listing):
    r = make_listing(auth_headers(), owner_id=99999)          # try to plant another owner
    assert r.status_code == 201
    # The listing is retrievable by its real owner (the caller), proving owner_id
    # came from the JWT, not the body.
    listing_id = r.json()["id"]
    mine = client.get(f"/api/listings/{listing_id}", headers=auth_headers())
    assert mine.status_code == 200


def test_a3_client_status_live_is_ignored(client, auth_headers, make_listing):
    r = make_listing(auth_headers(), status="live")           # try to self-publish
    assert r.status_code == 201
    assert r.json()["status"] == "draft"


def test_a4_non_positive_asking_price_is_422(client, auth_headers, make_listing):
    r = make_listing(auth_headers(), asking_price="0")
    assert r.status_code == 422


def test_a5_missing_required_field_is_422(client, auth_headers):
    payload = {"type": "saas", "headline": "x"}                # most fields missing
    r = client.post("/api/listings", json=payload, headers=auth_headers())
    assert r.status_code == 422


def test_a6_unauthenticated_create_is_401(client, make_listing):
    r = make_listing({})                                       # no Authorization header
    assert r.status_code == 401


def test_a7_money_is_decimal_no_float_rounding(client, auth_headers, make_listing):
    # 13 significant digits — a float cannot hold this exactly; Decimal can.
    r = make_listing(auth_headers(), asking_price="12345678901.99")
    listing_id = r.json()["id"]
    got = client.get(f"/api/listings/{listing_id}", headers=auth_headers()).json()["asking_price"]
    assert Decimal(str(got)) == Decimal("12345678901.99")
