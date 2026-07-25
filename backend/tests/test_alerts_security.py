"""M8 — security & abuse (S) and the failure contract (X), spec 008.

Written failing first, and this is the file that matters most in the milestone.

**S1 and S10 are the corridor tests.** Every prior milestone that shipped a
gate-per-door still found a bug in the *sequence* between doors — M3's
pause→edit→resume republish, M7's counter-on-a-dead-listing. M8's version of
that question is: *the inbox is a second surface that names objects the
permission gates own — does it become a way around them?* Spec D2's answer is
that a notification stores no private payload, so following a stale row lands
on the real gate and is refused. S1 walks that corridor; S10 asserts the
invariant over reachable sequences rather than trusting a per-door check.
"""

from __future__ import annotations

from tests.conftest import bearer_token


def _ws_url(conversation_id: int, token: str) -> str:
    return f"/ws/conversations/{conversation_id}?token={token}"


def _seller_and_buyer(auth_headers):
    return (
        auth_headers(email="seller@example.com", role="seller"),
        auth_headers(email="buyer@example.com", role="buyer"),
    )


# ── S — security & abuse ─────────────────────────────────────────────────────


def test_s1_a_revoked_buyer_cannot_follow_a_message_notification(
    client, auth_headers, live_listing, granted_access, chat_conversation, inbox
):
    """S1 — the inbox is not a bypass of the live membership re-check.

    The corridor: a buyer holds a legitimate message notification, then the
    seller revokes access. The stale row may still be listed (it carries no
    private payload, spec D2) but following it must hit `conversation_role_for`
    and be refused, exactly as M6's revocation semantics require.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(seller))) as ws:
        ws.send_json({"text": "happy to talk numbers"})
        ws.receive_json()

    req_id = client.get("/api/my/access-requests", headers=buyer).json()[0]["id"]
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    linked = [r for r in inbox(buyer).json() if r["type"] == "message_received"]
    assert linked, "expected the buyer to hold a message notification"
    res = client.get(f"/api/conversations/{conv_id}/messages", headers=buyer)
    assert res.status_code == 403


def test_s2_a_listing_matched_alert_grants_no_private_access(
    client, auth_headers, live_listing, notification_rows, user_id
):
    """S2 — an alert is an advertisement, not an entitlement."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    client.post(
        "/api/saved-searches",
        json={"name": "s", "filters": {"type": "saas"}},
        headers=buyer,
    )
    listing_id = live_listing(seller)

    assert "listing_matched" in [r["type"] for r in notification_rows(user_id(buyer))]
    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 403
    assert res.json()["code"] == "nda_access_required"


def test_s3_the_notification_schema_leaks_no_identity_or_private_fields(
    client, auth_headers, live_listing, granted_access, inbox
):
    """S3 — schema-leak: the response model declares only safe fields."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)

    rows = inbox(buyer).json()
    assert rows
    allowed = {
        "id", "type", "title", "listing_id", "conversation_id",
        "offer_id", "read_at", "created_at",
    }
    for row in rows:
        assert set(row) <= allowed, f"unexpected field(s): {set(row) - allowed}"
        assert "recipient_id" not in row


def test_s4_notifications_cannot_be_created_over_the_api(client, auth_headers):
    """S4 — notifications are a server-side side effect, never a client write.

    **This test passes before implementation, deliberately** — it is a
    regression pin, not a vacuous assertion (the M5 E4/E5 case). It asserts the
    *absence* of a route, which is true today and must stay true after slice 3
    mounts the read endpoints next to it; the way it fails is someone adding a
    `POST /api/notifications`. A pin like this has no red phase by definition,
    which is why it is called out here rather than silently counted as covered.
    """
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    res = client.post(
        "/api/notifications",
        json={"type": "listing_approved", "title": "spoofed"},
        headers=buyer,
    )

    assert res.status_code in (404, 405)


def test_s5_a_filter_on_a_private_column_is_refused(client, auth_headers):
    """S5 — the alert engine can never match on `ListingPrivate` text (M4's rule)."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    res = client.post(
        "/api/saved-searches",
        json={"name": "oracle", "filters": {"company_name": "Acme Internal Tools LLC"}},
        headers=buyer,
    )

    assert res.status_code == 422


