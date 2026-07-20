"""M6 — realtime chat (spec 006): A, B, C, D, E, F, S1 (WS half), S3, S4 (WS half), S5.

The project's first WebSocket surface. Written failing first: `Conversation`,
`Message`, the WS handshake, and the message loop do not exist yet, so every
test here either asserts a status/close-code the app cannot yet produce, or
errors trying to connect to a route that isn't mounted (`WebSocketDisconnect`
en route to something else, or a plain connection failure). Both are runtime
failures, not collection failures — the red set is the work queue.

Scope: this file owns the WebSocket-live half — connect/auth/membership (B),
sending/receiving/persistence (C), non-fatal validation (D), fatal rate
limiting (E), revocation applying live (F), conversation creation (A), and
the security criteria that only make sense against a live socket. REST-only
criteria (G/H/I, the REST halves of S1/S4, X1) live in `test_chat_rest.py`.
"""

from __future__ import annotations

import datetime

import jwt
import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import TEST_JWT_ALG, TEST_JWT_SECRET, bearer_token


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


def _user_id(client, headers) -> int:
    return client.get("/api/auth/me", headers=headers).json()["id"]


def _access_request_id(client, buyer_headers, listing_id: int) -> int:
    rows = client.get("/api/my/access-requests", headers=buyer_headers).json()
    return next(r["id"] for r in rows if r["listing_id"] == listing_id)


def _ws_url(conversation_id: int, token: str | None) -> str:
    if token is None:
        return f"/ws/conversations/{conversation_id}"
    return f"/ws/conversations/{conversation_id}?token={token}"


def _expired_token(user_id: int) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "iat": now - datetime.timedelta(hours=2),
        "exp": now - datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALG)


# ── A — conversation creation on approval ────────────────────────────────────


def test_a1_approval_creates_a_conversation(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    assert conv_id is not None


def test_a2_denied_request_creates_no_conversation(client, auth_headers, live_listing, request_access, session):
    from app.models import Conversation
    from sqlmodel import select

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]
    client.post(f"/api/access-requests/{req_id}/deny", headers=seller)

    buyer_id = _user_id(client, buyer)
    conversation = session.exec(
        select(Conversation).where(
            Conversation.listing_id == listing_id, Conversation.buyer_id == buyer_id
        )
    ).first()
    assert conversation is None


# ── B — WebSocket connect: authentication + membership ──────────────────────


def test_b1_owner_connects(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    with client.websocket_connect(_ws_url(conv_id, bearer_token(seller))):
        pass  # accepted — no exception raised


def test_b2_approved_buyer_connects(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))):
        pass


def test_b3_stranger_is_rejected_4003(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    stranger = auth_headers(email="mallory@example.com", role="buyer")

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(stranger))):
            pass
    assert exc.value.code == 4003


