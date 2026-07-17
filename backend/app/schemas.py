"""Pydantic request/response models.

The public/private split (constitution Article 2 #2) is enforced here by schema:
`UserRead` simply has no `password_hash` field, so it *cannot* leak. Write models
list only client-settable fields, so mass-assignment of `is_admin`/`owner_id` is
impossible **by schema**, not by runtime filtering (`security.md` §6).
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr
from sqlmodel import SQLModel

Role = Literal["buyer", "seller"]


# ── Auth (M1) ────────────────────────────────────────────────────────────────

class UserRegister(SQLModel):
    """Register body — only client-settable fields. No `is_admin`, no role flags
    directly: `role` is mapped to a flag server-side, so escalation is impossible."""

    email: EmailStr
    password: str
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