def test_s6_client_supplied_recipient_and_read_at_are_ignored(
    client, auth_headers, live_listing, granted_access, inbox, user_id
):
    """S6 — mass-assignment on the M8 write routes."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    notification_id = inbox(buyer).json()[0]["id"]

    client.post(
        f"/api/notifications/{notification_id}/read",
        json={"recipient_id": user_id(stranger), "read_at": None},
        headers=buyer,
    )

    assert inbox(stranger).json() == []
    assert inbox(buyer).json()[0]["read_at"] is not None


def test_s7_a_reset_token_in_the_query_string_is_refused(client, register, outbox):
    """S7 — spec D11: the token is a body field, never a URL parameter a proxy logs."""
    from tests.conftest import reset_token_from

    register(email="alice@example.com")
    client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    token = reset_token_from(outbox.to("alice@example.com")[-1])

    res = client.post(
        f"/api/auth/reset-password?token={token}&password=a+brand+new+password+here"
    )

    assert res.status_code == 422


def test_s8_notification_ids_are_not_an_existence_oracle(
    client, auth_headers, live_listing, granted_access, inbox
):
    """S8 — probing a real foreign id and an invented one answer identically."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    real_foreign = inbox(buyer).json()[0]["id"]

    foreign = client.post(f"/api/notifications/{real_foreign}/read", headers=stranger)
    invented = client.post("/api/notifications/987654/read", headers=stranger)

    assert (foreign.status_code, foreign.json()) == (invented.status_code, invented.json())


def test_s9_re_registering_an_address_does_not_mail_its_owner(client, register, outbox):
    """S9 — registration must not become a way to mail a third party on demand.

    The first assertion (a *successful* registration does mail) is what keeps
    this from passing vacuously: without it, "no mail was sent" is trivially
    true before the mailer exists, and the test would never have failed first.
    Asserting both halves means it only goes green once registration really
    mails **and** the duplicate path really stays silent.
    """
    register(email="victim@example.com")
    assert len(outbox.to("victim@example.com")) == 1
    outbox.sent.clear()

    res = register(email="victim@example.com")

    assert res.status_code == 409
    assert res.json()["code"] == "email_taken"
    assert outbox.sent == []


def test_s10_every_notification_recipient_is_a_party_to_its_subject(
    client, session, auth_headers, admin_headers, make_listing, live_listing,
    granted_access, submitted_offer, chat_conversation, user_id
):
    """S10 — the reachability invariant, in `test_nda_gate.py` D10's tradition.

    A negative test per *door* proves each door is locked; it says nothing about
    the corridor. This walks a sequence of real transitions that exercises every
    path which writes a notification, and after **every step** asserts the one
    invariant that must never break: a notification's recipient is a party to
    the object it names — the listing's owner, or the buyer named on the access
    request / conversation / offer. `listing_matched` is the deliberate
    exception (a public advertisement), and is held to the stricter rule that it
    must be addressed to someone who actually saved a matching search.
    """
    from sqlalchemy import text

    def check_invariant(step: str) -> None:
        rows = session.execute(
            text(
                "SELECT id, recipient_id, type, listing_id, conversation_id, offer_id "
                "FROM notification ORDER BY id"
            )
        ).mappings().all()
        for row in rows:
            recipient, kind = row["recipient_id"], row["type"]
            if kind == "listing_matched":
                savers = {
                    r[0] for r in session.execute(
                        text("SELECT user_id FROM savedsearch")
                    ).fetchall()
                }
                assert recipient in savers, f"[{step}] alert to a non-subscriber: {dict(row)}"
                continue

            parties: set[int] = set()
            if row["listing_id"] is not None:
                owner = session.execute(
                    text("SELECT owner_id FROM listing WHERE id = :i"),
                    {"i": row["listing_id"]},
                ).scalar_one_or_none()
                if owner is not None:
                    parties.add(owner)
                buyers = session.execute(
                    text("SELECT buyer_id FROM accessrequest WHERE listing_id = :i"),
                    {"i": row["listing_id"]},
                ).fetchall()
                parties.update(b[0] for b in buyers)
            if row["conversation_id"] is not None:
                buyer = session.execute(
                    text("SELECT buyer_id FROM conversation WHERE id = :i"),
                    {"i": row["conversation_id"]},
                ).scalar_one_or_none()
                if buyer is not None:
                    parties.add(buyer)
            if row["offer_id"] is not None:
                buyer = session.execute(
                    text("SELECT buyer_id FROM offer WHERE id = :i"),
                    {"i": row["offer_id"]},
                ).scalar_one_or_none()
                if buyer is not None:
                    parties.add(buyer)

            assert parties, f"[{step}] notification names no resolvable subject: {dict(row)}"
            assert recipient in parties, f"[{step}] outsider recipient: {dict(row)}"

    seller, buyer = _seller_and_buyer(auth_headers)
    outsider = auth_headers(email="outsider@example.com", role="buyer")
    client.post(
        "/api/saved-searches",
        json={"name": "s", "filters": {"type": "saas"}},
        headers=outsider,
    )
    check_invariant("saved search created")

    # curation → publication → access → chat → offers, checking after each move
    rejected = make_listing(seller).json()["id"]
    client.post(f"/api/listings/{rejected}/submit", headers=seller)
    check_invariant("submitted")
    client.post(
        f"/api/listings/{rejected}/reject",
        json={"reason": "needs detail"},
        headers=admin_headers(),
    )
    check_invariant("rejected")

    listing_id = live_listing(seller)
    check_invariant("published")

    conv_id = chat_conversation(listing_id, buyer, seller)
    check_invariant("access approved + conversation created")

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": "question about churn"})
        ws.receive_json()
    check_invariant("message sent")

    offer_id = submitted_offer(listing_id, buyer, seller)
    check_invariant("offer submitted")
    client.post(
        f"/api/offers/{offer_id}/counter",
        json={
            "price": "400000.00",
            "structure": "all cash",
            "contingencies": "none",
            "proposed_close_date": "2026-11-01",
        },
        headers=seller,
    )
    check_invariant("countered")

    req_id = client.get("/api/my/access-requests", headers=buyer).json()[0]["id"]
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    check_invariant("access revoked")


