"""M1 — Registration (spec 001 acceptance criteria A1–A6).

Written failing-first (SDD). DB inspection uses raw SQL so these tests don't
depend on importing the model class before it exists.
"""

from sqlalchemy import text

VALID = {"email": "alice@example.com", "password": "correct horse battery staple", "role": "buyer"}


def _password_hash(session, email):
    row = session.execute(
        text('SELECT password_hash FROM "user" WHERE email = :e'), {"e": email}
    ).first()
    return row[0] if row else None


def test_a1_register_creates_user_with_role(client):
    r = client.post("/api/auth/register", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    # role landed as the buyer flag (FR-2: two role booleans, not an enum)
    assert body.get("is_buyer") is True
    assert body.get("is_seller") is False


def test_a2_password_stored_as_bcrypt_hash_not_plaintext(client, session):
    client.post("/api/auth/register", json=VALID)
    stored = _password_hash(session, "alice@example.com")
    assert stored is not None
    assert stored != VALID["password"]            # never plaintext
    assert stored.startswith("$2b$") or stored.startswith("$2a$")  # bcrypt


def test_a3_registration_stamps_tos_accepted_at_and_version(client, session):
    client.post("/api/auth/register", json=VALID)
    row = session.execute(
        text('SELECT tos_accepted_at, tos_version FROM "user" WHERE email = :e'),
        {"e": "alice@example.com"},
    ).first()
    assert row is not None
    assert row[0] is not None        # tos_accepted_at stamped server-side
    assert row[1]                    # tos_version recorded (which text was accepted)


def test_a4_duplicate_email_conflicts(client):
    client.post("/api/auth/register", json=VALID)
    r = client.post("/api/auth/register", json=VALID)
    assert r.status_code == 409
    assert r.json()["code"] == "email_taken"


def test_a5_invalid_role_is_422(client):
    r = client.post("/api/auth/register", json={**VALID, "role": "wizard"})
    assert r.status_code == 422


def test_a6_invalid_email_is_422_on_the_email_field(client):
    r = client.post("/api/auth/register", json={**VALID, "email": "not-an-email"})
    assert r.status_code == 422
    locs = [".".join(str(p) for p in e["loc"]) for e in r.json()["detail"]]
    assert any("email" in loc for loc in locs)
