"""Access requests — the per-listing half of the NDA gate (M5, FR-13/FR-14).

Every transition of `accessrequest.status` happens in **this file**, for the same
reason M3 kept listing curation beside the rest of the listing state machine: a
state machine with a second implementation in another file is a state machine
with a hole (Article 2 #3).

The states and their only legal moves:

    requested ──approve──▶ approved ──revoke──▶ revoked
        └──────deny──────▶ denied

`denied` and `revoked` are terminal, and the unique constraint on
`(listing_id, buyer_id)` means a buyer cannot start over — re-granting is
deliberately post-MVP (owner-approved 2026-07-20; FR-13 in
`docs/requirements.md` names what its implementer inherits).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from ..db import get_session
from ..errors import Conflict, Forbidden, InvalidTransition, NotFound
from ..models import AccessRequest, AccessRequestEvent, Listing, User, _utcnow
from ..permissions import get_current_user, require_request_decider, require_signed_nda
from ..schemas import AccessRequestRead

router = APIRouter(tags=["access"])


def _record(session: Session, request: AccessRequest, actor: User, action: str,
            from_status: str, to_status: str) -> None:
    """Append one audit row for a **completed** transition (spec 005 D6).

    Never called for an attempt that was refused — the log records what happened,
    not what was tried (M3's rule for `listingevent`, kept identical here).
    """
    session.add(
        AccessRequestEvent(
            access_request_id=request.id,
            actor_id=actor.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
        )
    )


@router.post("/listings/{listing_id}/access-request", response_model=AccessRequestRead,
             status_code=201)
def create_access_request(
    listing_id: int,
    user: User = Depends(require_signed_nda),
    session: Session = Depends(get_session),
) -> AccessRequest:
    """A signed buyer asks the seller for the data room (spec 005 B1-B7).

    Order of checks is the security property:

    1. `require_signed_nda` runs first (B2) — an unsigned user cannot even learn
       whether the listing exists.
    2. A listing that has **never been published** is still a secret, so a
       non-owner gets **404**, identical to one that does not exist (B6, spec
       D1). A *published* listing is public knowledge, so its refusals can be
       honest 403s further down.
    3. The owner is refused (B5). They already have access — a self-request
       would be a self-approval path (`security.md` §6 self-dealing).

    There is **no request body**: `buyer_id` comes from the JWT, `status` and
    `created_at` from the server (B4, Article 2 #4). A body a function does not
    declare is a body FastAPI never reads, which is the cheapest possible
    defence against mass assignment.
    """
    listing = session.get(Listing, listing_id)
    if listing is None or (listing.published_at is None and listing.owner_id != user.id):
        raise NotFound("Listing not found")
    if listing.owner_id == user.id:
        raise Forbidden("You already have access to your own listing")

    access_request = AccessRequest(listing_id=listing_id, buyer_id=user.id, status="requested")
    session.add(access_request)
    try:
        # The unique constraint is the authority on "one request per pair", not
        # a prior SELECT — a check-then-insert would race two concurrent
        # requests into two rows (security.md §6 race conditions).
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(
            "An access request for this listing already exists",
            code="access_request_exists",
        ) from None

    session.refresh(access_request)
    # No audit row here, deliberately. The event table exists to preserve values
    # a later transition would **overwrite** — `decided_at`/`decided_by_id` are
    # rewritten by every decision, which is why revocation could erase when
    # access was granted (spec 005 D6). `created_at` is never rewritten, so the
    # request's own row is already a lossless record of when it was made, and a
    # `requested` event would be a second copy of a fact that cannot drift.
    return access_request


# ── The seller's decision (spec 005 C1-C11) ──────────────────────────────────
#
# One legal move per action, declared as data rather than as three hand-written
# `if` chains. A transition table is checkable by eye — the reviewer can see the
# whole state machine at once and confirm nothing else is reachable, which is
# exactly the property M3's bypass turned out not to have.
_TRANSITIONS: dict[str, tuple[str, str]] = {
    "approve": ("requested", "approved"),
    "deny": ("requested", "denied"),
    "revoke": ("approved", "revoked"),
}


def _decide(
    action: str,
    access_request: AccessRequest,
    seller: User,
    session: Session,
) -> AccessRequest:
    """Apply one decision, or refuse it. The only writer of `accessrequest.status`.

    The status guard is re-read from the row inside this function rather than
    trusted from anything the caller sent (S5), and an illegal move is a 409 —
    never a silent no-op, which would leave the seller believing they had acted.
    """
    required_from, to_status = _TRANSITIONS[action]
    if access_request.status != required_from:
        raise InvalidTransition(
            f"Cannot {action} a request that is {access_request.status}",
            code="invalid_access_transition",
        )

    from_status = access_request.status
    access_request.status = to_status
    access_request.decided_at = _utcnow()          # server clock, never the body
    access_request.decided_by_id = seller.id       # server identity, never the body
    session.add(access_request)
    _record(session, access_request, seller, to_status, from_status, to_status)
    session.commit()
    session.refresh(access_request)
    return access_request


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequestRead)
def approve_access_request(
    access_request: AccessRequest = Depends(require_request_decider),
    seller: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AccessRequest:
    """Grant the data room. **The only door to `ListingPrivate` besides ownership.**"""
    return _decide("approve", access_request, seller, session)


@router.post("/access-requests/{request_id}/deny", response_model=AccessRequestRead)
def deny_access_request(
    access_request: AccessRequest = Depends(require_request_decider),
    seller: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AccessRequest:
    return _decide("deny", access_request, seller, session)


@router.post("/access-requests/{request_id}/revoke", response_model=AccessRequestRead)
def revoke_access_request(
    access_request: AccessRequest = Depends(require_request_decider),
    seller: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AccessRequest:
    """Take back access already granted (M5 fold-in).

    Legal only from `approved` — revoking a request that was never granted is a
    409, not a quiet success, because the two mean different things to a seller
    looking at their queue.
    """
    return _decide("revoke", access_request, seller, session)
