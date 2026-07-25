"""Notifications router — the in-app inbox (M8, FR-22).

Every route here is **caller-scoped by construction**: the list and count
filter on `recipient_id == user.id`, and the two per-row routes go through
`get_owned_notification`, which cannot return someone else's row. There is
deliberately **no create route** (spec S4) — a notification is a side effect of
a domain action written by `notifications.py`, never a client write, so there
is nothing here for a client to forge.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from ..db import get_session
from ..models import Notification, User, _utcnow
from ..notifications import mark_all_read
from ..permissions import get_current_user, get_owned_notification
from ..schemas import NotificationQuery, NotificationRead, UnreadCountRead

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    query: NotificationQuery = Depends(),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Notification]:
    """The caller's inbox, newest first (spec E1, E2, E3, E8, X5).

    `id` breaks ties on `created_at` for the same reason M4's browse does it:
    two notifications written inside one transaction share a timestamp, and
    without a total ordering they could swap between pages and hide a row from
    a paginating caller.
    """
    conditions = [Notification.recipient_id == user.id]
    if query.unread:
        conditions.append(Notification.read_at.is_(None))    # type: ignore[union-attr]

    return list(
        session.exec(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(query.limit)
            .offset(query.offset)
        ).all()
    )


@router.get("/notifications/unread-count", response_model=UnreadCountRead)
def unread_count(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UnreadCountRead:
    """The nav badge (spec E6). Counts in SQL rather than loading the rows."""
    total = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_id == user.id,
            Notification.read_at.is_(None),                   # type: ignore[union-attr]
        )
    ).one()
    return UnreadCountRead(unread_count=total)


@router.post("/notifications/read-all", response_model=UnreadCountRead)
def read_all(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UnreadCountRead:
    """Mark every unread row of **this caller** read (spec E7).

    Declared before the `{notification_id}` route below only for readability —
    the two cannot collide, since this path has one segment where that one has
    two.
    """
    mark_all_read(session, user)
    session.commit()
    return UnreadCountRead(unread_count=0)


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification: Notification = Depends(get_owned_notification),
    session: Session = Depends(get_session),
) -> Notification:
    """Mark one row read (spec E4, E5, E10).

    **Idempotent**: a second call returns the original timestamp rather than
    moving it. `read_at` answers "when did you first see this", and a re-click
    (or a double-fired request) must not be able to rewrite that.

    Takes no request body at all, so a client sending `recipient_id` or
    `read_at` is ignored entirely — FastAPI never reads a body this function
    does not declare (spec S6, the same construction `sign_nda` uses).
    """
    if notification.read_at is None:
        notification.read_at = _utcnow()
        session.add(notification)
        session.commit()
        session.refresh(notification)
    return notification
