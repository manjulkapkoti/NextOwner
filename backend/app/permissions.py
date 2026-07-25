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

from typing import Literal

import jwt
from fastapi import Depends, Request
from sqlmodel import Session, select

from .db import get_session
from .errors import Forbidden, InvalidTransition, NotFound, Unauthorized
from .models import (
    AccessRequest,
    Conversation,
    Listing,
    Notification,
    Offer,
    SavedSearch,
    User,
)
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


def conversation_role_for(session: Session, conversation: Conversation, user: User) -> str | None:
    """Trust boundary logic for chat (M6, spec 006), shared by two callers
    that can't both use `Depends`: `require_conversation_member` below (REST,
    raises) and the WebSocket handshake (`routers/chat.py`, which must
    `close()` the socket rather than let an `AppError` propagate somewhere a
    WebSocket has no JSON response to render it into).

    A deliberate 5-line duplicate of `require_private_access`'s "approved
    access" query (spec 006 plan.md), not a refactor of it — M6 must not be
    able to introduce a regression in M5's crown-jewel gate by editing it.

    The owner of the conversation's listing always passes, unconditionally
    (mirrors D1 on the NDA gate). The buyer passes **only if** an `approved`
    `AccessRequest` for this exact `(listing, buyer)` pair exists **right
    now** — re-checked live on every call, not inferred from the conversation
    row's mere existence, which is what makes F1-F3 (revocation applying
    live, REST included) possible. Returns `None` for everyone else,
    uniformly (spec 006 D2/S4) — never distinguishes "no such conversation"
    from "not yours."
    """
    listing = session.get(Listing, conversation.listing_id)
    if listing is not None and listing.owner_id == user.id:
        return "seller"
    if user.id == conversation.buyer_id:
        approved = session.exec(
            select(AccessRequest).where(
                AccessRequest.listing_id == conversation.listing_id,
                AccessRequest.buyer_id == user.id,
                AccessRequest.status == "approved",
            )
        ).first()
        if approved is not None:
            return "buyer"
    return None


