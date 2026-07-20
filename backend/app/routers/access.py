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
from sqlmodel import Session, select

from ..db import get_session
from ..errors import Conflict, Forbidden, InvalidTransition, NotFound
from ..models import (
    AccessRequest,
    AccessRequestEvent,
    Conversation,
    Listing,
    ListingDocument,
    ListingPrivate,
    User,
    _utcnow,
)
from ..permissions import (
    get_current_user,
    get_owned_listing,
    require_private_access,
    require_request_decider,
    require_signed_nda,
)
from ..schemas import (
    AccessRequestRead,
    AccessRequestWithBuyer,
    BuyerProfile,
    DocumentRead,
    ListingPrivateRead,
)

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
        # Which constraint failed is answered by **asking the database**, not by
        # reading the driver's prose. Catching every IntegrityError as "already
        # requested" would misreport an unrelated failure — the listing row
        # disappearing between the `session.get` above and this commit is a
        # foreign-key error and a completely different situation. Never a leak,
        # but a diagnostic that lies to whoever debugs it next.
        #
        # This was a string match twice, and both versions were wrong in a way
        # only the next environment would reveal. Matching the Postgres
        # constraint name 500'd every duplicate on SQLite (caught by `test_b3`).
        # Matching both dialects' wordings still breaks when an Alembic naming
        # convention **renames** the constraint at the Postgres swap: Postgres
        # quotes the name and never the columns, so neither branch would fire.
        # A re-query has no wording to bet on and no dialect to track.
        duplicate = session.exec(
            select(AccessRequest).where(
                AccessRequest.listing_id == listing_id,
                AccessRequest.buyer_id == user.id,
            )
        ).first()
        if duplicate is None:
            raise                      # some other constraint — let it 500 honestly
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
    """Grant the data room. **The only door to `ListingPrivate` besides ownership.**

    Also creates the `Conversation` row (M6, spec 006 A1) —
    `design_implementation.md` M6 names this as approval's second effect. No
    duplicate-guard needed: the transition guard above already makes `approve`
    fire at most once per `(listing, buyer)` pair (a second attempt is `409`
    before reaching this line), and `Conversation`'s own unique constraint is
    the defense-in-depth backstop, not the only line of defense.
    """
    result = _decide("approve", access_request, seller, session)
    session.add(Conversation(listing_id=access_request.listing_id, buyer_id=access_request.buyer_id))
    session.commit()
    return result


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


# ── The data room (spec 005 D1-D10) ⭐ ────────────────────────────────────────


@router.get("/listings/{listing_id}/private", response_model=ListingPrivateRead)
def get_listing_private(
    listing: Listing = Depends(require_private_access),
    session: Session = Depends(get_session),
) -> ListingPrivate:
    """What the NDA gate unlocks (FR-15).

    Read the signature: by the time this body runs, the caller has **already**
    been proven to be the owner or an approved buyer — the endpoint does nothing
    but fetch. That is the shape `design_implementation.md` §3.6 is describing
    when it says an endpoint should read like a sentence, and it is why the gate
    can be trusted: there is no second, endpoint-local check that could disagree
    with it.
    """
    private = session.get(ListingPrivate, listing.id)
    if private is None:                     # a listing with no private row yet
        raise NotFound("Listing not found")
    return private


@router.get("/listings/{listing_id}/documents", response_model=list[DocumentRead])
def list_listing_documents(
    listing: Listing = Depends(require_private_access),
    session: Session = Depends(get_session),
) -> list[ListingDocument]:
    """The data room's file index (spec 005 E6).

    **Behind the same gate as the files themselves** — the list of what a seller
    has uploaded is itself confidential: filenames alone ("2024-tax-notice.pdf",
    "acme-holdings-cap-table.pdf") leak both identity and circumstance, so this
    cannot be a lighter boundary than the download it feeds.

    Added during M5's branch review. Without it, `GET .../documents/{doc_id}`
    was unreachable in practice: the only place a `doc_id` appeared was the
    upload response, which only the seller ever sees — so an approved buyer got
    an empty data room and user story 2 went unmet. The component test could not
    catch it because it passes `documents` in as a prop, supplying exactly what
    the real app did not.
    """
    return session.exec(
        select(ListingDocument)
        .where(ListingDocument.listing_id == listing.id)
        .order_by(ListingDocument.uploaded_at.desc(), ListingDocument.id.desc())
    ).all()


# ── The two queues (spec 005 F1-F3, G1-G3) ───────────────────────────────────


@router.get("/my/access-requests", response_model=list[AccessRequestRead])
def my_access_requests(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AccessRequest]:
    """The buyer's own requests, across every listing (M5 fold-in).

    Caller-scoped in the **query**, not in a post-filter: `buyer_id == user.id`
    is a WHERE clause, so another buyer's row is never loaded in the first place
    and cannot leak through a serialization mistake (F2).

    This is also what the buyer's UI reads to know it has a request pending after
    a page reload — the POST response only knows about the current session
    (plan.md § Frontend).
    """
    return session.exec(
        select(AccessRequest)
        .where(AccessRequest.buyer_id == user.id)
        .order_by(AccessRequest.created_at.desc(), AccessRequest.id.desc())
    ).all()


@router.get(
    "/my/listings/{listing_id}/access-requests",
    response_model=list[AccessRequestWithBuyer],
)
def listing_access_requests(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> list[AccessRequestWithBuyer]:
    """The seller's queue for one listing — who is asking, and enough to decide (FR-14).

    **Guarded by the existing `get_owned_listing`** (spec 005 D7), which is the
    whole reason the path carries the listing id instead of taking it as a query
    parameter: ownership is checked by a trust boundary that already exists and
    is already tested, rather than by a fresh comparison written here. Its
    404-for-not-yours semantics come along for free, so this route confirms no
    listing's existence to a stranger (G2).

    The buyer is projected into `BuyerProfile` — never returned as a `User`.
    A seller sees a profile, not contact details (G3).
    """
    rows = session.exec(
        select(AccessRequest, User)
        .join(User, User.id == AccessRequest.buyer_id)
        .where(AccessRequest.listing_id == listing.id)
        .order_by(AccessRequest.created_at.desc(), AccessRequest.id.desc())
    ).all()

    return [
        AccessRequestWithBuyer(
            id=request.id,
            listing_id=request.listing_id,
            status=request.status,
            created_at=request.created_at,
            decided_at=request.decided_at,
            buyer=BuyerProfile(
                display_name=buyer.display_name,
                budget=buyer.budget,
                target_industries=buyer.target_industries,
                experience=buyer.experience,
            ),
        )
        for request, buyer in rows
    ]
