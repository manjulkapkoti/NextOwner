"""M8 — password reset (spec 008): G. **The milestone's security core.**

Written failing first: `tokens.py`, the `passwordresettoken` table, and both
`/api/auth/forgot-password` and `/api/auth/reset-password` do not exist yet.

`security.md` §7 M8 states the rules this file exists to enforce: a reset token
is **account takeover if it leaks**, so it must be high-entropy, single-use,
short-lived, hashed at rest, invalidated when the password changes, delivered
without ever appearing in a log or a URL a proxy records — and requesting one
must reveal nothing about whether the address exists (M1's login rule, applied
to a second endpoint).
"""

from __future__ import annotations

import logging

from tests.conftest import VALID_PW, reset_token_from

NEW_PW = "a different correct horse battery staple"


def _forgot(client, email="alice@example.com"):
    return client.post("/api/auth/forgot-password", json={"email": email})


def _reset(client, token, password=NEW_PW):
    return client.post(
        "/api/auth/reset-password", json={"token": token, "password": password}
    )


def test_g1_known_address_gets_a_reset_email(client, register, outbox):
    """G1 — a registered user receives a reset mail and a 202."""
    register(email="alice@example.com")
    outbox.sent.clear()

    res = _forgot(client)

    assert res.status_code == 202
    assert len(outbox.to("alice@example.com")) == 1


def test_g2_unknown_address_is_indistinguishable(client, register, outbox):
    """G2 — no user enumeration: same status, same body, and no mail sent.

    The `== 202` assertion is load-bearing, not decoration. Equality alone
    passes **vacuously** before the route exists, because two 404s are also
    identical — the exact failure mode M5 caught twice (`progress.md`: "a test
    that passes before implementation is unverified"). Pinning the status the
    unmounted route cannot produce is what makes this test fail first.
    """
    register(email="alice@example.com")
    outbox.sent.clear()

    known = _forgot(client, "alice@example.com")
    outbox.sent.clear()
    unknown = _forgot(client, "nobody@example.com")

    assert known.status_code == 202
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert outbox.sent == []


def test_g3_valid_token_sets_the_new_password(client, register, login, outbox):
    """G3 — the happy path: redeem, then log in with the new password."""
    register(email="alice@example.com")
    _forgot(client)
    token = reset_token_from(outbox.to("alice@example.com")[-1])

    assert _reset(client, token).status_code == 200
    assert login(email="alice@example.com", password=NEW_PW).status_code == 200


def test_g4_a_token_cannot_be_redeemed_twice(client, register, login, outbox):
    """G4 — single-use: the second redemption is refused."""
    register(email="alice@example.com")
    _forgot(client)
    token = reset_token_from(outbox.to("alice@example.com")[-1])
    _reset(client, token)

    second = _reset(client, token, "yet another password entirely")

    assert second.status_code == 400
    assert login(email="alice@example.com", password=NEW_PW).status_code == 200


def test_g5_an_expired_token_is_refused(
    client, register, login, outbox, token_rows, expire_token
):
    """G5 — short expiry is enforced, and the password is untouched."""
    register(email="alice@example.com")
    _forgot(client)
    token = reset_token_from(outbox.to("alice@example.com")[-1])
    expire_token("passwordresettoken", token_rows("passwordresettoken")[-1]["id"])

    assert _reset(client, token).status_code == 400
    assert login(email="alice@example.com", password=VALID_PW).status_code == 200


def test_g6_a_token_cannot_reset_a_different_user(client, register, login, outbox):
    """G6 — the token alone names its user; naming another address changes nothing."""
    register(email="alice@example.com")
    register(email="bob@example.com")
    _forgot(client, "alice@example.com")
    alice_token = reset_token_from(outbox.to("alice@example.com")[-1])

    client.post(
        "/api/auth/reset-password",
        json={"token": alice_token, "password": NEW_PW, "email": "bob@example.com"},
    )

    assert login(email="bob@example.com", password=VALID_PW).status_code == 200
    assert login(email="bob@example.com", password=NEW_PW).status_code == 401


def test_g7_the_raw_token_is_not_stored(client, register, outbox, token_rows):
    """G7 — spec D5: the row holds a hash; a leaked DB yields no usable token."""
    register(email="alice@example.com")
    _forgot(client)
    token = reset_token_from(outbox.to("alice@example.com")[-1])

    rows = token_rows("passwordresettoken")
    assert rows
    assert all(row["token_hash"] != token for row in rows)
    assert token not in str(rows)


def test_g8_redeeming_one_token_invalidates_the_others(client, register, outbox):
    """G8 — a password change invalidates every outstanding token for that user."""
    register(email="alice@example.com")
    _forgot(client)
    first = reset_token_from(outbox.to("alice@example.com")[-1])
    _forgot(client)
    second = reset_token_from(outbox.to("alice@example.com")[-1])

    assert _reset(client, second).status_code == 200
    assert _reset(client, first, "a third distinct password value").status_code == 400


def test_g9_forgot_password_is_rate_limited(client, register):
    """G9 — it mails a third party on demand, so volume is bounded."""
    register(email="alice@example.com")

    statuses = [_forgot(client).status_code for _ in range(12)]

    assert 429 in statuses


def test_g10_the_raw_token_never_reaches_the_logs(client, register, outbox, caplog):
    """G10 — `security.md` §7 M8: never log the token."""
    register(email="alice@example.com")
    with caplog.at_level(logging.DEBUG):
        _forgot(client)
        token = reset_token_from(outbox.to("alice@example.com")[-1])
        _reset(client, token)

    assert token not in caplog.text


def test_g11_a_too_short_password_is_422(client, register, login, outbox):
    """G11 — the new password obeys the same minimum as registration."""
    register(email="alice@example.com")
    _forgot(client)
    token = reset_token_from(outbox.to("alice@example.com")[-1])

    assert _reset(client, token, "short").status_code == 422
    assert login(email="alice@example.com", password=VALID_PW).status_code == 200


def test_g12_nonexistent_and_expired_tokens_answer_identically(
    client, register, outbox, token_rows, expire_token
):
    """G12 — no oracle for which tokens exist."""
    register(email="alice@example.com")
    _forgot(client)
    real = reset_token_from(outbox.to("alice@example.com")[-1])
    expire_token("passwordresettoken", token_rows("passwordresettoken")[-1]["id"])

    expired = _reset(client, real)
    invented = _reset(client, "Zm9vYmFyYmF6cXV1eGNvcmdlZ3JhdWx0Z2FybHlfMDEyMzQ1Ng")

    assert (expired.status_code, expired.json()) == (invented.status_code, invented.json())


def test_g13_a_soft_deleted_user_gets_no_token(client, register, session, outbox):
    """G13 — an anonymized account is not a reset target, and still answers 202."""
    from sqlalchemy import text

    register(email="alice@example.com")
    session.execute(
        text('UPDATE "user" SET deleted_at = :t WHERE email = :e'),
        {"t": "2026-01-01 00:00:00", "e": "alice@example.com"},
    )
    session.commit()
    outbox.sent.clear()

    res = _forgot(client)

    assert res.status_code == 202
    assert outbox.sent == []
    assert session.execute(text("SELECT count(*) FROM passwordresettoken")).scalar_one() == 0
