"""SQLModel tables — the schema.

Milestone 0 only defines a throwaway ``SandboxItem`` to prove the write→read
DB path end to end. The real domain tables (user, listing, listing_private,
access_request, offer, …) arrive with their milestones per
``docs/design_implementation.md`` §3.5.
"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Timezone-aware UTC now (``datetime.utcnow`` is deprecated in 3.12)."""
    return datetime.now(timezone.utc)


class SandboxItem(SQLModel, table=True):
    """Throwaway Milestone-0 row — proves the DB pipeline; removed once the
    first real table lands."""

    id: int | None = Field(default=None, primary_key=True)
    note: str
    created_at: datetime = Field(default_factory=_utcnow)
