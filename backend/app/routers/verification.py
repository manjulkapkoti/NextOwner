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

from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from ..db import get_session
from ..errors import Conflict, InvalidTransition, NotFound
from ..models import BuyerVerificationDocument, BuyerVerificationEvent, User, _utcnow
from ..permissions import (
    get_current_user,
    get_owned_or_admin_verification_document,
    require_admin,
)
from ..schemas import (
    AdminVerificationQueueRead,
    VerificationDocumentRead,
    VerificationRead,
    VerificationRejectRequest,
)
from ..uploads import (
    attachment_headers,
    display_filename,
    enforce_upload_quota,
    read_validated_upload,
    storage,
)

router = APIRouter(tags=["verification"])

# ── The D1 state machine, in one place ───────────────────────────────────────
#
#   unverified ─upload─→ pending ─approve─→ verified
#                  ↑        └────reject───→ rejected
#                  └───────upload──────────────┘        (resubmission, story 2)
#                          verified ─reject─→ rejected  (revoke, story 4)
#
# `unverified` is the default (nothing submitted yet); a buyer's upload is the
# only buyer-initiated transition and always lands on `pending`; only an admin
# reaches `verified`/`rejected`. Reject is deliberately one endpoint for two
# readings — a `pending → rejected` decision is a *deny*, a `verified → rejected`
# one is a *revoke* — so story 4 needs no separate route, and `from_status` on the
# audit row is what tells them apart afterwards (D1, D6, V14).
_UPLOAD_ALLOWED_FROM = {"unverified", "pending", "rejected"}
_APPROVE_ALLOWED_FROM = {"pending"}
_REJECT_ALLOWED_FROM = {"pending", "verified"}

# What the admin queue may be filtered to. `unverified` is **absent by schema**,
# not merely defaulted away: it is every registered account that never submitted
# anything, so a route that could return it would be an "dump every user's email"
# endpoint wearing a review-queue name. Pydantic answers 422 for anything else.
QueueStatus = Literal["pending", "verified", "rejected"]


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
    # D8's per-owner quota — the same helper the M2 listing-document route runs,
    # keyed on the user instead of a listing. Before `storage.save`, so a refused
    # upload leaves nothing on disk. Per D11 there is no resubmission exemption:
    # at the cap the way out is an admin, not a retry.
    enforce_upload_quota(
        session,
        model=BuyerVerificationDocument,
        owner_column=BuyerVerificationDocument.user_id,
        owner_id=user.id,
        new_size_bytes=len(data),
    )
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


@router.get("/verification/documents/{document_id}")
def download_verification_document(
    document: BuyerVerificationDocument = Depends(
        get_owned_or_admin_verification_document
    ),
) -> Response:
    """Serve a proof-of-funds file to its uploader or a reviewing admin (S4, S5, S10).

    **The dependency is the entire authorization**, and the body deliberately
    never sees a `document_id` of its own — the same construction M2's
    `download_document` uses with `require_private_access`, and the reason "B's
    file is unreachable from A's request" is structural rather than a predicate
    someone must remember to write. There is nothing left here to get wrong
    except the response, which is the other half of the seam (S10):
    `attachment_headers` sanitizes the stored name and serves it as an
    attachment, so an uploader controls neither a header nor whether their file
    renders same-origin.

    No `response_model`: this returns bytes, not JSON — the same exception M2's
    document download already is. The `content_type` came from M10's whitelist
    and was matched against the file's magic bytes at upload (`uploads.py`), so
    it is a server-validated value rather than an echo of what the client
    claimed.
    """
    return Response(
        content=storage.open(document.storage_key),
        media_type=document.content_type,
        headers=attachment_headers(document.original_filename),
    )


# ── Admin review (M10 slice 2) — `require_admin` on all three ────────────────
#
# These live here, beside the rest of the state machine, rather than in
# `routers/admin.py` — `verification_status` changes in exactly one file
# (Article 2 #3), the same rule that keeps `listing.status` inside
# `routers/listings.py` even for M3's curation routes. A second implementation in
# another module is how a state machine grows a hole.


