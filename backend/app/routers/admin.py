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

from ..config import settings
from ..db import get_session
from ..models import Listing, ListingPrivate, User, ValuationLead
from ..permissions import require_admin
from ..schemas import AdminListingRead, ValuationLeadRead

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


@router.get("/valuation-leads", response_model=list[ValuationLeadRead])
def admin_valuation_leads(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[ValuationLeadRead]:
    """The leads the public calculator captured (M11, FR-23, spec 011 D3, A1-A3).

    **The one privileged surface in M11**, and the only route in the milestone
    that reads an identity at all — the other two are anonymous by design. It
    exists because a captured lead nobody can read is not a captured lead, and
    because this codebase has a recorded lesson about tables written milestones
    before their only consumer (`milestones.md` § Scope fold-ins → M8).

    It lives here rather than in `routers/valuation.py` because this file already
    *is* "the routes behind `require_admin`": splitting one trust boundary across
    two modules is how a guard eventually gets forgotten on one of them.

    Newest-first because a lead magnet's value decays — the person who typed
    their numbers in this morning is the one worth calling. Capped at
    `valuation_leads_page_limit`, the same unbounded-pagination control M4's
    browse and M8's inbox apply (`security.md` §6 DoS surface).

    `ValuationLeadRead` carries an email address, which is why it is returned
    **only** here. Like `AdminListingRead` above, it is safe solely because
    `require_admin` re-reads `is_admin` from the DB on every request (S3), so it
    must never be reused on a route with a weaker guard.
    """
    leads = session.exec(
        select(ValuationLead)
        .order_by(ValuationLead.created_at.desc(), ValuationLead.id.desc())
        .limit(settings.valuation_leads_page_limit)
    ).all()
    return [ValuationLeadRead.model_validate(lead, from_attributes=True) for lead in leads]
