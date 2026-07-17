"""Profile router — the caller edits their *own* profile only.

The target user is derived from the JWT (`get_current_user`), never from the
request body. `ProfileUpdate` has no `user_id` field, so an IDOR attempt (E3)
targeting another user is structurally impossible — the id is simply ignored.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..models import User
from ..permissions import get_current_user
from ..schemas import ProfileUpdate, UserRead

router = APIRouter(tags=["profile"])


@router.put("/profile", response_model=UserRead)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
