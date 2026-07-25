"""M8 — the email channel (spec 008): F.

Written failing first: `app/mailer.py`, the `email_verified` gate on
notification mail, and the failure isolation around a dead transport do not
exist yet.

The channel is a **port** (spec D9), shaped like `ratelimit.py`'s
`RateLimiterBackend` and `chat_broker.py`'s `ChatBroker` — the codebase's
established way of keeping an external or per-instance effect swappable. The
`outbox` fixture swaps in a recorder for every test, which is what makes F6
("no socket is ever opened") assertable rather than aspirational.
"""

from __future__ import annotations

import smtplib

from tests.conftest import VALID_PW


def _seller_and_buyer(auth_headers):
    return (
        auth_headers(email="seller@example.com", role="seller"),
        auth_headers(email="buyer@example.com", role="buyer"),
    )


def test_f1_verified_recipient_gets_one_email(
    client, auth_headers, live_listing, granted_access, verify_email, outbox
):
    """F1 — a notification for a verified address dispatches exactly one email."""
    seller, buyer = _seller_and_buyer(auth_headers)
    verify_email(buyer)
    outbox.sent.clear()                       # drop the verification mail itself

    granted_access(live_listing(seller), buyer, seller)

    assert len(outbox.to("buyer@example.com")) == 1


def test_f2_unverified_recipient_gets_the_inbox_but_no_email(
    auth_headers, live_listing, granted_access, notification_rows, user_id, outbox
):
    """F2 — spec D6: an unverified address gets in-app delivery and no mail."""
    seller, buyer = _seller_and_buyer(auth_headers)
    outbox.sent.clear()

    granted_access(live_listing(seller), buyer, seller)

    assert notification_rows(user_id(buyer)) != []
    assert outbox.to("buyer@example.com") == []


def test_f3_registration_mails_an_unverified_address(client, outbox):
    """F3 — spec D6: transactional mail is exempt, or verification could never
    bootstrap."""
    client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": VALID_PW, "role": "buyer"},
    )

    assert len(outbox.to("new@example.com")) == 1


def test_f4_a_failing_transport_does_not_fail_the_business_action(
    client, auth_headers, live_listing, request_access, verify_email,
    notification_rows, user_id, outbox
):
    """F4 — an SMTP outage must never turn an approval into a 500."""
    seller, buyer = _seller_and_buyer(auth_headers)
    verify_email(buyer)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    outbox.should_raise = True
    res = client.post(f"/api/access-requests/{req_id}/approve", headers=seller)

    assert res.status_code == 200
    assert "access_approved" in [r["type"] for r in notification_rows(user_id(buyer))]


def test_f5_emails_carry_no_secrets_or_private_fields(
    client, auth_headers, live_listing, granted_access, verify_email, session, outbox
):
    """F5 — no password hash, no JWT, no `ListingPrivate` value in any mail."""
    from sqlalchemy import text

    seller, buyer = _seller_and_buyer(auth_headers)
    verify_email(buyer)
    granted_access(live_listing(seller), buyer, seller)

    hashes = [
        row[0] for row in session.execute(text('SELECT password_hash FROM "user"')).fetchall()
    ]
    body = str(outbox.sent)
    assert not any(h in body for h in hashes)
    assert "eyJ" not in body                  # a JWT's base64 header prefix
    assert "Acme Internal Tools LLC" not in body
    assert "acme.example.com" not in body


def test_f6_no_smtp_socket_is_ever_opened(client, monkeypatch, outbox):
    """F6 — the port is swapped in tests; constructing an SMTP client would fail."""
    def _explode(*args, **kwargs):
        raise AssertionError("the test suite must never open an SMTP connection")

    monkeypatch.setattr(smtplib, "SMTP", _explode)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _explode, raising=False)

    res = client.post(
        "/api/auth/register",
        json={"email": "nosocket@example.com", "password": VALID_PW, "role": "buyer"},
    )

    assert res.status_code == 201
    assert outbox.to("nosocket@example.com") != []
