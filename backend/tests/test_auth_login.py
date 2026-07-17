"""M1 — Login & tokens (spec 001 acceptance criteria B1–B4)."""

import jwt

from tests.conftest import TEST_JWT_ALG, TEST_JWT_SECRET, VALID_PW


def test_b1_login_returns_jwt_with_user_id_subject(client, register):
    register()
    r = client.post("/api/auth/login", data={"username": "alice@example.com", "password": VALID_PW})
    assert r.status_code == 200
    token = r.json()["access_token"]
    claims = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALG])
    assert str(claims["sub"])  # subject is the user's id


def test_b2_wrong_password_is_401(client, register):
    register()
    r = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_b3_unknown_email_is_401_identical_to_wrong_password(client, register):
    """No user enumeration: unknown email and wrong password must be byte-identical."""
    register()
    wrong_pw = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "wrong"})
    unknown = client.post("/api/auth/login", data={"username": "nobody@example.com", "password": "wrong"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()          # same body — no "user not found" tell


def test_b4_me_returns_own_record_without_password_hash(client, auth_headers):
    r = client.get("/api/auth/me", headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert "password_hash" not in body                # never leaked, by schema
