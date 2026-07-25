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
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
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
    listing: Listing = Depends(require_approved_buyer),
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
    try:
        # The SELECT above answers the common case with a clean 409; the partial
        # unique index (`Offer.__table_args__`) is the race backstop for two
        # concurrent creates that both pass that SELECT — the same
        # check-then-insert TOCTOU `create_access_request` closes with a DB
        # constraint rather than a prior read (`security.md` §6). `Offer` has
        # exactly one unique constraint, so an IntegrityError here is that
        # duplicate.
        session.flush()                    # assigns offer.id without ending the transaction
        _record(session, offer, user, "submitted", None, "submitted")
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(
            "An active offer already exists on this listing", code="offer_already_active"
        ) from None
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

    now = _utcnow()
    # Compare-and-swap, not read-then-write. The WHERE clauses are evaluated
    # against committed DB state at write time, so two concurrent accepts can't
    # both pass a stale start-of-request snapshot and both commit (B8/S6,
    # `security.md` §6). A read-then-write guard is a TOCTOU: production hands
    # each request its **own** Session (`db.py`), so the earlier per-request
    # read is a snapshot, not a lock. `SELECT ... FOR UPDATE` is not an option —
    # SQLite drops it silently (false confidence); a rowcount-checked
    # conditional UPDATE closes the window on both SQLite and the later Postgres.
    accepted = session.execute(
        update(Offer)
        .where(Offer.id == offer.id, Offer.status == "submitted")
        .values(status="accepted", decided_at=now, decided_by_id=user.id)
        .execution_options(synchronize_session=False)
    )
    if accepted.rowcount != 1:
        raise InvalidTransition(
            f"Cannot accept an offer that is {offer.status}", code="offer_already_decided"
        )

    flipped = session.execute(
        update(Listing)
        .where(Listing.id == offer.listing_id, Listing.status == "live")
        .values(status="under_offer")
        .execution_options(synchronize_session=False)
    )
    if flipped.rowcount != 1:
        # The listing left `live` between this offer's creation and now (the
        # seller paused it, or another accept already won the race for this
        # listing) — nothing this transaction did may stand, so roll the offer
        # CAS above back too before refusing.
        session.rollback()
        raise InvalidTransition("Listing is not live", code="listing_not_live")

    _record(session, offer, user, "accepted", "submitted", "accepted")

    # Sibling sweep (D2, E1-E4): every OTHER offer on this listing still
    # `submitted` is declined in the same transaction — an honest, immediate,
    # auditable "no". Each decline is itself a compare-and-swap, so a sibling a
    # concurrent request just moved out of `submitted` is left untouched (its
    # rowcount is 0, no event written), never double-decided. Terminal rows
    # (E3) and the accepting buyer's own history (E4) are excluded by
    # `status == "submitted"` to begin with.
    siblings = session.exec(
        select(Offer).where(
            Offer.listing_id == offer.listing_id,
            Offer.status == "submitted",
            Offer.id != offer.id,
        )
    ).all()
    for sibling in siblings:
        swept = session.execute(
            update(Offer)
            .where(Offer.id == sibling.id, Offer.status == "submitted")
            .values(status="declined", decided_at=now, decided_by_id=user.id)
            .execution_options(synchronize_session=False)
        )
        if swept.rowcount == 1:                      # the accepting seller caused it
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

    # Compare-and-swap (see `accept_offer`) — a concurrent second decline finds
    # the row no longer `submitted` and 409s rather than double-deciding.
    declined = session.execute(
        update(Offer)
        .where(Offer.id == offer.id, Offer.status == "submitted")
        .values(status="declined", decided_at=_utcnow(), decided_by_id=user.id)
        .execution_options(synchronize_session=False)
    )
    if declined.rowcount != 1:
        raise InvalidTransition(
            f"Cannot decline an offer that is {offer.status}", code="offer_already_decided"
        )
    _record(session, offer, user, "declined", "submitted", "declined")
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

    # A counter CREATES a new priced proposal (D1) — the same class of action
    # `require_approved_buyer` gates on `live` for the root offer (A3), and that
    # `accept` re-checks inside its own transaction (B8). Without this, a party
    # could spawn priced `submitted` rows on a listing that has left `live`
    # (paused/closed/under_offer) — the corridor past an already-open thread that
    # every other door already blocks (spec 007 B10/D8; appsec M7 Finding 1).
    # Checked before any write, so a 409 leaves the parent and the audit trail
    # untouched. `decline`/`withdraw` are deliberately NOT gated on liveness (D8):
    # they resolve/retract an existing row without creating a new commitment.
    #
    # This is a plain read, not a WHERE-clause CAS like `accept`'s listing flip
    # (B8/S6). That leaves a theoretical microsecond TOCTOU — the listing could
    # pause between this read and the child insert — accepted, not closed:
    # unlike the accept race (two buyers competing for a scarce accept), no party
    # gains anything by racing a counter onto a just-paused listing, and the only
    # money-moving step, `accept`, remains a true CAS regardless of what a
    # mistimed counter produced (appsec M7 re-verification, non-blocking).
    listing = session.get(Listing, offer.listing_id)
    if listing is None or listing.status != "live":
        raise InvalidTransition("Listing is not live", code="listing_not_live")

    now = _utcnow()
    # Compare-and-swap the parent to `countered` BEFORE inserting the child, so
    # (a) a concurrent second counter finds it no longer `submitted` and 409s
    # instead of spawning a rival child, and (b) the pair never momentarily
    # holds two `submitted` rows, which the D7 partial-unique index forbids.
    countered = session.execute(
        update(Offer)
        .where(Offer.id == offer.id, Offer.status == "submitted")
        .values(status="countered", decided_at=now, decided_by_id=user.id)
        .execution_options(synchronize_session=False)
    )
    if countered.rowcount != 1:
        raise InvalidTransition(
            f"Cannot counter an offer that is {offer.status}", code="offer_already_decided"
        )

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
    try:
        # Defense-in-depth mirror of `create_offer`'s own IntegrityError guard.
        # The parent was CAS'd out of `submitted` above before this insert, so on
        # SQLite (writes serialize) the D7 partial-unique index cannot currently
        # be tripped here; the guard keeps the two insert paths symmetric and
        # race-safe under Postgres row-locking, turning a would-be raw 500 into
        # the same clean 409 `create_offer` returns.
        session.flush()                    # assigns child.id without ending the transaction
        _record(session, offer, user, "countered", "submitted", "countered")
        _record(session, child, user, "submitted", None, "submitted")
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(
            "An active offer already exists on this listing", code="offer_already_active"
        ) from None
    session.refresh(child)
    return child


@router.post("/offers/{offer_id}/withdraw", response_model=OfferRead)
def withdraw_offer(
    offer_and_role: tuple[Offer, str] = Depends(require_offer_party),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Offer:
    """D1-D4 — the mirror image of accept/decline/counter: only the current
    **proposer** of the live `submitted` row may withdraw it."""
    offer, role = offer_and_role
    if role != offer.proposed_by_role:
        raise Forbidden("You may not withdraw an offer you did not propose")   # D2/D3

    # Compare-and-swap (see `accept_offer`) — proposer-only, and a concurrent
    # second withdraw finds the row no longer `submitted` and 409s.
    withdrawn = session.execute(
        update(Offer)
        .where(Offer.id == offer.id, Offer.status == "submitted")
        .values(status="withdrawn", decided_at=_utcnow(), decided_by_id=user.id)
        .execution_options(synchronize_session=False)
    )
    if withdrawn.rowcount != 1:
        raise InvalidTransition(
            f"Cannot withdraw an offer that is {offer.status}", code="offer_already_decided"
        )
    _record(session, offer, user, "withdrawn", "submitted", "withdrawn")
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
