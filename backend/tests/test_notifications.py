"""M8 — the notifications engine (spec 008): C (event projection), E (the inbox).

Written failing first: the `notification` table, `notifications.py`'s `notify()`
recipient derivation, and every `/api/notifications` route do not exist yet, so
each test here either asserts on a table SQLite has never heard of or calls a
route that 404s. Both are runtime failures — the red set is the work queue.

Scope: this file owns **who receives what** (C — spec D3's recipient derivation,
projected from the event rows M3/M5/M6/M7 already leave behind) and **the
caller-scoped inbox** (E). The security corridors around them (S) and the
saved-search fan-out (B) live in `test_alerts_security.py` and
`test_saved_searches.py`.
"""

from __future__ import annotations

from tests.conftest import bearer_token


def _ws_url(conversation_id: int, token: str) -> str:
    return f"/ws/conversations/{conversation_id}?token={token}"


def _seller_and_buyer(auth_headers, seller="seller@example.com", buyer="buyer@example.com"):
    return auth_headers(email=seller, role="seller"), auth_headers(email=buyer, role="buyer")


def _types(rows) -> list[str]:
    return [r["type"] for r in rows]


# ── C — projecting notifications from the M3/M5/M6/M7 events ─────────────────


def test_c1_listing_approved_notifies_only_the_owner(
    client, auth_headers, admin_headers, make_listing, notification_rows, user_id
):
    """C1 — approving a listing notifies its owner, and nobody else."""
    seller = auth_headers(email="seller@example.com", role="seller")
    admin = admin_headers()
    listing_id = make_listing(seller).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=seller)
    client.post(f"/api/listings/{listing_id}/approve", headers=admin)

    assert "listing_approved" in _types(notification_rows(user_id(seller)))
    assert notification_rows(user_id(admin)) == []


def test_c2_listing_rejected_notification_carries_the_reason(
    client, auth_headers, admin_headers, make_listing, notification_rows, user_id
):
    """C2 — a rejection notification carries the admin's reason."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=seller)
    client.post(
        f"/api/listings/{listing_id}/reject",
        json={"reason": "Financials need a source document"},
        headers=admin_headers(),
    )

    rows = [r for r in notification_rows(user_id(seller)) if r["type"] == "listing_rejected"]
    assert len(rows) == 1
    assert "Financials need a source document" in rows[0]["title"]


def test_c3_access_request_notifies_the_seller_not_the_buyer(
    auth_headers, live_listing, request_access, notification_rows, user_id
):
    """C3 — requesting access notifies the listing's owner; the buyer gets nothing."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    request_access(listing_id, buyer)

    assert "access_requested" in _types(notification_rows(user_id(seller)))
    assert "access_requested" not in _types(notification_rows(user_id(buyer)))


def test_c4_access_approved_notifies_the_buyer(
    auth_headers, live_listing, granted_access, notification_rows, user_id
):
    """C4 — approving an access request notifies the buyer."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)

    assert "access_approved" in _types(notification_rows(user_id(buyer)))


def test_c5_access_denied_notifies_the_buyer(
    client, auth_headers, live_listing, request_access, notification_rows, user_id
):
    """C5 — denying an access request notifies the buyer."""
    seller, buyer = _seller_and_buyer(auth_headers)
    req_id = request_access(live_listing(seller), buyer).json()["id"]
    client.post(f"/api/access-requests/{req_id}/deny", headers=seller)

    assert "access_denied" in _types(notification_rows(user_id(buyer)))


def test_c6_access_revoked_notifies_the_buyer(
    client, auth_headers, live_listing, granted_access, notification_rows, user_id
):
    """C6 — revoking access notifies the buyer."""
    seller, buyer = _seller_and_buyer(auth_headers)
    req_id = granted_access(live_listing(seller), buyer, seller)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    assert "access_revoked" in _types(notification_rows(user_id(buyer)))


def test_c7_message_notifies_the_other_party_only(
    client, auth_headers, live_listing, chat_conversation, notification_rows, user_id
):
    """C7 — a chat message notifies the recipient, never the sender."""
    seller, buyer = _seller_and_buyer(auth_headers)
    conv_id = chat_conversation(live_listing(seller), buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": "Is churn really 2%?"})
        ws.receive_json()                     # drain the sender's own echo (spec 006 D4)

    assert "message_received" in _types(notification_rows(user_id(seller)))
    assert "message_received" not in _types(notification_rows(user_id(buyer)))


def test_c8_offer_submitted_notifies_the_seller_only(
    auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """C8 — a buyer's offer notifies the seller, not the buyer."""
    seller, buyer = _seller_and_buyer(auth_headers)
    submitted_offer(live_listing(seller), buyer, seller)

    assert "offer_submitted" in _types(notification_rows(user_id(seller)))
    assert "offer_submitted" not in _types(notification_rows(user_id(buyer)))


