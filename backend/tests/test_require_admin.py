"""M1 — require_admin, trust boundary #2 (spec 001 acceptance criteria D1–D3)."""

from sqlalchemy import text


def _make_admin(session, email):
    session.execute(text('UPDATE "user" SET is_admin = 1 WHERE email = :e'), {"e": email})
    session.commit()


def test_d1_non_admin_on_admin_route_is_403(client, auth_headers):
    r = client.get("/api/admin/ping", headers=auth_headers())
    assert r.status_code == 403


def test_d2_admin_flag_is_reread_from_db_after_token_issued(client, session, auth_headers):
    """Token issued while non-admin; DB promoted after. is_admin is re-read per request."""
    headers = auth_headers()                       # token minted as a non-admin
    _make_admin(session, "alice@example.com")       # promoted in the DB afterwards
    r = client.get("/api/admin/ping", headers=headers)
    assert r.status_code == 200                     # not read from the (stale) token


def test_d3_is_admin_mass_assignment_on_register_is_ignored(client, session):
    client.post(
        "/api/auth/register",
        json={
            "email": "mallory@example.com",
            "password": "correct horse battery staple",
            "role": "buyer",
            "is_admin": True,          # attacker tries to self-escalate
        },
    )
    row = session.execute(
        text('SELECT is_admin FROM "user" WHERE email = :e'), {"e": "mallory@example.com"}
    ).first()
    assert row is not None
    assert not row[0]                  # the flag was ignored
