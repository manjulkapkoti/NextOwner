"""The watchlist — a user's favorited listings (M9, FR-12, spec 009).

Caller-scoped throughout, and unusually thin even by this codebase's standards:
**no route here takes a request body.** Add and remove are addressed entirely by
the path (`/watchlist/{listing_id}`), so `user_id` mass-assignment is not
rejected by a runtime check someone could later remove — there is no field to
assign from at all (spec S4, the strongest form of `security.md` §2's control).

Two different boundaries, kept as two named checks rather than one blurred gate:

- *What may I see?* — `POST` reuses `get_public_listing`'s inline
  "missing or not `live` → the same 404" rule verbatim (D2). A buyer cannot
  favorite what they could never have browsed to, and the owner is not
  special-cased (W13), so this route is never an existence oracle.
- *What may I touch?* — `DELETE` goes through `get_owned_watchlist_entry`,
  keyed on the pair `(caller, listing)` (D5), so another account's row is
  unreachable by construction rather than by a predicate someone must remember
  to write (S2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..errors import NotFound
from ..models import Listing, User, WatchlistEntry
from ..permissions import get_current_user, get_owned_watchlist_entry
from ..schemas import WatchlistEntryRead

router = APIRouter(tags=["watchlist"])


def _to_read(entry: WatchlistEntry, listing: Listing) -> WatchlistEntryRead:
    """The entry joined to its listing's *public* fields only.

    Built field by field from a standalone model rather than by spreading the
    ORM row, so a column added to `Listing` later cannot ride out to a buyer
    unnoticed (plan 009 § Response models).
    """
    return WatchlistEntryRead(
        listing_id=listing.id,
        added_at=entry.created_at,
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


def _existing_entry(
    session: Session, user_id: int, listing_id: int
) -> WatchlistEntry | None:
    return session.exec(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.listing_id == listing_id,
        )
    ).first()


@router.post("/watchlist/{listing_id}", response_model=WatchlistEntryRead, status_code=201)
def add_to_watchlist(
    listing_id: int,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WatchlistEntryRead:
    """Favorite a `live` listing (spec W1, W4, W5, W6, W12, W13; D1, D2, D4).

    **Idempotent, not a duplicate-erroring create (D1).** A watchlist entry is a
    boolean membership fact with nothing to lose on a repeat — the closer
    precedent is `POST /auth/nda` ("signing again is idempotent"), not
    `access-request` (where a decided row is terminal and a repeat is a real
    conflict). A second add answers **200** instead of 201 and leaves exactly
    one row, which is the natural behaviour for a heart icon a client may click
    twice, hold open in two tabs, or retry on a flaky network.

    The check-then-insert below is a TOCTOU the read alone cannot close
    (`security.md` §6), so the unique index on `(user_id, listing_id)` is the
    backstop: if a concurrent request wins the race, the `IntegrityError` means
    "already present" — which is precisely D1's answer — and is converted into
    the same 200, never surfaced as a 409 or a 500.
    """
    listing = session.get(Listing, listing_id)
    if listing is None or listing.status != "live":
        # Same 404, same message as `get_public_listing`: a draft, a rejected
        # listing and a missing id are indistinguishable here (D2).
        raise NotFound("Listing not found")

    existing = _existing_entry(session, user.id, listing_id)
    if existing is not None:
        response.status_code = 200
        return _to_read(existing, listing)

    entry = WatchlistEntry(user_id=user.id, listing_id=listing_id)  # id from the JWT
    session.add(entry)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raced = _existing_entry(session, user.id, listing_id)
        if raced is None:
            raise
        response.status_code = 200
        return _to_read(raced, listing)

    session.refresh(entry)
    return _to_read(entry, listing)


@router.get("/watchlist", response_model=list[WatchlistEntryRead])
def list_watchlist(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[WatchlistEntryRead]:
    """The caller's own watchlist, newest-added first (spec W3, W7, W8, W11, S1; D3).

    **Filtered to currently-`live` listings, not to what was live at add time
    (D3).** A listing that is paused, closed, rejected or put under offer drops
    silently out of this view while its row stays untouched, so it reappears on
    its own if the seller resumes — W7 and W8 are one story split across two
    criteria. The alternative, returning the entry with its listing's status,
    would publish a seller-side lifecycle fact to a watching buyer: exactly the
    channel `ListingPublic` chose not to open, and here the field would not even
    be the constant it is there.

    The `user_id == caller` predicate is the whole of S1. It is easy to lose,
    because with a single user "all rows" and "my rows" are the same set and
    every happy-path test still passes.

    Ordered `created_at DESC, id DESC`: the id tiebreak is not decoration —
    several entries added inside one test share a timestamp at SQLite's
    resolution, and without it "newest first" is flaky rather than wrong
    (`list_saved_searches` orders the same way for the same reason).
    """
    rows = session.exec(
        select(WatchlistEntry, Listing)
        .join(Listing, Listing.id == WatchlistEntry.listing_id)
        .where(WatchlistEntry.user_id == user.id, Listing.status == "live")
        .order_by(WatchlistEntry.created_at.desc(), WatchlistEntry.id.desc())
    ).all()
    return [_to_read(entry, listing) for entry, listing in rows]


@router.delete("/watchlist/{listing_id}", status_code=204)
def remove_from_watchlist(
    entry: WatchlistEntry = Depends(get_owned_watchlist_entry),
    session: Session = Depends(get_session),
) -> Response:
    """Un-favorite (spec W2, W9, W10, S2).

    A hard delete, like `SavedSearch` and unlike the audit-bearing tables: a
    favorite carries no evidentiary value, so there is nothing here a later
    reader needs (plan 009 § Data protection).

    The gate does all the authorization, and this body deliberately never takes
    a `listing_id` of its own — that absence is what makes "B's delete cannot
    reach A's row" structural rather than a predicate someone must remember
    (S2). Note that the *listing's* status is irrelevant here: a buyer must be
    able to clear an entry whose listing has since left `live` and vanished
    from their view (D3), which a liveness check would make impossible.
    """
    session.delete(entry)
    session.commit()
    return Response(status_code=204)


