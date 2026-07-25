"""M8 — email verification (spec 008): H.

Written failing first: `emailverificationtoken`, `User.email_verified_at`, and
the verify/resend routes do not exist yet.

**Spec D4 is what H5/H6 exist to pin.** Reset tokens and verification tokens
live in two separate tables precisely so a token minted for one purpose cannot
be redeemed for the other — the classic cross-purpose confusion that a single
table with a `purpose` column makes a discipline problem instead of a
structural one. The codebase already prefers duplication over sharing when a
boundary is at stake (`conversation_role_for` duplicates the NDA-gate query so
M6 cannot regress M5); this is the same trade, and the tests below are the
proof that the structure actually holds.
"""

from __future__ import annotations

from tests.conftest import VALID_PW, reset_token_from, verification_token_from


def _register_and_login(client, register, login, email="alice@example.com"):
    register(email=email)
    token = login(email=email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_h1_a_new_user_starts_unverified(client, register, login):
    """H1 — registration does not confer verification."""
    headers = _register_and_login(client, register, login)

    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is False


def test_h2_a_valid_token_verifies_the_address(client, register, login, outbox):
    """H2 — the happy path flips `email_verified`."""
    headers = _register_and_login(client, register, login)
    token = verification_token_from(outbox.to("alice@example.com")[-1])

    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is True


def test_h3_a_verification_token_is_single_use(client, register, login, outbox):
    """H3 — the second redemption is refused."""
    _register_and_login(client, register, login)
    token = verification_token_from(outbox.to("alice@example.com")[-1])
    client.post("/api/auth/verify-email", json={"token": token})

    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


def test_h4_an_expired_verification_token_is_refused(
    client, register, login, outbox, token_rows, expire_token
):
    """H4 — expiry applies to verification tokens too."""
    headers = _register_and_login(client, register, login)
    token = verification_token_from(outbox.to("alice@example.com")[-1])
    expire_token("emailverificationtoken", token_rows("emailverificationtoken")[-1]["id"])

    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is False


def test_h5_a_reset_token_cannot_verify_an_email(client, register, login, outbox):
    """H5 — spec D4: no cross-purpose redemption, reset → verify."""
    headers = _register_and_login(client, register, login)
    client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    reset = reset_token_from(outbox.to("alice@example.com")[-1])

    assert client.post("/api/auth/verify-email", json={"token": reset}).status_code == 400
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is False


def test_h6_a_verification_token_cannot_reset_a_password(
    client, register, login, outbox
):
    """H6 — spec D4: no cross-purpose redemption, verify → reset."""
    _register_and_login(client, register, login)
    verification = verification_token_from(outbox.to("alice@example.com")[-1])

    res = client.post(
        "/api/auth/reset-password",
        json={"token": verification, "password": "an entirely new password value"},
    )

    assert res.status_code == 400
    assert login(email="alice@example.com", password=VALID_PW).status_code == 200


def test_h7_resend_issues_a_new_token_and_kills_the_old(client, register, login, outbox):
    """H7 — resending invalidates the previous token rather than accumulating."""
    headers = _register_and_login(client, register, login)
    first = verification_token_from(outbox.to("alice@example.com")[-1])

    assert client.post("/api/auth/resend-verification", headers=headers).status_code == 202
    second = verification_token_from(outbox.to("alice@example.com")[-1])

    assert second != first
    assert client.post("/api/auth/verify-email", json={"token": first}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": second}).status_code == 200


def test_h8_email_verified_cannot_be_set_through_the_profile(client, register, login):
    """H8 — mass-assignment: a client cannot verify itself."""
    headers = _register_and_login(client, register, login)

    client.put(
        "/api/profile",
        json={"display_name": "Alice", "email_verified": True},
        headers=headers,
    )

    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is False


def test_h9_resending_when_already_verified_is_409(client, register, login, outbox):
    """H9 — no pointless mail once the address is confirmed."""
    headers = _register_and_login(client, register, login)
    token = verification_token_from(outbox.to("alice@example.com")[-1])
    client.post("/api/auth/verify-email", json={"token": token})
    outbox.sent.clear()

    assert client.post("/api/auth/resend-verification", headers=headers).status_code == 409
    assert outbox.sent == []
