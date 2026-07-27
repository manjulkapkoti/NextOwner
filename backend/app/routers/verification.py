"""Buyer verification — the manual Persona mock (M10, FR-3/FR-14/F11, spec 010).

A badge that tells a seller whether the stranger asking to read their data room
has shown proof of funds. It is the only trust signal in the product a seller
consumes about a *person* rather than about a listing (FR-14), which is why the
routes here are unusually paranoid for how little they do.

Three properties hold this together:

- **`verification_status` is server-controlled, and has no field to be assigned
  from.** The only request bodies this milestone introduces are an `UploadFile`
  and (slice 2) a `{reason}` model, so mass-assignment is impossible by schema
  rather than filtered at runtime — the same construction `ListingCreate` uses
  for `status`/`owner_id`. `ProfileUpdate`, the one route that already writes to
  `User`, does not declare these columns either (spec 010 S1).
- **Uploads are hostile, and reuse M2's seam rather than a second pipeline**
  (spec 010 D5). `uploads.read_validated_upload` is literally the function
  `POST /listings/{id}/documents` calls; `uploads.storage` is literally the
  backend it writes through. The one difference is which entity owns the key —
  a user id here, a listing id there — which is what `StorageBackend.save`'s
  first parameter has always meant.
- **The state machine changes only in this file** (Article 2 #3), the same rule
  that keeps `listing.status` inside `routers/listings.py`. A second
  implementation elsewhere is how a state machine grows a hole, so the admin
  decision routes (slice 2) belong here too rather than in `routers/admin.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session, select

from ..db import get_session
from ..errors import Conflict
from ..models import BuyerVerificationDocument, User
from ..permissions import get_current_user
from ..schemas import VerificationDocumentRead, VerificationRead
from ..uploads import display_filename, read_validated_upload, storage

router = APIRouter(tags=["verification"])

# The D1 state machine. `unverified` is the default (nothing submitted yet); a
# buyer's upload is the only buyer-initiated transition and always lands on
# `pending`; only an admin reaches `verified`/`rejected` (slice 2).
_UPLOAD_ALLOWED_FROM = {"unverified", "pending", "rejected"}


def _documents(session: Session, user_id: int) -> list[BuyerVerificationDocument]:
    """A user's submissions, oldest first — the resubmission history (D1/D11).

    Ordered by `id` rather than `uploaded_at`: several uploads inside one request
    cycle share a timestamp at SQLite's resolution, and the surrogate key is the
    only total order available.
    """
    return list(
        session.exec(
            select(BuyerVerificationDocument)
            .where(BuyerVerificationDocument.user_id == user_id)
            .order_by(BuyerVerificationDocument.id)
        ).all()
    )


@router.post(
    "/verification/documents",
    response_model=VerificationDocumentRead,
    status_code=201,
)
async def submit_verification_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BuyerVerificationDocument:
    """Submit proof of funds (spec 010 V1, V6, V7, V10, V11; D1, D3, D4, D5).

    **No role gate** (D4): F11 is framed from the buyer's side, but a dual
    buyer+seller account (FR-2) must not be locked out of a feature its buyer
    half needs, and the badge is simply irrelevant to a pure-seller account
    since nothing surfaces it outside their own profile.

    **The already-`verified` check runs first**, before a single byte is read
    (D3/V7). Ordering it ahead of validation is the point: a verified buyer
    cannot re-trigger review, and refusing before the write means a rejected
    request leaves nothing on disk to clean up. The only way out of `verified`
    is an admin revoke, never a buyer resubmission.

    From `unverified` (first submission) or `rejected` (resubmission, story 2)
    the status moves to `pending`; from `pending` it stays there, since a second
    document while already queued is more evidence, not a new state.

    No audit row is written here (D6): the document row *is* the record of the
    upload, and nothing about it is overwritten by a later transition. Only
    admin decisions overwrite `verification_reason`, so only they need history.
    """
    if user.verification_status not in _UPLOAD_ALLOWED_FROM:
        # i.e. `verified` — the one status a buyer cannot submit from (D3).
        raise Conflict("Already verified", code="already_verified")

    data, suffix = await read_validated_upload(file)
    # `user.id` from the JWT into the slot M2 passes `listing_id` into — the key
    # is server-generated (uuid) and confined to the uploads base inside
    # `storage.py`, so the client filename never reaches a path (S7).
    key = storage.save(user.id, data, suffix)

    document = BuyerVerificationDocument(
        user_id=user.id,                      # from the JWT, never the body
        storage_key=key,
        original_filename=display_filename(file.filename),
        content_type=file.content_type,
        size_bytes=len(data),
    )
    session.add(document)

    if user.verification_status != "pending":
        user.verification_status = "pending"
        # Cleared, not kept: the reason belonged to the decision this submission
        # answers, and leaving it would show a buyer a stale rejection beside a
        # queued document. The history survives in `BuyerVerificationEvent`,
        # which is the whole reason that table exists (D6).
        user.verification_reason = None
        user.verification_reviewed_at = None
        session.add(user)

    session.commit()
    session.refresh(document)
    return document


@router.get("/verification", response_model=VerificationRead)
def get_my_verification(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> VerificationRead:
    """The caller's own verification state (spec 010 V1, V2, V5, S9).

    Caller-scoped by construction: the id comes from `get_current_user`, and no
    route parameter names a user, so there is nothing here to point at someone
    else's submission. `unverified` with an empty list is the honest answer for a
    user who has never submitted (V2) — not a 404, because "you have no
    verification" is a state, not a missing resource.

    `VerificationRead`/`VerificationDocumentRead` are the boundary: the response
    is built from a declared model, never by serializing the ORM rows, so
    `storage_key` cannot ride along (S9).
    """
    return VerificationRead(
        verification_status=user.verification_status,
        verification_reviewed_at=user.verification_reviewed_at,
        verification_reason=user.verification_reason,
        documents=[
            VerificationDocumentRead(
                id=document.id,
                original_filename=document.original_filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                uploaded_at=document.uploaded_at,
            )
            for document in _documents(session, user.id)
        ],
    )
