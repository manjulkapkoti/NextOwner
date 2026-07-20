"""Listings router — the seller's listing builder + uploads (M2).

`owner_id` and `status` are always server-derived (Article 2 #4); every
`{listing_id}` route goes through `get_owned_listing` (404 for not-yours). The
status state machine lives here — transitions happen only inside these endpoints
and illegal moves are 409. Uploads are treated as hostile: type+size whitelist,
server-generated filename, path confinement in the storage adapter.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy import Numeric, cast, func, or_
from sqlmodel import Session, select

from ..config import ALLOWED_UPLOAD_TYPES, settings
from ..db import get_session
from ..errors import InvalidTransition, NotFound, PayloadTooLarge, UnsupportedMediaType
from ..models import Listing, ListingDocument, ListingEvent, ListingPrivate, User, _utcnow
from ..permissions import (
    get_current_user,
    get_owned_listing,
    require_admin,
    require_private_access,
)
from ..schemas import (
    DocumentRead,
    ListingCreate,
    ListingPage,
    ListingPublic,
    ListingQuery,
    ListingRead,
    ListingSummary,
    ListingUpdate,
    RejectRequest,
)
from ..storage import LocalDiskStorageBackend

router = APIRouter(tags=["listings"])

# One storage backend per process — the swappable seam (horizontal-scale #2).
_storage = LocalDiskStorageBackend(settings.upload_dir)

_ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg"}
_EDIT_LOCKED = {"closed", "sold"}     # terminal — can't edit or re-transition
_UPLOAD_CHUNK = 1024 * 1024           # 1 MB read chunk

# Magic bytes — the actual content must match its declared type, so a whitelisted
# content-type can't smuggle a different file (defense that matters at M5, when a
# buyer downloads a seller's doc).
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


def _to_read(listing: Listing, private: ListingPrivate | None) -> ListingRead:
    return ListingRead(
        id=listing.id,
        owner_id=listing.owner_id,
        status=listing.status,
        type=listing.type,
        headline=listing.headline,
        description=listing.description,
        asking_price=listing.asking_price,
        ttm_revenue=listing.ttm_revenue,
        ttm_profit=listing.ttm_profit,
        mrr=listing.mrr,
        churn_pct=listing.churn_pct,
        customers=listing.customers,
        created_at=listing.created_at,
        published_at=listing.published_at,
        company_name=private.company_name if private else None,
        website_url=private.website_url if private else None,
        detailed_financials=private.detailed_financials if private else None,
    )


# ── Public marketplace (M4) ──────────────────────────────────────────────────
#
# The first routes in the project an anonymous stranger may call. They have no
# permission dependency **by design** — and because there is no gate, two other
# controls are the entire boundary:
#
#   1. `WHERE status = 'live'`  — nothing unapproved is ever public
#   2. the `ListingPublic` schema — identity fields cannot leak
#
# `_to_public` takes a `Listing` and nothing else, so `ListingPrivate` is not
# even in scope at the call site: there is no private row here to leak from.


def _escape_like(term: str) -> str:
    """Neutralize LIKE metacharacters in user input.

    Parameterization stops SQL injection but says nothing about *wildcards*: a
    bound parameter of `%` is still a valid LIKE pattern matching every row, and
    `_` matches any single character. Escaping them (backslash first, or we'd
    double-escape our own escapes) makes the search term literal, which is what
    a user typing `%` means (spec B10).
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_public(listing: Listing) -> ListingPublic:
    return ListingPublic(
        id=listing.id,
        type=listing.type,
        headline=listing.headline,
        description=listing.description,
        asking_price=listing.asking_price,
        ttm_revenue=listing.ttm_revenue,
        ttm_profit=listing.ttm_profit,
        mrr=listing.mrr,
        churn_pct=listing.churn_pct,
        customers=listing.customers,
        published_at=listing.published_at,
    )


