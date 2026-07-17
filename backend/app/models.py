"""SQLModel tables — the schema.

`User` (M1) ships **erasure-ready** (`data_protection.md` §3): a `deleted_at`
soft-delete path and nullable PII, so a future GDPR erasure flow anonymizes in
place without breaking referential integrity. The user-facing erasure *endpoint*
is post-MVP; only the schema support lands here.

`SandboxItem` is the throwaway M0 DB-pipeline proof — deleted at M1 slice 11.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Timezone-aware UTC now (``datetime.utcnow`` is deprecated in 3.12)."""
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)          # PII — never on a public model, never logged
    password_hash: str                                    # bcrypt — never returned

    # Roles: two flags, not an enum — FR-2 allows holding *both* under one account.
    is_buyer: bool = Field(default=False)
    is_seller: bool = Field(default=False)
    is_admin: bool = Field(default=False)                 # server-only; re-read from DB per request

    # Minimal profile (FR-3)
    display_name: str | None = None
    budget: Decimal | None = None                         # money is Decimal, never float
    target_industries: str | None = None
    experience: str | None = None

    # Retained legal record
    tos_accepted_at: datetime | None = None
    tos_version: str | None = None

    # Erasure-ready (data_protection.md §3) — anonymize-in-place, never hard-delete
    deleted_at: datetime | None = None

    created_at: datetime = Field(default_factory=_utcnow)


class SandboxItem(SQLModel, table=True):
    """Throwaway Milestone-0 row — proves the DB pipeline; removed at M1 slice 11."""

    id: int | None = Field(default=None, primary_key=True)
    note: str
    created_at: datetime = Field(default_factory=_utcnow)
