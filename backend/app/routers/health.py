"""Health + Milestone-0 sandbox router.

``GET /api/health`` is the liveness probe. The ``/api/sandbox`` pair is a
throwaway that proves the endpoint→session→DB→response path works end to end;
both sandbox routes are deleted once the first real feature ships.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..models import SandboxItem
from ..schemas import SandboxCreate, SandboxRead

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no auth, no data, leaks nothing."""
    return {"status": "ok"}


@router.post("/sandbox", response_model=SandboxRead, status_code=201)
def create_sandbox_item(
    payload: SandboxCreate, session: Session = Depends(get_session)
) -> SandboxItem:
    """Write a row through the session (proves the DB write path)."""
    item = SandboxItem(note=payload.note)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/sandbox", response_model=list[SandboxRead])
def list_sandbox_items(session: Session = Depends(get_session)) -> list[SandboxItem]:
    """Read the rows back (proves the DB read path)."""
    return list(session.exec(select(SandboxItem)).all())
