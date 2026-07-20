"""M5 — Signing the platform NDA + requesting per-listing access
(spec 005 acceptance criteria A1-A4, B1-B7).

A is the one-time platform NDA (`POST /api/auth/nda`) — signed once, timestamped
on the account (FR-13), and idempotent (spec D4: the first signature is the
legal record; a second click never re-stamps it, and `nda_version` is frozen at
signature from server config, never the client).

B is the per-listing access request (`POST /api/listings/{id}/access-request`)
— the row `require_private_access` later decides against. The gate itself
(`GET /api/listings/{id}/private`) is covered in test_nda_gate.py; this file
only covers the row's creation and its own trust boundary
(`require_signed_nda`, ownership, existence).
"""

from sqlalchemy import text

# ── A — signing the platform NDA ─────────────────────────────────────────────

def test_a1_signing_stamps_timestamp_and_server_version(client, auth_headers):
    headers = auth_headers()
    r = client.post("/api/auth/nda", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["nda_signed_at"] is not None

    from app.config import settings
    assert body["nda_version"] == settings.nda_version


def test_a2_signing_twice_is_idempotent(client, auth_headers):
    """D4: the first signature is the legal record — a second click must not
    re-stamp the timestamp or move the version."""
    headers = auth_headers()
    first = client.post("/api/auth/nda", headers=headers)
    second = client.post("/api/auth/nda", headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["nda_signed_at"] == first.json()["nda_signed_at"]
    assert second.json()["nda_version"] == first.json()["nda_version"]


def test_a3_signing_without_credentials_is_401(client):
    assert client.post("/api/auth/nda").status_code == 401


def test_a4_client_supplied_timestamp_and_version_are_ignored(client, auth_headers):
    """Article 2 #4 — mass assignment. The server derives both from its own
    clock and its own config, never from the request body."""
    headers = auth_headers()
    r = client.post(
        "/api/auth/nda",
        json={"nda_signed_at": "2000-01-01T00:00:00", "nda_version": "not-a-real-version"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["nda_signed_at"] != "2000-01-01T00:00:00"
    assert body["nda_version"] != "not-a-real-version"

    from app.config import settings
    assert body["nda_version"] == settings.nda_version


# ── B — requesting access to a listing ───────────────────────────────────────

def test_b1_creates_a_requested_row_owned_by_the_caller(
    client, auth_headers, live_listing, sign_nda, session
):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    sign_nda(buyer)

    r = client.post(f"/api/listings/{listing_id}/access-request", headers=buyer)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "requested"
    assert body.get("created_at") is not None

    buyer_id = session.execute(
        text('SELECT id FROM "user" WHERE email = :e'), {"e": "buyer@example.com"}
    ).scalar()
    row = session.execute(
        text("SELECT buyer_id, listing_id, status FROM accessrequest WHERE id = :i"),
        {"i": body["id"]},
    ).fetchone()
    assert row is not None
    assert row[0] == buyer_id
    assert row[1] == listing_id
    assert row[2] == "requested"


def test_b2_unsigned_buyer_is_403_nda_not_signed(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    buyer = auth_headers(email="buyer@example.com", role="buyer")   # never signs

    r = client.post(f"/api/listings/{listing_id}/access-request", headers=buyer)
    assert r.status_code == 403
    assert r.json()["code"] == "nda_not_signed"


def test_b3_duplicate_request_is_409(client, auth_headers, live_listing, request_access):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    assert request_access(listing_id, buyer).status_code == 201
    dup = request_access(listing_id, buyer, sign=False)   # already signed above
    assert dup.status_code == 409


def test_b4_mass_assignment_on_create_is_ignored(
    client, auth_headers, live_listing, sign_nda, session
):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    auth_headers(email="other@example.com", role="buyer")     # a second real user exists
    other_id = session.execute(
        text('SELECT id FROM "user" WHERE email = :e'), {"e": "other@example.com"}
    ).scalar()
    sign_nda(buyer)

    r = client.post(
        f"/api/listings/{listing_id}/access-request",
        json={"status": "approved", "buyer_id": other_id, "decided_at": "2020-01-01T00:00:00"},
        headers=buyer,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "requested"

    row = session.execute(
        text("SELECT buyer_id, decided_at FROM accessrequest WHERE id = :i"), {"i": body["id"]}
    ).fetchone()
    assert row[0] != other_id
    assert row[1] is None


def test_b5_owner_requesting_their_own_listing_is_403(
    client, auth_headers, live_listing, sign_nda
):
    """Self-dealing: the owner already has access, and a self-request would be
    a self-approval path (security.md §6)."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    sign_nda(seller)

    r = client.post(f"/api/listings/{listing_id}/access-request", headers=seller)
    assert r.status_code == 403


def test_b6_never_published_listing_is_404(
    client, auth_headers, make_listing, live_listing, sign_nda
):
    """Spec D1: a listing that has never been published is still a secret — a
    non-owner gets 404, identical to a listing that doesn't exist.

    Confirms the route actually works against a live listing first — a route
    that doesn't exist yet also 404s on the draft, which would pass this test
    for the wrong reason (mirrors test_my_listing_detail.py's D2)."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    sign_nda(buyer)

    live_id = live_listing(seller)
    assert client.post(f"/api/listings/{live_id}/access-request", headers=buyer).status_code == 201

    draft_id = make_listing(seller).json()["id"]     # never submitted/approved
    r = client.post(f"/api/listings/{draft_id}/access-request", headers=buyer)
    assert r.status_code == 404


def test_b7_unauthenticated_is_401(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)

    r = client.post(f"/api/listings/{listing_id}/access-request")
    assert r.status_code == 401
