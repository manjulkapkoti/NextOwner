"""Pydantic request/response models.

The public/private split (constitution Article 2 #2) is enforced here by schema:
`UserRead` simply has no `password_hash` field, so it *cannot* leak. Write models
list only client-settable fields, so mass-assignment of `is_admin`/`owner_id` is
impossible **by schema**, not by runtime filtering (`security.md` §6).
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr, Field, field_serializer, field_validator
from sqlmodel import SQLModel

Role = Literal["buyer", "seller"]
_MONEY_FIELDS = ("asking_price", "ttm_revenue", "ttm_profit", "mrr", "churn_pct")


# ── Auth (M1) ────────────────────────────────────────────────────────────────

class UserRegister(SQLModel):
    """Register body — only client-settable fields. No `is_admin`, no role flags
    directly: `role` is mapped to a flag server-side, so escalation is impossible."""

    email: EmailStr
    # Length bounds enforced at the boundary (security.md §2): a floor against
    # weak passwords, a ceiling against request-size abuse. bcrypt's 72-byte
    # limit is handled by the SHA-256 pre-hash in security.py, so long
    # passphrases work rather than 500-ing.
    password: str = Field(min_length=8, max_length=128)
    role: Role


class RoleUpdate(SQLModel):
    role: Role


class ProfileUpdate(SQLModel):
    """FR-3 profile fields only. No `email`, `user_id`, or `is_admin` — a client
    that sends them finds them ignored (they aren't fields of this model)."""

    display_name: str | None = None
    budget: Decimal | None = None
    target_industries: str | None = None
    experience: str | None = None


class UserRead(SQLModel):
    """Response model — note the absence of `password_hash`. That absence is the
    control (B4)."""

    id: int
    email: str
    is_buyer: bool
    is_seller: bool
    is_admin: bool
    display_name: str | None
    budget: Decimal | None
    target_industries: str | None
    experience: str | None
    tos_accepted_at: datetime | None
    created_at: datetime


class LoginResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"


# ── Listings (M2) ────────────────────────────────────────────────────────────

class ListingCreate(SQLModel):
    """Create body — public + private fields. **No** `owner_id`, `status`, or
    `id`: those are server-controlled, so mass-assignment is impossible by
    schema, not by runtime filtering."""

    type: str
    headline: str
    description: str
    asking_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    ttm_revenue: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    ttm_profit: Decimal = Field(max_digits=14, decimal_places=2)          # may be negative
    mrr: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    churn_pct: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    customers: int = Field(ge=0)
    company_name: str
    website_url: str
    detailed_financials: str | None = None


class ListingUpdate(SQLModel):
    """Partial edit — every field optional, and again no `owner_id`/`status`."""

    type: str | None = None
    headline: str | None = None
    description: str | None = None
    asking_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    ttm_revenue: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    ttm_profit: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    mrr: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    churn_pct: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    customers: int | None = Field(default=None, ge=0)
    company_name: str | None = None
    website_url: str | None = None
    detailed_financials: str | None = None


class ListingRead(SQLModel):
    """The owner's full view (public + private + status). Money serialized as
    strings so precision is exact over the wire (A7)."""

    id: int
    owner_id: int
    status: str
    type: str
    headline: str
    description: str
    asking_price: Decimal
    ttm_revenue: Decimal
    ttm_profit: Decimal
    mrr: Decimal
    churn_pct: Decimal
    customers: int
    created_at: datetime
    published_at: datetime | None = None
    company_name: str | None = None
    website_url: str | None = None
    detailed_financials: str | None = None

    @field_serializer(*_MONEY_FIELDS, when_used="json")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)


class ListingSummary(SQLModel):
    """Dashboard row (`GET /my/listings`)."""

    id: int
    headline: str
    status: str
    asking_price: Decimal
    created_at: datetime

    @field_serializer("asking_price", when_used="json")
    def _ser_price(self, v: Decimal) -> str:
        return str(v)


class DocumentRead(SQLModel):
    id: int
    listing_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class AdminListingRead(ListingRead):
    """The curation queue row (M3, spec A5).

    Extends the owner's view rather than redefining it, so a field added to
    ListingRead cannot silently go missing from the admin's judgement surface.
    Private company detail is included deliberately — an admin cannot curate a
    listing they cannot see — which makes this the only schema outside the
    owner's own routes that carries it before M5's NDA gate. **Never mount it
    on a route guarded by anything weaker than `require_admin`.**
    """


class RejectRequest(SQLModel):
    """A rejection must tell the seller what to fix (spec C3).

    `min_length` alone would accept "   ", so the validator strips first — a
    whitespace-only reason is a blank one, and rejecting it here means the
    state machine never sees a rejection the seller cannot act on.
    """

    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("A rejection reason is required")
        return v
