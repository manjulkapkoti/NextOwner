"""Chat fan-out — behind a swappable port (horizontal-scale blocker #3).

Shaped like `ratelimit.py`'s `RateLimiterBackend`/`InMemoryRateLimiterBackend`
split, this codebase's existing precedent for "per-instance state behind a
swappable interface" (`design_implementation.md` § Horizontal scale). The
in-process registry is the correct MVP implementation; it is **per-instance
state**, so behind a load balancer, a buyer on instance A and a seller on
instance B never see each other's messages — no error, just a silently broken
product (`milestones.md` § Scope fold-ins → M6). Swapping in a pub/sub
backend (Redis, Postgres `LISTEN/NOTIFY`) later means constructing the
module-level `chat_broker` differently, not editing the WebSocket handler or
`access.py`'s revoke endpoint — neither ever touches a socket directly.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import WebSocket


class ChatBroker(Protocol):
    """The seam. A pub/sub-backed implementation exposes the same four methods."""

    def register(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None: ...
    def unregister(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None: ...
    async def publish(self, conversation_id: int, payload: dict) -> None: ...
    async def close_user(
        self, conversation_id: int, user_id: int, code: int, reason: str
    ) -> None: ...


class InMemoryChatBroker:
    """`{conversation_id: {user_id: {sockets}}}`. Single-instance only, by
    construction — correct for the MVP, fatal behind a load balancer."""

    def __init__(self) -> None:
        self._sockets: dict[int, dict[int, set[WebSocket]]] = {}

    def register(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None:
        self._sockets.setdefault(conversation_id, {}).setdefault(user_id, set()).add(websocket)

    def unregister(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None:
        users = self._sockets.get(conversation_id)
        if not users:
            return
        sockets = users.get(user_id)
        if sockets:
            sockets.discard(websocket)
            if not sockets:
                users.pop(user_id, None)
        if not users:
            self._sockets.pop(conversation_id, None)

    async def publish(self, conversation_id: int, payload: dict) -> None:
        """Fan out to every registered socket for this conversation, sender
        included (spec 006 D4/C4) — one code path renders every message."""
        users = self._sockets.get(conversation_id, {})
        for sockets in list(users.values()):
            for websocket in list(sockets):
                try:
                    await websocket.send_json(payload)
                except Exception:
                    pass  # a dead socket is cleaned up by its own disconnect handler

    async def close_user(self, conversation_id: int, user_id: int, code: int, reason: str) -> None:
        """Force-close every live socket a user has open on this conversation
        (spec 006 F1 — revocation applying live)."""
        sockets = self._sockets.get(conversation_id, {}).get(user_id, set())
        for websocket in list(sockets):
            try:
                await websocket.close(code=code, reason=reason)
            except Exception:
                pass


chat_broker: ChatBroker = InMemoryChatBroker()
