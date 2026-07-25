"""Saved searches — the buyer's stored browse filters (M8, FR-11).

Caller-scoped throughout: create derives `user_id` from the JWT, list filters
on it, and delete goes through `get_owned_saved_search`. `SavedSearchCreate`
has no `user_id` field at all, so a client that sends one finds it ignored by
schema rather than by a runtime check someone could remove (spec A6).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, func, select

from ..config import settings
from ..db import get_session
from ..errors import Conflict
from ..models import SavedSearch, User
from ..permissions import get_current_user, get_owned_saved_search
from ..schemas import SavedSearchCreate, SavedSearchRead
from ..saved_search_matching import parse_filters

router = APIRouter(tags=["saved-searches"])


def _to_read(row: SavedSearch) -> SavedSearchRead:
    return SavedSearchRead(
        id=row.id,
        name=row.name,
        filters=parse_filters(row.filters_json),
        created_at=row.created_at,
    )


@router.post("/saved-searches", response_model=SavedSearchRead, status_code=201)
def create_saved_search(
    body: SavedSearchCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SavedSearchRead:
    """Save a search (spec A1, A6, A7, A9, A10).

    The per-user cap is a real control, not tidiness: every saved search costs
    one predicate evaluation on **every** publication, so an unbounded count
    turns one buyer into a load amplifier on the admin's approve path
    (NFR Scalability — "fan-out alert jobs must handle publication spikes").
    A 409 says "you are at your limit" rather than silently dropping the row.
    """
    existing = session.exec(
        select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user.id)
    ).one()
    if existing >= settings.saved_search_max_per_user:
        raise Conflict(
            "You have reached the maximum number of saved searches",
            code="saved_search_limit",
        )

    row = SavedSearch(
        user_id=user.id,                        # from the JWT, never the body
        name=body.name,
        filters_json=body.filters.model_dump_json(exclude_none=True),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(row)


@router.get("/saved-searches", response_model=list[SavedSearchRead])
def list_saved_searches(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[SavedSearchRead]:
    """The caller's own searches, newest first (spec A2, A3)."""
    rows = session.exec(
        select(SavedSearch)
        .where(SavedSearch.user_id == user.id)
        .order_by(SavedSearch.created_at.desc(), SavedSearch.id.desc())
    ).all()
    return [_to_read(row) for row in rows]


@router.delete("/saved-searches/{saved_search_id}", status_code=204)
def delete_saved_search(
    saved_search: SavedSearch = Depends(get_owned_saved_search),
    session: Session = Depends(get_session),
) -> Response:
    """Delete one of the caller's own searches (spec A4, A5).

    A hard delete, unlike the audit-bearing tables elsewhere in this codebase:
    a saved search is a convenience with no evidentiary value, so there is
    nothing here a later reader needs (plan.md § Data protection).
    """
    session.delete(saved_search)
    session.commit()
    return Response(status_code=204)
