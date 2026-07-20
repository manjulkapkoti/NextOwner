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
from sqlmodel import Session, select

from .db import get_session
from .errors import Forbidden, NotFound, Unauthorized
from .models import AccessRequest, Listing, User
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


def require_signed_nda(user: User = Depends(get_current_user)) -> User:
    """Trust boundary: has this user signed the one platform-wide NDA? (FR-13)

    Deliberately **separate** from `require_private_access`, even though both
    guard the same data in the end. The signature is a property of the *user*;
    the approval is a property of the *(listing, buyer) pair*. Fusing them would
    put spec criteria B2 and D3 on one code path, where a single bug takes out
    both — and the whole point of one-function-per-boundary is that a rule lives
    in exactly one place and is tested directly.
    """
    if user.nda_signed_at is None:
        raise Forbidden("Platform NDA not signed", code="nda_not_signed")
    return user


def require_request_decider(
    request_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AccessRequest:
    """Trust boundary: may this caller decide this access request? (FR-14)

    The request is authorized **through its listing** — load the row, load the
    listing it belongs to, compare that listing's owner to the caller. Fetching
    the row by id and trusting it would be the IDOR this guards against (spec
    005 S1): a seller who owns *a* listing must not be able to decide a request
    against *another* seller's listing by guessing an id.

    Admin is **not** special-cased (C8). Curation is an admin power; deciding
    who reads your data room is not. The seller alone holds this one.

    **Returns 403 for a missing row as well as a foreign one — deliberately the
    opposite choice from `get_owned_listing`'s 404-for-both above.** Both obey
    `security.md` §1.4's actual rule, which is *be consistent within a
    boundary*, and both refuse to become an existence oracle (S7: probing a real
    id you don't own and a plainly nonexistent one must be indistinguishable).
    They differ in which answer is the safe uniform one: a listing's existence is
    the secret worth hiding, so that boundary hides behind "not found"; an access
    request's id carries no such secret, and every caller who reaches here
    without ownership deserves the same "you may not act on this" regardless of
    whether the row is real.
    """
    access_request = session.get(AccessRequest, request_id)
    if access_request is not None:
        listing = session.get(Listing, access_request.listing_id)
        if listing is not None and listing.owner_id == user.id:
            return access_request
    # One raise for every refusal — missing, foreign, or orphaned — so the three
    # cases cannot drift into three distinguishable responses.
    raise Forbidden("You may not decide this access request")


def require_private_access(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Listing:
    """⭐ **THE NDA GATE.** May this caller see this listing's data room?

    The single function guarding every path to `ListingPrivate` and to the
    documents behind it (`design_implementation.md` §3.6). One function, reused
    by every route behind the boundary — so "a buyer without approved access is
    denied" exists in exactly one place, and `test_nda_gate.py` tests it there.

    **The resolution order is itself the security property:**

    1. Listing missing → 404.
    2. The **owner** always passes (D1). Their own data room needs no request.
    3. An **`approved`** request for this exact `(listing, caller)` pair passes
       (D2). Note what is *not* consulted here: `listing.status`. The gate is the
       access request, so approval survives the seller pausing or closing the
       listing (D9, spec D2) — and it will still hold when M12 marks a listing
       `sold`, which `security.md` §7 M12 requires. `revoke` is the only way to
       take access back, deliberately.
    4. Everyone else is refused — but *how* depends on whether the listing is
       public knowledge (spec 005 D1). **Never published → 404**, identical to a
       listing that does not exist, because an unapproved draft is still a
       secret and this route must not become the oracle M4's public route
       refuses to be. **Published → 403** with `nda_access_required`, which is
       not merely honest but necessary: the buyer's UI has to tell "gone" from
       "ask for access", and a 404 there would make the request-access CTA
       unbuildable.

    Steps 3 and 4 are the milestone. Everything else in M5 exists to give them
    something to check.
    """
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise NotFound("Listing not found")
    if listing.owner_id == user.id:
        return listing

    granted = session.exec(
        select(AccessRequest).where(
            AccessRequest.listing_id == listing_id,
            AccessRequest.buyer_id == user.id,
            AccessRequest.status == "approved",
        )
    ).first()
    if granted is not None:
        return listing

    if listing.published_at is None:
        raise NotFound("Listing not found")
    raise Forbidden("NDA access not granted", code="nda_access_required")


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
