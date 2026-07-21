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
from ..permissions import (
    get_current_user,
    get_owned_listing,
    require_approved_buyer,
    require_offer_party,
)
from ..schemas import BuyerProfile, OfferCounter, OfferCreate, OfferRead, OfferWithBuyer

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
    success, the offer flips to `accepted`, the listing flips to
    `under_offer`, and every OTHER currently-`submitted` offer on the listing
    is auto-declined in the same commit (D2, E1-E4) — one write, or none.
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

    # Sibling sweep (D2, E1-E4): every OTHER offer on this listing that is
    # currently `submitted` — regardless of who proposed it — is declined in
    # the same transaction. An honest, immediate, auditable "no" rather than a
    # future accept attempt 409ing with no explanation ever given to the buyer
    # who placed it. Never reaches a row that is already terminal (E3) or a
    # different row in the accepting buyer's own history (E4) — both are
    # excluded by `status == "submitted"` alone.
    siblings = session.exec(
        select(Offer).where(
            Offer.listing_id == listing.id,
            Offer.status == "submitted",
            Offer.id != offer.id,
        )
    ).all()
    for sibling in siblings:
        sibling.status = "declined"
        sibling.decided_at = now
        sibling.decided_by_id = user.id     # the accepting seller caused it
        session.add(sibling)
        _record(session, sibling, user, "auto_declined", "submitted", "declined")

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


@router.post("/offers/{offer_id}/counter", response_model=OfferRead)
def counter_offer(
    body: OfferCounter,
    offer_and_role: tuple[Offer, str] = Depends(require_offer_party),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Offer:
    """C1-C7 ⭐ — the original row becomes `countered` (terminal) and a new
    **child** row is inserted (`parent_offer_id` = the original's id,
    `proposed_by_role` = the countering party's role, `status="submitted"`,
    same listing/buyer, the new terms). Two `offer_event` rows are written in
    one transaction: the original's `countered` transition and the child's
    own `submitted` creation.

    **Returns the new child row** (not the original) — this lets the next
    actor read `response.json()["id"]` to act on it directly (plan.md §
    Build order, slice 5).
    """
    offer, role = offer_and_role
    if role == offer.proposed_by_role:
        raise Forbidden("You may not decide your own offer")   # bilateral half of B4/C6

    if offer.status != "submitted":
        raise InvalidTransition(
            f"Cannot counter an offer that is {offer.status}", code="offer_already_decided"
        )

    now = _utcnow()
    from_status = offer.status
    offer.status = "countered"
    offer.decided_at = now
    offer.decided_by_id = user.id
    session.add(offer)

    child = Offer(
        listing_id=offer.listing_id,
        buyer_id=offer.buyer_id,
        parent_offer_id=offer.id,
        proposed_by_role=role,             # the countering party's role, never the body (S3)
        status="submitted",
        price=body.price,
        structure=body.structure,
        contingencies=body.contingencies,
        proposed_close_date=body.proposed_close_date,
    )
    session.add(child)
    session.flush()                        # assigns child.id without ending the transaction

    _record(session, offer, user, "countered", from_status, "countered")
    _record(session, child, user, "submitted", None, "submitted")
    session.commit()
    session.refresh(child)
    return child


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


# ── The seller's queue (spec 007 G1-G4) ──────────────────────────────────────
#
# Pulled forward from its originally-planned slice 7 (plan.md § Build order):
# the sibling auto-decline sweep above (D2, E1-E4) and the concurrent-accept
# invariant (S6) can only be *asserted* through this endpoint — every one of
# those tests reads the seller's queue to see a sibling's post-sweep status.
# Implementing the sweep without a way to observe it would leave it untested,
# so the read half of G moves here; the rest of slice 7's scope (F1-F3's own
# dedicated criteria, S2/S4/S7) is unaffected and still lands in its own slice.


@router.get("/my/listings/{listing_id}/offers", response_model=list[OfferWithBuyer])
def listing_offers(
    listing: Listing = Depends(get_owned_listing),
    session: Session = Depends(get_session),
) -> list[OfferWithBuyer]:
    """The seller's queue for one listing — every buyer's full thread (G1-G4).

    **Guarded by the existing `get_owned_listing`** (mirrors spec 005 D7),
    which is why this route 404s for a non-owner rather than 403ing (G2) — a
    draft's existence stays hidden from a stranger exactly as spec 005
    established.

    The buyer is projected into `BuyerProfile` — never returned as a `User`
    (G3, no email).
    """
    rows = session.exec(
        select(Offer, User)
        .join(User, User.id == Offer.buyer_id)
        .where(Offer.listing_id == listing.id)
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    ).all()

    return [
        OfferWithBuyer(
            id=offer.id,
            listing_id=offer.listing_id,
            buyer_id=offer.buyer_id,
            parent_offer_id=offer.parent_offer_id,
            proposed_by_role=offer.proposed_by_role,
            status=offer.status,
            price=offer.price,
            structure=offer.structure,
            contingencies=offer.contingencies,
            proposed_close_date=offer.proposed_close_date,
            created_at=offer.created_at,
            decided_at=offer.decided_at,
            buyer=BuyerProfile(
                display_name=buyer.display_name,
                budget=buyer.budget,
                target_industries=buyer.target_industries,
                experience=buyer.experience,
            ),
        )
        for offer, buyer in rows
    ]
