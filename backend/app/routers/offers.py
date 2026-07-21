"""Offers / LOI (M7, FR-17) — the project's first money surface and its first
**bilateral** state machine.

Every transition of `offer.status` happens in **this file**, for the same
reason M3 kept listing curation beside the rest of its state machine and M5
kept access decisions beside the rest of its own (Article 2 #3): a state
machine with a second implementation elsewhere is a state machine with a hole.

The states and their only legal moves (spec 007 D1/D4):

    submitted ──accept───▶ accepted
        ├──────decline──▶ declined
        ├──────counter──▶ countered  (+ spawns a new `submitted` child row)
        └──────withdraw─▶ withdrawn

`accepted`/`declined`/`withdrawn`/`countered` are all terminal for **that
row**. Decision rights on `accept`/`decline`/`counter` belong to whoever did
**not** propose the row's current terms (`role != offer.proposed_by_role`);
`withdraw` is the mirror image — proposer-only (`role == offer.proposed_by_role`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..errors import Conflict, Forbidden, InvalidTransition
from ..models import Listing, Offer, OfferEvent, User, _utcnow
from ..permissions import get_current_user, require_approved_buyer, require_offer_party
from ..schemas import OfferCreate, OfferRead

router = APIRouter(tags=["offers"])


def _record(
    session: Session, offer: Offer, actor: User, action: str,
    from_status: str | None, to_status: str,
) -> None:
    """Append one audit row for a **completed** transition (spec 007 § Schema
    deltas). Never called for an attempt that was refused — the log records
    what happened, not what was tried (the same rule `listingevent` and
    `accessrequestevent` already keep). `offer.id` must already be assigned
    (post-flush or post-commit) before this is called.
    """
    session.add(
        OfferEvent(
            offer_id=offer.id,
            actor_id=actor.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
        )
    )


# ── Creating an offer (spec 007 A1-A8, D3, D6, D7) ───────────────────────────

@router.post("/listings/{listing_id}/offers", response_model=OfferRead, status_code=201)
def create_offer(
    body: OfferCreate,
    listing=Depends(require_approved_buyer),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Offer:
    """A buyer with approved access proposes structured terms.

    `require_approved_buyer` already proved: the listing exists and is public
    knowledge or owned by the caller (else 404), the caller isn't the owner
    (else 403), the caller holds approved access (else 403
    `nda_access_required`), and the listing is `live` (else 409
    `listing_not_live`). What's left is this endpoint's own job:

    - **D7** — at most one *active* (`submitted`) offer per `(listing,
      buyer)`. An application-level check, not a DB constraint, because old
      terminal rows must coexist with a fresh submission.
    - **A6/S3** — mass-assignment defense. `OfferCreate` has no `status`,
      `buyer_id`, `proposed_by_role`, or `decided_at` fields, so a client that
      sends them finds them silently ignored; every one of those five values
      is derived here, server-side.
    """
    existing = session.exec(
        select(Offer).where(
            Offer.listing_id == listing.id,
            Offer.buyer_id == user.id,
            Offer.status == "submitted",
        )
    ).first()
    if existing is not None:
        raise Conflict(
            "An active offer already exists on this listing", code="offer_already_active"
        )

    offer = Offer(
        listing_id=listing.id,
        buyer_id=user.id,                  # from the JWT, never the body (A6)
        parent_offer_id=None,
        proposed_by_role="buyer",          # server-derived, never the body (A6)
        status="submitted",
        price=body.price,
        structure=body.structure,
        contingencies=body.contingencies,
        proposed_close_date=body.proposed_close_date,
    )
    session.add(offer)
    session.flush()                        # assigns offer.id without ending the transaction
    _record(session, offer, user, "submitted", None, "submitted")
    session.commit()
    session.refresh(offer)
    return offer


# ── The seller's decision on a buyer-proposed offer (spec 007 B ⭐) ──────────


@router.post("/offers/{offer_id}/accept", response_model=OfferRead)
def accept_offer(
    offer_and_role: tuple[Offer, str] = Depends(require_offer_party),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Offer:
    """Accept ⭐ — the atomic money path (spec 007 B1, B7-B8, plan.md § The
    atomic accept + sibling auto-decline).

    One transaction: `offer.status` and `listing.status` are re-loaded and
    guarded **here**, never trusted from anywhere earlier (B8, S6,
    `security.md` §6 race conditions) — a 409 leaves every row untouched. On
    success, the offer flips to `accepted` and the listing flips to
    `under_offer` together. (The sibling auto-decline sweep — D2, E1-E4 — is
    added on top of this same transaction in the next slice.)
    """
    offer, role = offer_and_role
    if role == offer.proposed_by_role:
        raise Forbidden("You may not decide your own offer")   # B4

    # Re-loaded fresh, never trusted from when the offer was created (B8/S6).
    listing = session.get(Listing, offer.listing_id)
    if offer.status != "submitted":
        raise InvalidTransition(
            f"Cannot accept an offer that is {offer.status}", code="offer_already_decided"
        )
    if listing is None or listing.status != "live":
        raise InvalidTransition("Listing is not live", code="listing_not_live")

    now = _utcnow()
    offer.status = "accepted"
    offer.decided_at = now
    offer.decided_by_id = user.id
    listing.status = "under_offer"
    session.add(offer)
    session.add(listing)
    _record(session, offer, user, "accepted", "submitted", "accepted")

    session.commit()
    session.refresh(offer)
    return offer


@router.post("/offers/{offer_id}/decline", response_model=OfferRead)
def decline_offer(
    offer_and_role: tuple[Offer, str] = Depends(require_offer_party),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Offer:
    """B2 — declines, terminal, and touches nothing outside this one row."""
    offer, role = offer_and_role
    if role == offer.proposed_by_role:
        raise Forbidden("You may not decide your own offer")   # B4

    if offer.status != "submitted":
        raise InvalidTransition(
            f"Cannot decline an offer that is {offer.status}", code="offer_already_decided"
        )

    from_status = offer.status
    offer.status = "declined"
    offer.decided_at = _utcnow()
    offer.decided_by_id = user.id
    session.add(offer)
    _record(session, offer, user, "declined", from_status, "declined")
    session.commit()
    session.refresh(offer)
    return offer


# ── The buyer's own offers (spec 007 F1-F3) ──────────────────────────────────


@router.get("/my/offers", response_model=list[OfferRead])
def my_offers(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Offer]:
    """The buyer's own offers, across every listing (F1-F3).

    Caller-scoped in the **query**, not a post-filter: `buyer_id == user.id`
    is a WHERE clause, so another buyer's row is never loaded in the first
    place (F2).
    """
    return session.exec(
        select(Offer)
        .where(Offer.buyer_id == user.id)
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    ).all()
