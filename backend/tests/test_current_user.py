"""M1 — get_current_user, trust boundary #1 (spec 001 acceptance criteria C1–C5).

These are crown-jewel token-attack tests: missing, expired, tampered, alg:none,
and a token for a since-anonymized user.
"""

import datetime

import jwt
from sqlalchemy import text
from tests.conftest import TEST_JWT_SECRET, TEST_JWT_ALG


def test_c1_no_token_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_c2_expired_token_is_401(client, register):
    register()
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    token = jwt.encode({"sub": "1", "exp": past}, TEST_JWT_SECRET, algorithm=TEST_JWT_ALG)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["code"] == "token_expired"


def test_c3_tampered_signature_is_401(client, register):
    register()
    # Signed with the WRONG key → signature verification must fail.
    forged = jwt.encode({"sub": "1"}, "attacker-key", algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_c4_alg_none_token_is_401(client, register):
    """Algorithm-confusion: an unsigned alg:none token must be rejected — alg is pinned."""
    register()
    unsigned = jwt.encode({"sub": "1"}, "", algorithm="none")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"})
    assert r.status_code == 401


def test_c5_token_for_anonymized_user_is_401(client, session, auth_headers):
    """Identity is re-read from the DB, not trusted from the token."""
    headers = auth_headers()
    # Soft-delete / anonymize the user out of band (a future erasure flow would do this).
    session.execute(
        text('UPDATE "user" SET deleted_at = :t WHERE email = :e'),
        {"t": datetime.datetime.now(datetime.timezone.utc).isoformat(), "e": "alice@example.com"},
    )
    session.commit()
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401