def test_c9_offer_countered_notifies_the_buyer(
    client, auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """C9 — the seller's counter notifies the buyer."""
    seller, buyer = _seller_and_buyer(auth_headers)
    offer_id = submitted_offer(live_listing(seller), buyer, seller)
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

    assert "offer_countered" in _types(notification_rows(user_id(buyer)))


def test_c10_offer_accepted_notifies_the_proposer(
    client, auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """C10 — accepting notifies whoever proposed those terms."""
    seller, buyer = _seller_and_buyer(auth_headers)
    offer_id = submitted_offer(live_listing(seller), buyer, seller)
    client.post(f"/api/offers/{offer_id}/accept", headers=seller)

    assert "offer_accepted" in _types(notification_rows(user_id(buyer)))


def test_c11_offer_declined_notifies_the_proposer(
    client, auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """C11 — declining notifies whoever proposed those terms."""
    seller, buyer = _seller_and_buyer(auth_headers)
    offer_id = submitted_offer(live_listing(seller), buyer, seller)
    client.post(f"/api/offers/{offer_id}/decline", headers=seller)

    assert "offer_declined" in _types(notification_rows(user_id(buyer)))


def test_c12_auto_declined_sibling_buyer_is_notified(
    client, auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """C12 — the sibling auto-declined by an accept notifies its own buyer."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer_a = auth_headers(email="a@example.com", role="buyer")
    buyer_b = auth_headers(email="b@example.com", role="buyer")
    listing_id = live_listing(seller)

    winner = submitted_offer(listing_id, buyer_a, seller)
    submitted_offer(listing_id, buyer_b, seller)
    client.post(f"/api/offers/{winner}/accept", headers=seller)

    assert "offer_auto_declined" in _types(notification_rows(user_id(buyer_b)))


def test_c13_offer_withdrawn_notifies_the_seller(
    client, auth_headers, live_listing, submitted_offer, notification_rows, user_id
):
    """C13 — a buyer withdrawing notifies the seller."""
    seller, buyer = _seller_and_buyer(auth_headers)
    offer_id = submitted_offer(live_listing(seller), buyer, seller)
    client.post(f"/api/offers/{offer_id}/withdraw", headers=buyer)

    assert "offer_withdrawn" in _types(notification_rows(user_id(seller)))


def test_c14_message_notification_does_not_store_the_message_text(
    client, auth_headers, live_listing, chat_conversation, notification_rows, user_id
):
    """C14 — spec D2: a notification carries no message body, so a revoked
    buyer's stale inbox row leaks nothing."""
    seller, buyer = _seller_and_buyer(auth_headers)
    conv_id = chat_conversation(live_listing(seller), buyer, seller)
    secret = "TOPSECRET-margin-is-actually-9-percent"

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": secret})
        ws.receive_json()

    rows = notification_rows(user_id(seller))
    assert rows, "expected a message notification for the seller"
    assert not any(secret in str(r) for r in rows)


def test_c15_notifications_carry_no_private_listing_fields(
    auth_headers, live_listing, granted_access, notification_rows, user_id
):
    """C15 — spec D2: no `ListingPrivate` value ever enters a notification row."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)

    everything = str(notification_rows(user_id(buyer)) + notification_rows(user_id(seller)))
    assert "Acme Internal Tools LLC" not in everything
    assert "acme.example.com" not in everything


# ── E — the caller-scoped inbox ──────────────────────────────────────────────


def test_e1_inbox_returns_only_the_callers_rows_newest_first(
    client, auth_headers, live_listing, granted_access, inbox
):
    """E1 — the inbox lists the caller's own notifications, newest first."""
    seller, buyer = _seller_and_buyer(auth_headers)
    req_id = granted_access(live_listing(seller), buyer, seller)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    rows = inbox(buyer).json()
    assert len(rows) >= 2
    assert [r["created_at"] for r in rows] == sorted(
        (r["created_at"] for r in rows), reverse=True
    )


def test_e2_another_users_notification_is_absent(
    auth_headers, live_listing, granted_access, inbox
):
    """E2 — user B's inbox never contains user A's rows."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    stranger = auth_headers(email="stranger@example.com", role="buyer")

    assert inbox(stranger).json() == []


def test_e3_unread_filter_returns_only_unread(
    client, auth_headers, live_listing, granted_access, inbox
):
    """E3 — `?unread=true` excludes rows already marked read."""
    seller, buyer = _seller_and_buyer(auth_headers)
    req_id = granted_access(live_listing(seller), buyer, seller)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    first = inbox(buyer).json()[0]["id"]
    client.post(f"/api/notifications/{first}/read", headers=buyer)

    unread = inbox(buyer, unread=True).json()
    assert first not in [r["id"] for r in unread]
    assert all(r["read_at"] is None for r in unread)


def test_e4_marking_read_sets_read_at_and_leaves_the_unread_filter(
    client, auth_headers, live_listing, granted_access, inbox
):
    """E4 — marking read stamps `read_at` and drops the row from `?unread=true`."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    notification_id = inbox(buyer).json()[0]["id"]

    res = client.post(f"/api/notifications/{notification_id}/read", headers=buyer)
    assert res.status_code == 200
    assert res.json()["read_at"] is not None
    assert notification_id not in [r["id"] for r in inbox(buyer, unread=True).json()]


def test_e5_marking_another_users_notification_read_is_404(
    client, auth_headers, live_listing, granted_access, inbox
):
    """E5 — IDOR: B cannot mark A's notification read."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    notification_id = inbox(buyer).json()[0]["id"]

    assert client.post(f"/api/notifications/{notification_id}/read", headers=stranger).status_code == 404
    assert inbox(buyer).json()[0]["read_at"] is None


def test_e6_unread_count_is_caller_scoped(
    client, auth_headers, live_listing, granted_access
):
    """E6 — the badge count covers only the caller's rows."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    stranger = auth_headers(email="stranger@example.com", role="buyer")

    assert client.get("/api/notifications/unread-count", headers=buyer).json()["unread_count"] >= 1
    assert client.get("/api/notifications/unread-count", headers=stranger).json()["unread_count"] == 0


def test_e7_read_all_touches_only_the_caller(
    client, auth_headers, live_listing, granted_access, inbox
):
    """E7 — `read-all` marks the caller's unread rows and nobody else's."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)

    client.post("/api/notifications/read-all", headers=buyer)
    assert inbox(buyer, unread=True).json() == []
    assert inbox(seller, unread=True).json() != []


def test_e8_pagination_limit_is_capped(client, auth_headers, inbox):
    """E8 — an over-cap `limit` is refused at the boundary (DoS surface)."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    assert inbox(buyer, limit=500).status_code == 422


def test_e9_inbox_requires_authentication(client):
    """E9 — the inbox is not a public route."""
    assert client.get("/api/notifications").status_code == 401


def test_e10_marking_read_twice_is_idempotent(
    client, auth_headers, live_listing, granted_access, inbox
):
    """E10 — a second mark-read is a no-op; `read_at` does not move."""
    seller, buyer = _seller_and_buyer(auth_headers)
    granted_access(live_listing(seller), buyer, seller)
    notification_id = inbox(buyer).json()[0]["id"]

    first = client.post(f"/api/notifications/{notification_id}/read", headers=buyer).json()["read_at"]
    second = client.post(f"/api/notifications/{notification_id}/read", headers=buyer)
    assert second.status_code == 200
    assert second.json()["read_at"] == first