# ── X — errors & failure modes ───────────────────────────────────────────────


def test_x1_a_wrongly_typed_filter_is_422_with_a_field_detail(client, auth_headers):
    """X1 — validation is field-level, not a bare rejection."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    res = client.post(
        "/api/saved-searches",
        json={"name": "x", "filters": {"min_price": "not-a-number"}},
        headers=buyer,
    )

    assert res.status_code == 422
    assert "min_price" in str(res.json())


def test_x2_an_internal_error_returns_the_generic_contract(client, auth_headers, session):
    """X2 — a 500 on a notifications route leaks no stack, SQL, or file path.

    The fault is injected at the session boundary (the route's own query
    raises), which is the cheapest way to reach the catch-all handler through
    a real route rather than the `/_debug/boom` stub.
    """
    from app.db import get_session
    from app.main import app

    buyer = auth_headers(email="buyer@example.com", role="buyer")

    class BrokenSession:
        def __getattr__(self, name):
            if name == "exec":
                raise RuntimeError("injected failure")
            return getattr(session, name)

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    try:
        res = client.get("/api/notifications", headers=buyer)
    finally:
        app.dependency_overrides[get_session] = lambda: session

    assert res.status_code == 500
    body = res.json()
    assert "request_id" in body
    assert "Traceback" not in str(body)
    assert "SELECT" not in str(body).upper()


def test_x3_smtp_failure_keeps_forgot_password_uniform(client, register, outbox):
    """X3 — a transport failure must not become the enumeration oracle G2 prevents."""
    register(email="alice@example.com")
    outbox.should_raise = True

    res = client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})

    assert res.status_code == 202


def test_x4_a_malformed_token_is_a_400_not_a_500(client):
    """X4 — token syntax nobody could have issued still takes the uniform path."""
    res = client.post(
        "/api/auth/reset-password",
        json={"token": "!!! not base64 !!!", "password": "a perfectly fine password"},
    )

    assert res.status_code == 400
    assert res.json()["code"] == "invalid_token"


def test_x5_negative_pagination_is_422(client, auth_headers, inbox):
    """X5 — bounded pagination at the boundary, both directions."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    assert inbox(buyer, limit=-1).status_code == 422
    assert inbox(buyer, offset=-5).status_code == 422
