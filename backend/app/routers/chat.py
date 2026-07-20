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
from sqlmodel import Session, func, or_, select

from ..chat_broker import chat_broker
from ..config import settings
from ..db import get_session
from ..models import Conversation, Listing, Message, User, _utcnow
from ..permissions import conversation_role_for, get_current_user, require_conversation_member
from ..ratelimit import InMemoryRateLimiterBackend, RateLimiter
from ..schemas import ConversationSummary, MessageRead
from ..security import decode_access_token

router = APIRouter(tags=["chat"])
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

    # Re-check immediately after registering, with no `await` between this and
    # `register()` above — so no interleaving is possible in between. `accept()`
    # is a real yield point: a revoke can commit and call `close_user` while this
    # connection is mid-handshake, before it exists in the broker's registry for
    # `close_user` to find. Without this second check, that TOCTOU window leaves
    # a revoked buyer connected until they happen to disconnect on their own
    # (branch review 2026-07-20 — appsec finding; spec 006 F1/S5).
    if conversation_role_for(session, conversation, user) is None:
        chat_broker.unregister(conversation_id, user.id, websocket)
        await websocket.close(code=4004, reason="access_revoked")
        return

    limiter_key = f"{conversation_id}:{user.id}"

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Rate-limit BEFORE validating content — a flood of invalid or
            # oversized frames must cost the sender its budget too, or the
            # cap is a no-op against exactly the abuse it exists for
            # (security.md §6 "WebSocket message floods"). Every inbound
            # frame counts, valid or not.
            if not _chat_rate_limiter.check(limiter_key):
                await websocket.close(code=4009, reason="rate_limited")
                return

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


# ── REST: history, mark-as-read, the conversation list (spec 006 G, H, I) ───


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ConversationSummary]:
    """Every conversation the caller participates in, as buyer or as seller
    (spec 006 I1-I2) — caller-scoped in the join itself, not a post-filter."""
    rows = session.exec(
        select(Conversation, Listing)
        .join(Listing, Listing.id == Conversation.listing_id)
        .where(or_(Conversation.buyer_id == user.id, Listing.owner_id == user.id))
    ).all()

    summaries: list[ConversationSummary] = []
    for conversation, listing in rows:
        is_seller = listing.owner_id == user.id
        counterpart_id = conversation.buyer_id if is_seller else listing.owner_id
        counterpart = session.get(User, counterpart_id)
        last_read = (
            conversation.seller_last_read_at if is_seller else conversation.buyer_last_read_at
        )

        unread_query = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation.id, Message.sender_id != user.id
        )
        if last_read is not None:
            unread_query = unread_query.where(Message.created_at > last_read)
        unread_count = session.exec(unread_query).one()

        last_message_at = session.exec(
            select(Message.created_at)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        ).first()

        summaries.append(
            ConversationSummary(
                id=conversation.id,
                listing_id=listing.id,
                listing_headline=listing.headline,
                counterpart_display_name=counterpart.display_name if counterpart else None,
                unread_count=unread_count,
                last_message_at=last_message_at,
            )
        )
    return summaries


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def get_conversation_messages(
    conversation: Conversation = Depends(require_conversation_member),
    before: int | None = None,
    limit: int = Query(
        default=settings.chat_history_page_limit, ge=1, le=settings.chat_history_page_limit
    ),
    session: Session = Depends(get_session),
) -> list[Message]:
    """The most recent page, newest first; `before` walks further back
    (spec 006 G1-G2). `limit`'s ceiling is a boundary rule, not a runtime
    clamp (G5) — the same discipline M4's `ListingQuery` uses."""
    query = select(Message).where(Message.conversation_id == conversation.id)
    if before is not None:
        query = query.where(Message.id < before)
    query = query.order_by(Message.id.desc()).limit(limit)
    return session.exec(query).all()


@router.post("/conversations/{conversation_id}/read", status_code=204)
def mark_conversation_read(
    conversation: Conversation = Depends(require_conversation_member),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """Stamp the caller's own `*_last_read_at` (spec 006 H2) — `require_conversation_member`
    already proved the caller is exactly one of these two roles, so no second
    role lookup is needed here."""
    if user.id == conversation.buyer_id:
        conversation.buyer_last_read_at = _utcnow()
    else:
        conversation.seller_last_read_at = _utcnow()
    session.add(conversation)
    session.commit()
