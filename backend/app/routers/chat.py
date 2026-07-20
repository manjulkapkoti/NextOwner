"""Chat — the project's first WebSocket surface (M6, spec 006, FR-16).

The WebSocket handler (`conversation_socket` below) is the trust boundary
`security.md` §1.5 describes: authenticate **during the handshake**, never
accept-then-ignore, and re-derive the sender from the verified connection on
every message — a spoofed `sender_id` in the payload is not even read.

`conversation_role_for` (`permissions.py`) can't raise an `AppError` here —
there is no JSON response for a WebSocket to render one into — so this file
translates a `None` role directly into a close code instead of a Forbidden.
"""

from __future__ import annotations

import json

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from ..chat_broker import chat_broker
from ..config import settings
from ..db import get_session
from ..models import Conversation, Message, User
from ..permissions import conversation_role_for
from ..ratelimit import InMemoryRateLimiterBackend, RateLimiter
from ..security import decode_access_token

ws_router = APIRouter()

# Per-connection message cap (spec 006 E1). In-process, like the auth
# limiters (`security.md` §6 DoS surface) — the same per-instance-state
# caveat applies and is out of scope for this milestone (`plan.md` § Build
# order slice 5's note; `design_implementation.md` § Horizontal scale).
_chat_rate_limiter = RateLimiter(
    max_attempts=settings.chat_rate_limit_max,
    window_seconds=settings.chat_rate_limit_window_seconds,
    backend=InMemoryRateLimiterBackend(),
)


def _authenticate_ws(token: str, session: Session) -> User | None:
    """A non-raising twin of `get_current_user` for the WebSocket handshake
    (spec 006 D6 — the token is a query param, never a header)."""
    if not token:
        return None
    try:
        claims = decode_access_token(token)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, TypeError, ValueError, KeyError):
        return None
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        return None
    return user


@ws_router.websocket("/conversations/{conversation_id}")
async def conversation_socket(
    websocket: WebSocket,
    conversation_id: int,
    token: str = Query(default=""),
    session: Session = Depends(get_session),
) -> None:
    """Connect, authenticate, and hold one chat conversation's live socket.

    Rejection happens **before** `accept()` (spec 006 B1-B5): a bad token is
    `4001`, a non-member (including a revoked buyer, or a conversation that
    doesn't exist) is `4003` — the same code for both, so neither is an
    existence oracle (D2/S4).
    """
    user = _authenticate_ws(token, session)
    if user is None:
        await websocket.close(code=4001, reason="auth_failed")
        return

    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation_role_for(session, conversation, user) is None:
        await websocket.close(code=4003, reason="not_a_member")
        return

    await websocket.accept()
    chat_broker.register(conversation_id, user.id, websocket)
    limiter_key = f"{conversation_id}:{user.id}"

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                data = json.loads(raw)
                text = data.get("text") if isinstance(data, dict) else None
            except (json.JSONDecodeError, AttributeError):
                text = None

            if not isinstance(text, str) or not text.strip():
                await websocket.send_json({"type": "error", "code": "invalid_message"})
                continue
            if len(text) > settings.chat_message_max_chars:
                await websocket.send_json({"type": "error", "code": "message_too_long"})
                continue

            if not _chat_rate_limiter.check(limiter_key):
                await websocket.close(code=4009, reason="rate_limited")
                return

            message = Message(conversation_id=conversation_id, sender_id=user.id, text=text.strip())
            session.add(message)
            session.commit()
            session.refresh(message)

            await chat_broker.publish(
                conversation_id,
                {
                    "type": "message",
                    "id": message.id,
                    "conversation_id": conversation_id,
                    "sender_id": user.id,
                    "text": message.text,
                    "created_at": message.created_at.isoformat(),
                },
            )
    finally:
        chat_broker.unregister(conversation_id, user.id, websocket)
