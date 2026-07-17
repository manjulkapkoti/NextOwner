"""SQLModel tables — the schema.

`User` (M1) ships **erasure-ready** (`data_protection.md` §3): a `deleted_at`
soft-delete path and nullable PII, so a future GDPR erasure flow anonymizes in
place without breaking referential integrity. The user-facing erasure *endpoint*
is post-MVP; only the schema support lands here.

`Listing` / `ListingPrivate` / `ListingDocument` (M2) are the public/private
split: the anonymous card (`Listing`, served at M4) and the confidential data
(`ListingPrivate` + files, owner-only now, NDA-gated at M5) are separate tables.
Money is `Money` (Decimal stored losslessly as text) — never float.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import String, TypeDecorator
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Timezone-aware UTC now (``datetime.utcnow`` is deprecated in 3.12)."""
    return datetime.now(UTC)


class Money(TypeDecorator):
    """Store ``Decimal`` losslessly as TEXT.

    SQLite has no native decimal type, and SQLAlchemy's ``Numeric`` on SQLite
    round-trips through float (lossy — the exact thing the fold-in forbids).
    Persisting the string representation is lossless here and portable to
    Postgres later (which could switch to native ``NUMERIC``).
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(Decimal(value))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)          # PII — never public, never logged
    password_hash: str                                    # bcrypt — never returned

    # Roles: two flags, not an enum — FR-2 allows holding *both* under one account.
    is_buyer: bool = Field(default=False)
    is_seller: bool = Field(default=False)
    is_admin: bool = Field(default=False)                 # server-only; re-read from DB per request

    # Minimal profile (FR-3)
    display_name: str | None = None
    budget: Decimal | None = None
    target_industries: str | None = None
    experience: str | None = None

    # Retained legal record
    tos_accepted_at: datetime | None = None
    tos_version: str | None = None

    # Erasure-ready (data_protection.md §3) — anonymize-in-place, never hard-delete
    deleted_at: datetime | None = None

    created_at: datetime = Field(default_factory=_utcnow)


class Listing(SQLModel, table=True):
    """Public, anonymous listing card (served at M4). owner_id + status are
    server-controlled — never trusted from the client (Article 2 #4)."""

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    status: str = Field(default="draft", index=True)      # state machine — see routers/listings.py
    type: str
    headline: str
    description: str
    asking_price: Decimal = Field(sa_type=Money)
    ttm_revenue: Decimal = Field(sa_type=Money)
    ttm_profit: Decimal = Field(sa_type=Money)
    mrr: Decimal = Field(sa_type=Money)
    churn_pct: Decimal = Field(sa_type=Money)
    customers: int
    created_at: datetime = Field(default_factory=_utcnow)
    published_at: datetime | None = None                  # set by admin at M3


class ListingPrivate(SQLModel, table=True):
    """Confidential data — owner-only in M2, NDA-gated at M5. Never on a public
    response_model."""

    listing_id: int = Field(foreign_key="listing.id", primary_key=True)
    company_name: str
    website_url: str
    detailed_financials: str | None = None                # JSON string


class ListingDocument(SQLModel, table=True):
    """One row per uploaded file. `storage_key` is opaque (from the storage
    port); `original_filename` is display-only and NEVER used to build a path."""

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=_utcnow)