@router.get("/listings", response_model=ListingPage)
def browse_listings(
    query: ListingQuery = Depends(),
    session: Session = Depends(get_session),
) -> ListingPage:
    """Public browse (spec 004 A1-A11, B1-B13). No auth — and no widening if a
    token is present (S8): this function never reads the caller's identity at
    all."""
    conditions = [Listing.status == "live"]

    # Truthiness, not `is not None`, so `?type=` (an empty value, which is how a
    # cleared dropdown serializes) means "no filter" rather than "match the
    # empty string" — matching `q`'s handling below.
    if query.type:
        conditions.append(Listing.type == query.type)

    # Money is stored as TEXT (the `Money` TypeDecorator keeps Decimal lossless),
    # so a bare SQL comparison would be **lexicographic**: '90000.00' > '200000.00'
    # is true as strings and false as money. Cast for the comparison. Only the
    # boundary check goes through NUMERIC — the stored and returned values are
    # still exact Decimals, so this does not reintroduce float money.
    if query.min_price is not None:
        conditions.append(cast(Listing.asking_price, Numeric(14, 2)) >= query.min_price)
    if query.max_price is not None:
        conditions.append(cast(Listing.asking_price, Numeric(14, 2)) <= query.max_price)
    if query.min_profit is not None:
        conditions.append(cast(Listing.ttm_profit, Numeric(14, 2)) >= query.min_profit)

    if query.q:
        # Public text only (spec D4/B8). Reaching into `ListingPrivate` here
        # would turn the search box into an identity oracle: a caller could
        # confirm "SecretCo" exists without the field ever being rendered.
        term = f"%{_escape_like(query.q)}%"
        conditions.append(
            or_(
                Listing.headline.ilike(term, escape="\\"),
                Listing.description.ilike(term, escape="\\"),
            )
        )

    total = session.exec(
        select(func.count()).select_from(Listing).where(*conditions)
    ).one()

    rows = session.exec(
        select(Listing)
        .where(*conditions)
        # `id` breaks ties so the ordering is total, not just sorted — two
        # listings approved in the same clock tick must not swap between pages
        # and hide a row from a paginating caller.
        .order_by(Listing.published_at.desc(), Listing.id.desc())
        .limit(query.limit)
        .offset(query.offset)
    ).all()

    return ListingPage(
        items=[_to_public(row) for row in rows],
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


# ── Create / read ────────────────────────────────────────────────────────────

@router.post("/listings", response_model=ListingRead, status_code=201)
def create_listing(
    body: ListingCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ListingRead:
    listing = Listing(
        owner_id=user.id,                 # from the JWT, never the body
        status="draft",                   # server-set — no self-publishing
        type=body.type,
        headline=body.headline,
        description=body.description,
        asking_price=body.asking_price,
        ttm_revenue=body.ttm_revenue,
        ttm_profit=body.ttm_profit,
        mrr=body.mrr,
        churn_pct=body.churn_pct,
        customers=body.customers,
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)
    private = ListingPrivate(
        listing_id=listing.id,
        company_name=body.company_name,
        website_url=body.website_url,
        detailed_financials=body.detailed_financials,
    )
    session.add(private)
    session.commit()
    return _to_read(listing, private)


@router.get("/my/listings", response_model=list[ListingSummary])
def my_listings(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ListingSummary]:
    """The seller's dashboard. A rejected listing carries the admin's reason
    (spec C6), read from the latest rejection event rather than a column on the
    listing — one home per fact."""
    listings = list(session.exec(select(Listing).where(Listing.owner_id == user.id)).all())

    reasons: dict[int, str] = {}
    rejected = [listing.id for listing in listings if listing.status == "rejected"]
    if rejected:
        events = session.exec(
            select(ListingEvent)
            .where(ListingEvent.listing_id.in_(rejected))    # noqa: E501
            .where(ListingEvent.action == "rejected")
            .order_by(ListingEvent.id)
        ).all()
        for event in events:            # ordered by id, so the last write wins
            if event.reason is not None:
                reasons[event.listing_id] = event.reason

    return [
        ListingSummary(
            id=listing.id,
            headline=listing.headline,
            status=listing.status,
            asking_price=listing.asking_price,
            created_at=listing.created_at,
            rejection_reason=reasons.get(listing.id),
        )
        for listing in listings
    ]


@router.get("/my/listings/{listing_id}", response_model=ListingRead)
def get_my_listing(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    """The owner's full view (spec 004 D1-D3).

    **Moved** from `GET /listings/{listing_id}` at M4 so the public browse could
    take the canonical path (spec 004 decision D1). Semantics are unchanged:
    `get_owned_listing` still returns 404 — never 403 — for someone else's
    listing, so a draft's existence is never confirmed.
    """
    return _to_read(listing, session.get(ListingPrivate, listing.id))


@router.get("/listings/{listing_id}", response_model=ListingPublic)
def get_public_listing(
    listing_id: int,
    session: Session = Depends(get_session),
) -> ListingPublic:
    """The anonymous card (spec 004 C1-C4). Public — no auth.

    A non-`live` listing and a missing one raise the **same** 404 with the same
    message, so this route is not an existence oracle: an unapproved draft can't
    be probed for (C3). The owner is not special-cased — the public route never
    serves unapproved content, not even to the person who wrote it (C2).
    """
    listing = session.get(Listing, listing_id)
    if listing is None or listing.status != "live":
        raise NotFound("Listing not found")
    return _to_public(listing)


@router.put("/listings/{listing_id}", response_model=ListingRead)
def update_listing(
    body: ListingUpdate,
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    if listing.status in _EDIT_LOCKED:
        raise InvalidTransition("A closed listing can't be edited")
    private = session.get(ListingPrivate, listing.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in ("company_name", "website_url", "detailed_financials"):
            setattr(private, field, value)
        else:
            setattr(listing, field, value)
    # Editing publicly-visible content sends it back through curation (no
    # bait-and-switch). `paused` counts: a paused listing is one `resume` away
    # from being public again, so an edit made while paused would otherwise
    # reach buyers without a second admin decision — pause → edit → resume was
    # a working curation bypass until M3 (spec E5, found by the independent
    # security review). `draft` and `pending_review` are excluded because
    # neither is publicly visible and `pending_review` is already in the queue.
    if listing.status in ("live", "paused"):
        listing.status = "pending_review"
    session.add(listing)
    session.add(private)
    session.commit()
    session.refresh(listing)
    return _to_read(listing, private)


# ── Lifecycle transitions ────────────────────────────────────────────────────

def _transition(
    listing: Listing,
    allowed_from: set[str],
    to: str,
    session: Session,
    *,
    actor: User | None = None,
    action: str | None = None,
    reason: str | None = None,
    set_fields: dict[str, object] | None = None,
) -> Listing:
    """Move a listing between states, and audit it if an actor is given.

    The status check comes first, so an illegal transition raises before
    anything is written — that is what makes "no audit row for a failed
    attempt" (spec D3) a property of the code rather than a promise. The log
    records what happened, not what was tried.

    `actor`/`action` are optional because seller-driven transitions (submit,
    pause) are not audited at M3: FR-21 asks for an audit of *curation*
    decisions. When the seller lifecycle needs its own trail, pass an actor
    here rather than adding a second logging path.
    """
    from_status = listing.status
    if from_status not in allowed_from:
        raise InvalidTransition(f"Cannot go from {from_status!r} to {to!r}")
    listing.status = to
    # Applied only after the guard passed, so a 409 leaves the row untouched —
    # `published_at` must never be stamped on a listing that did not go live.
    for field, value in (set_fields or {}).items():
        setattr(listing, field, value)
    session.add(listing)

    if actor is not None and action is not None:
        session.add(
            ListingEvent(
                listing_id=listing.id,
                actor_id=actor.id,          # from the JWT, never the body
                action=action,
                from_status=from_status,
                to_status=to,
                reason=reason,
            )
        )

    session.commit()
    session.refresh(listing)
    return listing


@router.post("/listings/{listing_id}/submit", response_model=ListingRead)
def submit_listing(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    _transition(listing, {"draft"}, "pending_review", session)
    return _to_read(listing, session.get(ListingPrivate, listing.id))


@router.post("/listings/{listing_id}/pause", response_model=ListingRead)
def pause_listing(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    _transition(listing, {"live"}, "paused", session)
    return _to_read(listing, session.get(ListingPrivate, listing.id))


@router.post("/listings/{listing_id}/resume", response_model=ListingRead)
def resume_listing(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    # Safe without re-review only because an edit while paused already sent the
    # listing back to `pending_review` (see `update_listing`) — so anything
    # resumable here is content an admin has approved. That invariant is the
    # whole reason this route can skip curation; spec E5 guards it.
    _transition(listing, {"paused"}, "live", session)
    return _to_read(listing, session.get(ListingPrivate, listing.id))


@router.post("/listings/{listing_id}/close", response_model=ListingRead)
def close_listing(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    _transition(listing, {"draft", "pending_review", "live", "paused"}, "closed", session)
    return _to_read(listing, session.get(ListingPrivate, listing.id))


# ── Documents (hostile input) ────────────────────────────────────────────────

@router.post("/listings/{listing_id}/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    listing: Listing = Depends(get_owned_listing),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ListingDocument:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if file.content_type not in ALLOWED_UPLOAD_TYPES or ext not in _ALLOWED_EXTS:
        raise UnsupportedMediaType("Only PDF, PNG, or JPEG documents are allowed")
    # Stream with a hard ceiling — never materialize more than one chunk over the
    # limit, so a huge upload can't exhaust memory (the DoS the appsec review
    # caught). The Content-Length middleware is the pre-parse outer guard.
    buf = bytearray()
    while chunk := await file.read(_UPLOAD_CHUNK):
        buf.extend(chunk)
        if len(buf) > settings.max_upload_bytes:
            raise PayloadTooLarge("File exceeds the maximum upload size")
    data = bytes(buf)
    # The bytes must actually match the declared type (not just its header).
    if not any(data.startswith(sig) for sig in _MAGIC[file.content_type]):
        raise UnsupportedMediaType("File content does not match its declared type")
    suffix = ALLOWED_UPLOAD_TYPES[file.content_type]
    key = _storage.save(listing.id, data, suffix)        # server-generated name; path confined
    doc = ListingDocument(
        listing_id=listing.id,
        storage_key=key,
        original_filename=os.path.basename(file.filename or "upload"),
        content_type=file.content_type,
        size_bytes=len(data),
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.get("/listings/{listing_id}/documents/{doc_id}")
def download_document(
    doc_id: int,
    listing: Listing = Depends(require_private_access),
    session: Session = Depends(get_session),
) -> Response:
    """Serve a data-room document (M2 upload, M5 gate).

    **The dependency is the entire M5 change to this route** — `get_owned_listing`
    became `require_private_access`, and nothing in the body moved. That is the
    payoff of one-function-per-trust-boundary (Article 2 #1): the rule "owner, or
    an approved buyer, and nobody else" is written once and *reused* here, rather
    than reimplemented beside the file-serving code where the two copies could
    drift apart. Spec 005 E1-E5 assert this route now answers exactly as the
    private-data route does.
    """
    doc = session.get(ListingDocument, doc_id)
    if doc is None or doc.listing_id != listing.id:
        raise NotFound("Document not found")
    data = _storage.open(doc.storage_key)
    # Sanitize the download name (strip path + CR/LF) — never trust the stored
    # original filename in a header (traversal / header-injection).
    safe = os.path.basename(doc.original_filename)
    safe = safe.replace('"', "").replace("\r", "").replace("\n", "")[:200]
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={"Content-Disposition": f'attachment; filename="{safe or "document"}"'},
    )


# ── Curation (M3) — admin only ───────────────────────────────────────────────
#
# These live here, beside the rest of the state machine, rather than in the
# admin router: `listing.status` changes in exactly one place (Article 2 #3).
# A second implementation in another file is how a state machine grows a hole.


def _pending_listing(listing_id: int, session: Session) -> Listing:
    """Fetch for curation. Unlike `get_owned_listing`, a 404 here is safe to be
    literal — the caller is already an authenticated admin, so there is no
    existence oracle to protect."""
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise NotFound("Listing not found")
    return listing


@router.post("/listings/{listing_id}/approve", response_model=ListingRead)
def approve_listing(
    listing_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ListingRead:
    """The only path to `live` (spec B1-B5). No seller-reachable route sets it."""
    listing = _pending_listing(listing_id, session)
    _transition(
        listing,
        {"pending_review"},
        "live",
        session,
        actor=admin,
        action="approved",
        set_fields={"published_at": _utcnow()},   # server clock, never the client's
    )
    return _to_read(listing, session.get(ListingPrivate, listing.id))


@router.post("/listings/{listing_id}/reject", response_model=ListingRead)
def reject_listing(
    listing_id: int,
    body: RejectRequest,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ListingRead:
    """Reject with a reason (spec C1-C5). The reason is required by schema, so a
    blank one is a 422 at the boundary and never reaches the state machine — a
    rejection the seller cannot act on is worse than none."""
    listing = _pending_listing(listing_id, session)
    _transition(
        listing,
        {"pending_review"},
        "rejected",
        session,
        actor=admin,
        action="rejected",
        reason=body.reason.strip(),
    )
    return _to_read(listing, session.get(ListingPrivate, listing.id))
