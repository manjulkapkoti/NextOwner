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
from .errors import Forbidden, NotFound, Unauthorized
from .models import Listing, User
from .security import decode_access_token


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise Unauthorized("Not authenticated")
    token = auth[len("Bearer ") :]

    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Token expired", code="token_expired") from None
    except jwt.InvalidTokenError:
        # covers bad signature, alg:none / algorithm confusion, malformed tokens.
        # `from None` so JWT internals never chain into a traceback.
        raise Unauthorized("Invalid token") from None

    sub = claims.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise Unauthorized("Invalid token") from None

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


def get_owned_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Listing:
    """Trust boundary for owner-scoped listing routes.

    Returns **404** for both "doesn't exist" and "exists but not yours" — the two
    are deliberately indistinguishable, so an unpublished draft's existence is
    never confirmed to a non-owner (no enumeration; spec 002 decision).
    """
    listing = session.get(Listing, listing_id)
    if listing is None or listing.owner_id != user.id:
        raise NotFound("Listing not found")
    return listing
