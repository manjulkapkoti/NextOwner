"""Permission gates — one function per trust boundary (constitution Article 2 #1).

This is *the* place privilege is decided. Every non-public route depends on one
of these. They are deliberately small and boring; boring is the point.

- `get_current_user` — trust boundary #1: proves *who* you are from the JWT, then
  re-loads you from the DB (so a revoked/anonymized user is rejected, and roles
  are never trusted from the token).
- `require_admin` — trust boundary #2: `is_admin` is read from the DB row, never
  from a token claim.
"""

from __future__ import annotations

import jwt
from fastapi import Depends, Request
from sqlmodel import Session

from .db import get_session
from .errors import Forbidden, Unauthorized
from .models import User
from .security import decode_access_token


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise Unauthorized("Not authenticated")
    token = auth[len("Bearer ") :]

    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Token expired", code="token_expired")
    except jwt.InvalidTokenError:
        # covers bad signature, alg:none / algorithm confusion, malformed tokens
        raise Unauthorized("Invalid token")

    sub = claims.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise Unauthorized("Invalid token")

    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        # identity re-checked against the DB — a since-anonymized user's live
        # token stops working (C5)
        raise Unauthorized("Invalid token")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:                       # read from the DB row, not the token
        raise Forbidden("Admin access required")
    return user