def _to_queue_row(
    user: User, documents: list[BuyerVerificationDocument]
) -> AdminVerificationQueueRead:
    """Build the queue row field by field from the declared model.

    Never `AdminVerificationQueueRead(**user.model_dump())`: spreading the ORM row
    is how `password_hash` joins a response the day someone widens the model, and
    S8 exists because that is the *likely* bug here, not a hypothetical one.
    """
    return AdminVerificationQueueRead(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        budget=user.budget,
        target_industries=user.target_industries,
        experience=user.experience,
        verification_status=user.verification_status,
        documents=[
            VerificationDocumentRead(
                id=document.id,
                original_filename=document.original_filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                uploaded_at=document.uploaded_at,
            )
            for document in documents
        ],
    )


def _decision_subject(user_id: int, session: Session) -> User:
    """Load the buyer a decision is about.

    A **literal** 404, unlike the deliberately-uniform 404s of
    `get_owned_watchlist_entry` and friends: by the time this runs the caller has
    already passed `require_admin`, so there is no existence oracle left to
    protect — an admin may legitimately learn which user ids exist. The same
    reasoning `_pending_listing` gives for M3's curation routes.

    **This lookup runs in the route body, after the gate.** That ordering is S2:
    a non-admin is refused by the dependency before any row is read, so they
    cannot distinguish "no such user" from "nothing pending" and turn these routes
    into a probe over the user table. The refusal is about the *caller*, never
    about the target.
    """
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    return user


def _decide(
    *,
    session: Session,
    buyer: User,
    admin: User,
    allowed_from: set[str],
    to: str,
    action: str,
    illegal_message: str,
    reason: str | None = None,
) -> User:
    """Apply an admin decision and audit it (V4, V5, V14, X3, X4; D1, D6).

    The status guard comes **first**, so an illegal transition raises before
    anything is written — that is what makes "no audit row for a refused attempt"
    a property of the code rather than a promise, exactly as `_transition` does
    for listings. The log records what happened, not what was tried.

    Every decision stamps `verification_reviewed_at` (V4) and overwrites
    `verification_reason` — the overwrite is precisely why the event row exists
    (D6): once a rejection is followed by an approval, only the row still knows
    the buyer was ever rejected and why.

    **No compare-and-swap** (D12(c), deliberate). Two admins deciding in the same
    microsecond could each write an event row, and that is the honest record:
    unlike M7's offer accept, nothing here is exclusive, both decisions are
    legitimately audited, and the resulting status is one an admin chose. The
    guard is a plain read.
    """
    from_status = buyer.verification_status
    if from_status not in allowed_from:
        # A fixed message per route (plan.md § Errors), not an interpolated
        # "cannot go from X to Y": the code is what a client branches on, and a
        # message that recites the subject's current status is a detail this
        # response has no reason to carry.
        raise InvalidTransition(illegal_message)

    buyer.verification_status = to
    buyer.verification_reviewed_at = _utcnow()      # server clock, never the client's
    buyer.verification_reason = reason
    session.add(buyer)
    session.add(
        BuyerVerificationEvent(
            user_id=buyer.id,
            actor_id=admin.id,          # from the JWT, never the body
            action=action,
            from_status=from_status,
            to_status=to,
            reason=reason,              # copied at write time — the point of the row
        )
    )
    session.commit()
    session.refresh(buyer)
    return buyer