def require_conversation_member(
    conversation_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Conversation:
    """REST wrapper around `conversation_role_for` — the chat history and
    read-receipt endpoints' trust boundary (spec 006 G3, H4)."""
    conversation = session.get(Conversation, conversation_id)
    if conversation is not None and conversation_role_for(session, conversation, user) is not None:
        return conversation
    # One raise for every refusal — missing, foreign, or revoked — mirroring
    # `require_request_decider`'s reasoning: a conversation id carries no
    # secret an unpublished listing would (D2), so this boundary never
    # distinguishes "doesn't exist" from "not yours anymore."
    raise Forbidden("You may not access this conversation", code="not_a_conversation_member")


def require_approved_buyer(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Listing:
    """Trust boundary: may this caller open an offer on this listing? (M7,
    spec 007 A1-A8, D5).

    Mirrors `create_access_request`'s existing ordering exactly:

    1. Listing missing, or never published and caller isn't the owner → 404
       (D5, spec 005 D1) — an unpublished draft's existence stays a secret.
    2. Caller is the owner → 403 (self-dealing, A4) — they already have the
       data room; an offer on your own listing is meaningless.
    3. No **approved** `AccessRequest` for `(listing, caller)` → 403
       `nda_access_required` (A2). **Deliberately the same query
       `require_private_access` runs, duplicated rather than reused** — the
       same reason `conversation_role_for` duplicates it at M6: this boundary
       must not be able to regress M5's crown-jewel gate by editing it.
    4. `listing.status != "live"` → 409 `listing_not_live` (A3).

    Returns the `Listing`. The D7 "one active offer" check and mass-assignment
    defense (A6) are the endpoint's own job, not the gate's — D7 is a fact
    about *offers*, not about this listing/buyer pair's eligibility to
    negotiate at all.
    """
    listing = session.get(Listing, listing_id)
    if listing is None or (listing.published_at is None and listing.owner_id != user.id):
        raise NotFound("Listing not found")
    if listing.owner_id == user.id:
        raise Forbidden("You already have access to your own listing")

    granted = session.exec(
        select(AccessRequest).where(
            AccessRequest.listing_id == listing_id,
            AccessRequest.buyer_id == user.id,
            AccessRequest.status == "approved",
        )
    ).first()
    if granted is None:
        raise Forbidden("NDA access not granted", code="nda_access_required")

    if listing.status != "live":
        raise InvalidTransition("Listing is not live", code="listing_not_live")
    return listing


def offer_role_for(session: Session, offer: Offer, user: User) -> Literal["buyer", "seller"] | None:
    """Trust boundary logic for offers (M7, spec 007), named and shaped after
    M6's `conversation_role_for` on purpose: two callers need a *role*, not a
    boolean, and both need to reason about it before choosing which action is
    theirs to take (accept/decline/counter vs. withdraw).

    Loads the offer's listing; the owner is always `"seller"`. Otherwise,
    `user.id == offer.buyer_id` is `"buyer"`. Anyone else is `None`, uniformly
    (D5) — never distinguishes "no such offer" from "not yours."

    **Does not** re-check approved access here — an offer, once it exists, is
    decided by the two parties named on it; approval already gated its
    *creation* (`require_approved_buyer`), and re-deriving it here would let a
    later revocation silently invalidate a pending offer with no criterion
    asking for that (out of scope).
    """
    listing = session.get(Listing, offer.listing_id)
    if listing is not None and listing.owner_id == user.id:
        return "seller"
    if user.id == offer.buyer_id:
        return "buyer"
    return None


def require_offer_party(
    offer_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> tuple[Offer, str]:
    """REST wrapper around `offer_role_for` — every decision/withdraw route's
    trust boundary (M7, spec 007 B/C/D).

    Loads the `Offer` (`None` → `Forbidden`, never `NotFound` — D5 mirrors
    `require_request_decider`'s uniform-403 reasoning: an offer id carries no
    secret an unpublished listing would). Raises `Forbidden` for anyone
    `offer_role_for` does not recognize; otherwise returns `(offer, role)` so
    the caller (the router) can apply the bilateral rule the gate itself does
    not decide (accept/decline/counter vs. withdraw).
    """
    offer = session.get(Offer, offer_id)
    role = offer_role_for(session, offer, user) if offer is not None else None
    if offer is None or role is None:
        # One raise for every refusal — missing, foreign, or orphaned — so the
        # cases cannot drift into distinguishable responses (S5).
        raise Forbidden("You may not act on this offer")
    return offer, role


def get_owned_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Notification:
    """Trust boundary: is this notification the caller's own? (M8, spec E5/S8)

    Returns **404 for both** "no such id" and "exists but not yours", the same
    choice `get_owned_listing` makes below and for the same reason: this is the
    caller's own inbox, so the two cases must be indistinguishable or the id
    space becomes an oracle for how much traffic other users are getting (S8).

    The contrast with `require_request_decider`'s uniform *403* is deliberate
    and both obey `security.md` §1.4's real rule — *be consistent within a
    boundary*. They differ in which uniform answer is safe: an access-request
    id carries no secret, so "you may not act on this" is honest there; a
    notification id is only ever meaningful to one person, so "not found" is
    the truthful answer to everyone else.
    """
    notification = session.get(Notification, notification_id)
    if notification is None or notification.recipient_id != user.id:
        raise NotFound("Notification not found")
    return notification


def get_owned_saved_search(
    saved_search_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SavedSearch:
    """Trust boundary: is this saved search the caller's own? (M8, spec A4)

    Same 404-for-both shape as `get_owned_notification` above, same reasoning —
    a saved search is a private artifact of one account.
    """
    saved_search = session.get(SavedSearch, saved_search_id)
    if saved_search is None or saved_search.user_id != user.id:
        raise NotFound("Saved search not found")
    return saved_search


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