@pytest.mark.parametrize("kind", ["missing", "malformed", "tampered", "expired"])
def test_b4_s3_bad_token_is_rejected_4001(client, auth_headers, live_listing, chat_conversation, kind):
    """B4 + S3 together: every flavor of "not a valid, live identity" is 4001,
    never 4003 — identity resolves before membership (mirrors M5's S6)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    if kind == "missing":
        token = None
    elif kind == "malformed":
        token = "not-a-jwt"
    elif kind == "tampered":
        token = bearer_token(buyer) + "tampered"
    else:
        token = _expired_token(_user_id(client, buyer))

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, token)):
            pass
    assert exc.value.code == 4001


def test_b5_s4_nonexistent_conversation_is_rejected_4003(client, auth_headers):
    """B5 + the WS half of S4: a real id you don't own and a fake id are
    indistinguishable (D2) — both 4003, never a distinguishable error."""
    someone = auth_headers(email="alice@example.com", role="buyer")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(999999, bearer_token(someone))):
            pass
    assert exc.value.code == 4003


# ── C — sending and receiving messages ───────────────────────────────────────


def test_c1_message_reaches_the_other_participant(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as buyer_ws, \
         client.websocket_connect(_ws_url(conv_id, bearer_token(seller))) as seller_ws:
        buyer_ws.send_json({"text": "Is churn really 2%?"})
        assert seller_ws.receive_json()["text"] == "Is churn really 2%?"


def test_c2_message_is_persisted_across_reconnect(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": "hello"})
        ws.receive_json()  # drain the sender's own echo (D4) before closing

    res = client.get(f"/api/conversations/{conv_id}/messages", headers=buyer)
    assert res.status_code == 200
    assert "hello" in [m["text"] for m in res.json()]


def test_c3_spoofed_sender_id_is_ignored(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    seller_id = _user_id(client, seller)
    buyer_id = _user_id(client, buyer)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": "hi", "sender_id": seller_id})
        frame = ws.receive_json()

    assert frame["sender_id"] == buyer_id


def test_c4_sender_receives_their_own_broadcast(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": "hi"})
        frame = ws.receive_json()

    assert frame["text"] == "hi"
    assert isinstance(frame.get("id"), int)
    assert frame.get("created_at")


# ── D — message validation (non-fatal) ───────────────────────────────────────


@pytest.mark.parametrize("bad_text", ["", "   "])
def test_d1_blank_text_is_a_non_fatal_error(client, auth_headers, live_listing, chat_conversation, bad_text):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": bad_text})
        assert ws.receive_json() == {"type": "error", "code": "invalid_message"}
        # the connection survives — prove it by sending a valid message next
        ws.send_json({"text": "still here"})
        assert ws.receive_json()["text"] == "still here"


def test_d2_text_over_the_cap_is_a_non_fatal_error(client, auth_headers, live_listing, chat_conversation):
    from app.config import settings

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    too_long = "x" * (settings.chat_message_max_chars + 1)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_json({"text": too_long})
        assert ws.receive_json() == {"type": "error", "code": "message_too_long"}
        ws.send_json({"text": "still here"})
        assert ws.receive_json()["text"] == "still here"


def test_d3_malformed_frame_is_a_non_fatal_error(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
        ws.send_text("not valid json{")
        assert ws.receive_json() == {"type": "error", "code": "invalid_message"}
        ws.send_json({"text": 12345})  # non-string
        assert ws.receive_json() == {"type": "error", "code": "invalid_message"}
        ws.send_json({"nope": "no text key"})
        assert ws.receive_json() == {"type": "error", "code": "invalid_message"}
        ws.send_json({"text": "still here"})
        assert ws.receive_json()["text"] == "still here"


# ── E — rate limiting (fatal) ─────────────────────────────────────────────────


def test_e1_rate_cap_closes_the_connection(client, auth_headers, live_listing, chat_conversation, monkeypatch):
    from app.routers import chat as chat_router

    monkeypatch.setattr(chat_router._chat_rate_limiter, "max_attempts", 3)
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
            for i in range(3):
                ws.send_json({"text": f"msg {i}"})
                ws.receive_json()  # each lands under the cap
            ws.send_json({"text": "one too many"})
            ws.receive_json()  # the close arrives here instead of a message
    assert exc.value.code == 4009


def test_e2_invalid_frames_also_consume_the_rate_budget(client, auth_headers, live_listing, chat_conversation, monkeypatch):
    """An invalid/oversized frame must cost the sender its rate budget
    exactly like a valid one — otherwise a garbage flood walks straight past
    the limiter D1-D3's non-fatal handling would otherwise leave wide open
    (branch review 2026-07-20)."""
    from app.routers import chat as chat_router

    monkeypatch.setattr(chat_router._chat_rate_limiter, "max_attempts", 3)
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
            for _ in range(3):
                ws.send_json({"text": ""})  # invalid — but still counted
                ws.receive_json()
            ws.send_json({"text": ""})  # the 4th invalid frame trips the cap
            ws.receive_json()
    assert exc.value.code == 4009


# ── F — revocation applies live ──────────────────────────────────────────────


def test_f1_revocation_closes_the_live_socket(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    req_id = _access_request_id(client, buyer, listing_id)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
            res = client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
            assert res.status_code == 200
            ws.receive_json()  # the forced close arrives instead of a message
    assert exc.value.code == 4004


def test_f2_reconnect_after_revocation_is_rejected_4003(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    req_id = _access_request_id(client, buyer, listing_id)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))):
            pass
    assert exc.value.code == 4003


def test_f3_revoked_buyer_gets_403_on_rest_history(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    req_id = _access_request_id(client, buyer, listing_id)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    res = client.get(f"/api/conversations/{conv_id}/messages", headers=buyer)
    assert res.status_code == 403


def test_f4_revocation_is_buyer_scoped_not_conversation_wide(client, auth_headers, live_listing, chat_conversation):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    req_id = _access_request_id(client, buyer, listing_id)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    res = client.get(f"/api/conversations/{conv_id}/messages", headers=seller)
    assert res.status_code == 200


def test_f5_revoke_during_handshake_still_closes_the_socket(
    client, auth_headers, live_listing, chat_conversation, monkeypatch, session
):
    """Independent appsec finding (branch review 2026-07-20): `accept()` is a
    real `await` — a yield point a revoke can land in, between the pre-accept
    membership check and the socket's registration with the broker. Simulated
    deterministically rather than raced on real scheduler timing: the FIRST
    call to `conversation_role_for` (the pre-accept check) revokes the row
    directly on the same session as its side effect, mirroring "a revoke
    committed during this connection's `await accept()`" — the SECOND call
    (this fix's post-register re-check) then sees the now-revoked state and
    must refuse.

    Remove the post-register re-check in `chat.py` to see this fail — the
    connection stays open despite the revoke.
    """
    from sqlalchemy import text

    from app.routers import chat as chat_router
    from app.permissions import conversation_role_for as real_role_for

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    conv_id = chat_conversation(listing_id, buyer, seller)
    req_id = _access_request_id(client, buyer, listing_id)

    calls = {"n": 0}

    def racing_role_for(session_, conversation, user):
        calls["n"] += 1
        result = real_role_for(session_, conversation, user)
        if calls["n"] == 1:
            session.execute(text("UPDATE accessrequest SET status = 'revoked' WHERE id = :i"), {"i": req_id})
            session.commit()
        return result

    monkeypatch.setattr(chat_router, "conversation_role_for", racing_role_for)

    # The close (spec 006 F1's own pattern) happens **after** `accept()`, so
    # the client's `__enter__` has already succeeded by the time it fires —
    # a bare `with ...: pass` would never observe it. Only a `receive()`
    # inside the block sees the close frame and raises.
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))) as ws:
            ws.receive_json()
    assert exc.value.code == 4004
    assert calls["n"] == 2  # the pre-accept check, then this fix's re-check


# ── S5 — revocation reachability (a lighter D10 cousin, spec 006 S5) ────────


def test_s5_access_reflects_only_the_current_status(client, auth_headers, live_listing, request_access, session):
    """The state machine only ever reaches two states after approval —
    `approved` and (from there) `revoked`, since revoke is terminal and there
    is no path back. GIVEN each state, WHEN access is checked immediately
    after the action that produced it, THEN the check reflects *that* state
    and never a prior one. Revert F1/F2's live re-check (key
    `conversation_role_for` on the conversation's mere existence instead of
    the access request's current status) to see this fail on the second half.
    """
    from app.models import Conversation
    from sqlmodel import select

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]
    client.post(f"/api/access-requests/{req_id}/approve", headers=seller)
    buyer_id = _user_id(client, buyer)
    conv_id = session.exec(
        select(Conversation).where(
            Conversation.listing_id == listing_id, Conversation.buyer_id == buyer_id
        )
    ).first().id

    # State 1: approved — connect succeeds, history is readable.
    with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))):
        pass
    assert client.get(f"/api/conversations/{conv_id}/messages", headers=buyer).status_code == 200

    # State 2: revoked — the *same* conversation id now refuses both checks.
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(conv_id, bearer_token(buyer))):
            pass
    assert exc.value.code == 4003
    assert client.get(f"/api/conversations/{conv_id}/messages", headers=buyer).status_code == 403
