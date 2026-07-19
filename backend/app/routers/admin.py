"""Admin router — the curation queue (M3), behind `require_admin`.

Curation is the product's quality promise: every listing a buyer sees passed a
human check. That promise holds only because approve is the sole path to
`live` — and the transitions themselves live in `routers/listings.py` beside
the rest of the state machine, so there is one implementation of it, not two.

`/ping` predates M3: it exists so `require_admin` had a testable surface at M1,
and still proves the boundary independently of any real data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Listing, ListingPrivate, User
from ..permissions import require_admin
from ..schemas import AdminListingRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
def admin_ping(user: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok", "admin": user.email}


@router.get("/listings", response_model=list[AdminListingRead])
def admin_listings(
    status: str | None = Query(default=None),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[AdminListingRead]:
    """The curation queue. `?status=pending_review` is the working view; no
    filter returns every status, because an admin also needs to see what they
    already decided (spec A1, A2).

    Rows carry the private company detail (A5). This is the one place private
    data is served outside the owner before M5's NDA gate, and it is
    deliberate: an admin cannot judge a listing they cannot see. It is safe
    only because `require_admin` re-reads `is_admin` from the DB on every
    request — so `AdminListingRead` must never be reused on a route with a
    weaker guard.
    """
    query = select(Listing)
    if status is not None:
        query = query.where(Listing.status == status)
    listings = session.exec(query.order_by(Listing.created_at)).all()

    rows: list[AdminListingRead] = []
    for listing in listings:
        private = session.get(ListingPrivate, listing.id)
        rows.append(
            AdminListingRead(
                **listing.model_dump(),
                company_name=private.company_name if private else None,
                website_url=private.website_url if private else None,
            )
        )
    return rows