@router.get("/admin/verifications", response_model=list[AdminVerificationQueueRead])
def admin_verification_queue(
    status: QueueStatus = Query(default="pending"),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[AdminVerificationQueueRead]:
    """The review queue (spec 010 V3, S3, S8; story 3).

    Curation of *demand*, the sibling of M3's curation of supply — and the same
    shape: profile fields plus the submitted documents on the row, so an admin can
    judge without a second lookup.

    `?status=` defaults to `pending` (the working view) and also reaches
    `verified`/`rejected`. The override is not decoration: D1's revoke path
    (V14) is `reject` on an *already-verified* buyer, and without a way to list
    them an admin would have to already know the user id — story 4 would have an
    endpoint and no way to find its subject.

    **Not paginated**, a recorded omission rather than an oversight (D12(b)): a
    page cap belongs with the filtering and search the `trust-safety-ops` queue
    work will add. Note that the `?status=verified` view is bounded by *all*
    verified buyers rather than by the review backlog, which is the one place that
    omission actually bites — the reason to fix it there and not here.
    """
    users = list(
        session.exec(
            select(User)
            .where(User.verification_status == status)
            # By id: deterministic and total. Genuine queue fairness wants oldest
            # *submission* first, which no column here answers — the buyer's own
            # `created_at` is when they registered, not when they submitted. That
            # belongs with the ordering/filtering work D12(b) defers, not with a
            # join bolted on for an untested property.
            .order_by(User.id)
        ).all()
    )
    if not users:
        return []

    # One query for every row's documents rather than one per user — the same
    # batch shape `my_listings` uses for rejection reasons.
    documents = session.exec(
        select(BuyerVerificationDocument)
        .where(BuyerVerificationDocument.user_id.in_([user.id for user in users]))
        .order_by(BuyerVerificationDocument.id)
    ).all()
    by_user: dict[int, list[BuyerVerificationDocument]] = {}
    for document in documents:
        by_user.setdefault(document.user_id, []).append(document)

    return [_to_queue_row(user, by_user.get(user.id, [])) for user in users]


@router.post(
    "/admin/verifications/{user_id}/approve",
    response_model=AdminVerificationQueueRead,
)
def approve_verification(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AdminVerificationQueueRead:
    """`pending → verified` — the only path to a badge (spec 010 V4, X3, S2).

    No client-reachable route sets `verification_status` to `verified`; this one
    is `require_admin`, which re-reads `is_admin` from the DB row on every
    request, so a token minted before a demotion cannot be replayed into it.

    409 from anything but `pending` (X3): there is nothing to approve for a user
    who never submitted, and re-approving an already-`verified` buyer would write
    a second event row recording a transition that did not happen.

    An admin acting on their own account is **not** special-cased (D12(a)): the
    audit row simply shows `actor_id == user_id`, which is more legible than an
    exception would be, and admin is granted by direct DB access alone.
    """
    buyer = _decision_subject(user_id, session)
    _decide(
        session=session,
        buyer=buyer,
        admin=admin,
        allowed_from=_APPROVE_ALLOWED_FROM,
        to="verified",
        action="approved",
        illegal_message="Nothing pending to approve",
        # Explicitly cleared: an approved buyer carries no reason. A stale one
        # would surface to them through `GET /verification` beside a granted badge.
        reason=None,
    )
    return _to_queue_row(buyer, _documents(session, buyer.id))


@router.post(
    "/admin/verifications/{user_id}/reject",
    response_model=AdminVerificationQueueRead,
)
def reject_verification(
    user_id: int,
    body: VerificationRejectRequest,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AdminVerificationQueueRead:
    """`{pending, verified} → rejected` — deny **and** revoke (V5, V14, X2, X4, S2).

    One endpoint for both readings of the same transition (D1): rejecting a
    `pending` submission is a *deny*, rejecting a `verified` buyer is story 4's
    *revoke*. They need no separate routes because nothing about the write
    differs — and `from_status` on the event row is what distinguishes them
    afterwards, which is the concrete thing `User.verification_reason` alone
    loses on the next decision (D6, V14).

    `rejected` is not a legal `from_status` (X4): a second rejection would record
    a transition that did not occur. `unverified` is not either — there is
    nothing to deny.

    The reason is required *by schema* (`VerificationRejectRequest`), so a missing
    or over-long one is a 422 at the boundary and the state machine never sees a
    rejection the buyer cannot act on — M3's rule, and the reason this route
    stores `.strip()`ped text.
    """
    buyer = _decision_subject(user_id, session)
    _decide(
        session=session,
        buyer=buyer,
        admin=admin,
        allowed_from=_REJECT_ALLOWED_FROM,
        to="rejected",
        action="rejected",
        illegal_message="Cannot reject from this status",
        reason=body.reason.strip(),
    )
    return _to_queue_row(buyer, _documents(session, buyer.id))
