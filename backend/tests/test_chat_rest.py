"""M6 — realtime chat (spec 006): G, H, I, S1 (REST half), S2, S4 (REST half), X1.

The REST-only half of the chat surface — message history, unread counts via
`last_read_at`, and the conversation list. The WebSocket-live half (A, B, C,
D, E, F, S3, S5) lives in `test_chat.py`. Written failing first, same as that
file: none of these endpoints exist yet.
"""

from __future__ import annotations


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


def _send(client, auth_headers, conv_id, sender_headers, text):
    """Send one message over the socket and wait for the persisted echo, so
    REST-only tests can seed history without duplicating the WS test file's
    connection machinery for every fixture message."""
    from tests.conftest import bearer_token

    with client.websocket_connect(f"/ws/conversations/{conv_id}?token={bearer_token(sender_headers)}") as ws:
        ws.send_json({"text": text})
        return ws.receive_json()


# ── G — message history ──────────────────────────────────────────────────────


def test_g1_history_returns_the_most_recent_page_newest_first(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    for text in ("first", "second", "third"):
        _send(client, auth_headers, conv_id, buyer, text)

    res = client.get(f"/api/conversations/{conv_id}/messages", headers=buyer)
    assert res.status_code == 200
    texts = [m["text"] for m in res.json()]
    assert texts[:3] == ["third", "second", "first"]


def test_g2_before_cursor_returns_older_messages(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    ids = [_send(client, auth_headers, conv_id, buyer, t)["id"] for t in ("one", "two", "three")]

    res = client.get(f"/api/conversations/{conv_id}/messages?before={ids[-1]}", headers=buyer)
    assert res.status_code == 200
    returned_ids = [m["id"] for m in res.json()]
    assert ids[-1] not in returned_ids
    assert ids[0] in returned_ids


def test_g3_s1_non_member_gets_403_on_history(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    stranger = auth_headers(email="mallory@example.com", role="buyer")

    res = client.get(f"/api/conversations/{conv_id}/messages", headers=stranger)
    assert res.status_code == 403


def test_g4_no_credentials_is_401(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    res = client.get(f"/api/conversations/{conv_id}/messages")
    assert res.status_code == 401


def test_g5_over_cap_limit_is_422(client, auth_headers, live_listing, chat_conversation):
    from app.config import settings

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    res = client.get(
        f"/api/conversations/{conv_id}/messages?limit={settings.chat_history_page_limit + 1}",
        headers=buyer,
    )
    assert res.status_code == 422


def test_x1_over_cap_limit_carries_field_level_detail(client, auth_headers, live_listing, chat_conversation):
    from app.config import settings

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    res = client.get(
        f"/api/conversations/{conv_id}/messages?limit={settings.chat_history_page_limit + 1}",
        headers=buyer,
    )
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)


# ── H — unread counts ─────────────────────────────────────────────────────────


def test_h1_unread_count_reflects_the_counterparts_unread_messages(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    for text in ("one", "two", "three"):
        _send(client, auth_headers, conv_id, seller, text)

    rows = client.get("/api/conversations", headers=buyer).json()
    row = next(r for r in rows if r["id"] == conv_id)
    assert row["unread_count"] == 3


def test_h2_marking_read_zeroes_the_unread_count(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    _send(client, auth_headers, conv_id, seller, "hi")

    res = client.post(f"/api/conversations/{conv_id}/read", headers=buyer)
    assert res.status_code == 204

    rows = client.get("/api/conversations", headers=buyer).json()
    row = next(r for r in rows if r["id"] == conv_id)
    assert row["unread_count"] == 0


def test_h3_a_new_message_after_reading_counts_again(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    _send(client, auth_headers, conv_id, seller, "hi")
    client.post(f"/api/conversations/{conv_id}/read", headers=buyer)
    _send(client, auth_headers, conv_id, seller, "one more")

    rows = client.get("/api/conversations", headers=buyer).json()
    row = next(r for r in rows if r["id"] == conv_id)
    assert row["unread_count"] == 1


def test_h4_non_member_cannot_mark_read(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    stranger = auth_headers(email="mallory@example.com", role="buyer")

    res = client.post(f"/api/conversations/{conv_id}/read", headers=stranger)
    assert res.status_code == 403


# ── I — the conversation list ─────────────────────────────────────────────────


def test_i1_buyer_sees_only_their_own_conversations(client, auth_headers, live_listing, chat_conversation):
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer_a = auth_headers(email="alice@example.com", role="buyer")
    buyer_b = auth_headers(email="bob@example.com", role="buyer")
    listing_1 = live_listing(seller, headline="Listing one")
    listing_2 = live_listing(seller, headline="Listing two")
    chat_conversation(listing_1, buyer_a, seller)
    chat_conversation(listing_2, buyer_a, seller)
    chat_conversation(listing_1, buyer_b, seller)

    rows = client.get("/api/conversations", headers=buyer_a).json()
    assert {r["listing_id"] for r in rows} == {listing_1, listing_2}


def test_i2_seller_sees_conversations_across_their_listings(client, auth_headers, live_listing, chat_conversation):
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_1 = live_listing(seller, headline="Listing one")
    listing_2 = live_listing(seller, headline="Listing two")
    chat_conversation(listing_1, buyer, seller)
    chat_conversation(listing_2, buyer, seller)

    rows = client.get("/api/conversations", headers=seller).json()
    assert {r["listing_id"] for r in rows} == {listing_1, listing_2}


def test_i3_no_credentials_is_401(client):
    res = client.get("/api/conversations")
    assert res.status_code == 401


# ── S2 — schema leak ──────────────────────────────────────────────────────────


def test_s2_no_email_or_password_hash_on_conversation_or_message_models(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    _send(client, auth_headers, conv_id, buyer, "hi")

    for res in (
        client.get("/api/conversations", headers=buyer),
        client.get(f"/api/conversations/{conv_id}/messages", headers=buyer),
    ):
        body = res.text.lower()
        assert "password" not in body
        assert "seller@example.com" not in body
        assert "buyer@example.com" not in body


# ── S4 — enumeration uniformity (REST half) ──────────────────────────────────


def test_s4_nonexistent_and_foreign_conversation_ids_look_identical(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    stranger = auth_headers(email="mallory@example.com", role="buyer")

    real_but_foreign = client.get(f"/api/conversations/{conv_id}/messages", headers=stranger)
    fake = client.get("/api/conversations/999999/messages", headers=stranger)

    assert real_but_foreign.status_code == fake.status_code == 403
    assert real_but_foreign.json()["code"] == fake.json()["code"]
