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
from sqlmodel import Session, select

from ..config import ALLOWED_UPLOAD_TYPES, settings
from ..db import get_session
from ..errors import InvalidTransition, NotFound, PayloadTooLarge, UnsupportedMediaType
from ..models import Listing, ListingDocument, ListingPrivate, User
from ..permissions import get_current_user, get_owned_listing
from ..schemas import (
    DocumentRead,
    ListingCreate,
    ListingRead,
    ListingSummary,
    ListingUpdate,
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
) -> list[Listing]:
    return list(session.exec(select(Listing).where(Listing.owner_id == user.id)).all())


@router.get("/listings/{listing_id}", response_model=ListingRead)
def get_listing(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> ListingRead:
    return _to_read(listing, session.get(ListingPrivate, listing.id))


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
    # Editing a live listing sends it back through curation (no bait-and-switch).
    if listing.status == "live":
        listing.status = "pending_review"
    session.add(listing)
    session.add(private)
    session.commit()
    session.refresh(listing)
    return _to_read(listing, private)


# ── Lifecycle transitions ────────────────────────────────────────────────────

def _transition(listing: Listing, allowed_from: set[str], to: str, session: Session) -> Listing:
    if listing.status not in allowed_from:
        raise InvalidTransition(f"Cannot go from {listing.status!r} to {to!r}")
    listing.status = to
    session.add(listing)
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
    _transition(listing, {"paused"}, "live", session)    # no re-review — not a content change
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
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> Response:
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
