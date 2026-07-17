"""M1 — Roles & profile (spec 001 acceptance criteria E1–E3)."""


def test_e1_buyer_can_add_seller_role(client, auth_headers):
    """FR-2: a user may hold both roles under one account."""
    headers = auth_headers(role="buyer")
    r = client.post("/api/auth/roles", json={"role": "seller"}, headers=headers)
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["is_buyer"] is True and me["is_seller"] is True


def test_e2_profile_update_persists_on_own_record(client, auth_headers):
    headers = auth_headers()
    r = client.put(
        "/api/profile",
        json={
            "display_name": "Alice",
            "budget": "500000",
            "target_industries": "SaaS, e-commerce",
            "experience": "2 prior acquisitions",
        },
        headers=headers,
    )
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["display_name"] == "Alice"
    assert me["target_industries"] == "SaaS, e-commerce"


def test_e3_cannot_update_another_users_profile(client, auth_headers):
    """IDOR: the server derives the target from the JWT; a client-supplied id is ignored."""
    a = auth_headers(email="alice@example.com")
    auth_headers(email="bob@example.com")           # a second real user exists
    # Alice tries to target Bob by id in the body — must not touch Bob.
    r = client.put(
        "/api/profile",
        json={"user_id": 999, "display_name": "hacked"},
        headers=a,
    )
    # Either the field is ignored (200, applied to Alice) or rejected — never applied to Bob.
    bob = client.get("/api/auth/me", headers=auth_headers(email="bob@example.com"))
    assert bob.json()["display_name"] != "hacked"
    assert r.status_code in (200, 403, 404, 422)
