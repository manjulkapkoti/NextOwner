"""Pydantic request/response models.

The public/private split (constitution Article 2 #2) is enforced here by schema:
`UserRead` simply has no `password_hash` field, so it *cannot* leak. Write models
list only client-settable fields, so mass-assignment of `is_admin`/`owner_id` is
impossible **by schema**, not by runtime filtering (`security.md` §6).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from sqlmodel import SQLModel

from .config import settings

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
    # The frontend reads these off `/api/auth/me` to decide whether "Request
    # access" opens the click-wrap modal or goes straight through (spec 005
    # J1/J2). Safe on this model: it is the caller's own record, never a public
    # or cross-user one.
    nda_signed_at: datetime | None
    nda_version: str | None
    email_verified_at: datetime | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def email_verified(self) -> bool:
        """Derived, never stored twice (M8). The timestamp is the one source of
        truth; this is the boolean the API and the UI actually want."""
        return self.email_verified_at is not None


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
    # Derived from the latest rejection event, not stored on the listing —
    # a column would be a second copy that goes stale the moment a listing is
    # rejected twice (spec C6, plan.md § Schema delta).
    rejection_reason: str | None = None

    @field_serializer("asking_price", when_used="json")
    def _ser_price(self, v: Decimal) -> str:
        return str(v)


# ── Public marketplace (M4) ──────────────────────────────────────────────────

class ListingPublic(SQLModel):
    """The anonymous card — what an unauthenticated stranger may see (FR-6).

    Deliberately a **standalone model, not a subclass of `ListingRead`**. If it
    inherited, a private field added to the owner's view would silently join the
    public one; the inheritance direction that makes `AdminListingRead` correct
    (it *should* get everything) is exactly wrong here. The duplication is the
    control, and spec 004 S3 asserts the absent field set directly so this
    cannot drift unnoticed.

    Absent by construction: `owner_id`, `status`, `company_name`, `website_url`,
    `detailed_financials`. `status` is excluded even though it is not private —
    browse returns `live` rows only, so the field would be a constant that tells
    a caller nothing while creating a channel for a future state to leak by
    accident (spec D2). M12 may add a deliberate public "under offer" flag.
    """

    id: int
    type: str
    headline: str
    description: str
    asking_price: Decimal
    ttm_revenue: Decimal
    ttm_profit: Decimal
    mrr: Decimal
    churn_pct: Decimal
    customers: int
    published_at: datetime | None = None

    @field_serializer(*_MONEY_FIELDS, when_used="json")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)


class ListingQuery(SQLModel):
    """Browse query parameters, validated at the boundary (security.md §2).

    The `limit` ceiling is the DoS control (spec 004 S7): because it lives on
    the schema, an over-limit request is refused by Pydantic *before* a query is
    built, and the refusal is an explicit 422 rather than a silent clamp — a
    clamp hides the caller's mistake and makes the ceiling invisible.

    Every filter is optional and bounded. `q` is length-capped so a pathological
    search term can't become an expensive scan, and its LIKE metacharacters are
    escaped in the router — a bare `%` would otherwise match the whole table.
    """

    q: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=40)
    min_price: Decimal | None = Field(default=None, ge=0, max_digits=14)
    max_price: Decimal | None = Field(default=None, ge=0, max_digits=14)
    min_profit: Decimal | None = Field(default=None, max_digits=14)   # may be negative
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class ListingPage(SQLModel):
    """A page of public listings. `total` is the count *before* limit/offset, so
    the UI can paginate without a second endpoint."""

    items: list[ListingPublic]
    total: int
    limit: int
    offset: int


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


# ── M5 — access requests (NDA gate) ──────────────────────────────────────────

class AccessRequestRead(SQLModel):
    """A request as its own buyer, or its listing's seller, sees it.

    Carries **no buyer identity** (spec 005 S3): the buyer already knows who
    they are, and the seller gets a profile through `AccessRequestWithBuyer`,
    never an email. Keeping this model free of identity fields means a leak
    would have to be *added* deliberately rather than merely forgotten.
    """

    id: int
    listing_id: int
    status: str
    created_at: datetime
    decided_at: datetime | None


class ListingPrivateRead(SQLModel):
    """The data room — what the NDA gate unlocks (FR-15).

    Standalone, **not** a subclass of `ListingRead`, for the same reason
    `ListingPublic` is (spec 004 D2): inheritance would let a field added to the
    owner's view silently join a gated payload. Here the duplication is cheap —
    three fields — and the independence is the control.
    """

    listing_id: int
    company_name: str
    website_url: str
    detailed_financials: str | None = None


class BuyerProfile(SQLModel):
    """What a seller learns about a buyer when deciding (FR-14).

    **No email, by construction** (spec 005 G3/S3). The seller needs enough to
    judge whether to open their books — budget, sector, experience — and contact
    details are not that; chat (M6) is the channel, once they have decided. The
    absence of the field *is* the control, exactly as with `UserRead` and
    `password_hash`.

    **No verification field either** (spec 005 D5). M10 owns buyer verification
    and its fold-in already covers surfacing the badge here. A placeholder now
    would be an unenforced flag, which `security.md` §7 M8 rightly calls
    decoration.
    """

    display_name: str | None
    budget: Decimal | None
    target_industries: str | None
    experience: str | None

    @field_serializer("budget", when_used="json")
    def _ser_budget(self, v: Decimal | None) -> str | None:
        return None if v is None else str(v)


class AccessRequestWithBuyer(SQLModel):
    """A row in the seller's queue: the request plus who is asking."""

    id: int
    listing_id: int
    status: str
    created_at: datetime
    decided_at: datetime | None
    buyer: BuyerProfile


# ── M6 — chat ──────────────────────────────────────────────────────────────

class ConversationSummary(SQLModel):
    """A row in the caller's conversation list (spec 006 I1-I3).

    No email for either participant (S2) — a display name is the only
    identity-adjacent field, the same minimization `BuyerProfile` applies.
    """

    id: int
    listing_id: int
    listing_headline: str
    counterpart_display_name: str | None
    unread_count: int
    last_message_at: datetime | None


class MessageRead(SQLModel):
    """One chat message (spec 006 G1-G2). `sender_id` is a bare integer —
    the frontend already knows both participants from the conversation
    summary it came from; comparing this to the caller's own id is how it
    tells "mine" from "theirs" (J3)."""

    id: int
    conversation_id: int
    sender_id: int
    text: str
    created_at: datetime


# ── M7 — offers / LOI ────────────────────────────────────────────────────────

class OfferTerms(SQLModel):
    """The structured terms shared by a fresh offer and a counter (spec 007
    D6) — `OfferCreate`/`OfferCounter` are the same shape under two names.

    No `listing_id`/`buyer_id`/`status`/`proposed_by_role` here: those come
    from the path, the JWT, and the server — never the body (A6, S3).
    """

    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    structure: str = Field(min_length=1, max_length=settings.offer_structure_max_chars)
    contingencies: str | None = Field(
        default=None, max_length=settings.offer_contingencies_max_chars
    )
    proposed_close_date: date


class OfferCreate(OfferTerms):
    """`POST /listings/{listing_id}/offers` body."""


class OfferCounter(OfferTerms):
    """`POST /offers/{offer_id}/counter` body — identical shape to
    `OfferCreate` (D6): a counter is a fresh proposal, not a patch."""


class OfferRead(SQLModel):
    """An offer as either of its two parties sees it (`GET /my/offers`,
    spec 007 F).

    **No `buyer_id`** (the caller already knows it's their own — mirrors
    `AccessRequestRead`'s minimalism, spec 005) and **no `decided_by_id`**
    ("who decided" is implied by role, not a raw id).
    """

    id: int
    listing_id: int
    parent_offer_id: int | None
    proposed_by_role: str
    status: str
    price: Decimal
    structure: str
    contingencies: str | None
    proposed_close_date: date
    created_at: datetime
    decided_at: datetime | None

    @field_serializer("price", when_used="json")
    def _ser_price(self, v: Decimal) -> str:
        return str(v)


class OfferWithBuyer(SQLModel):
    """A row in the seller's per-listing queue (`GET /my/listings/{id}/offers`,
    spec 007 G1).

    Standalone, **not** a subclass of `OfferRead` — the same independence
    `AccessRequestWithBuyer`/`ListingPublic` keep from their own base shapes
    (spec 004 D2): a seller-only view is a different trust boundary than the
    buyer's own read, so growing one must never silently grow the other.
    **Carries `buyer_id`** (unlike `OfferRead`) alongside the nested
    `BuyerProfile` — this view is seller-only, so the id is not a leak, and
    the frontend needs it to group rows into per-buyer threads.

    No verification field on `buyer` — same D5 deferral to M10 spec 005
    already made.
    """

    id: int
    listing_id: int
    buyer_id: int
    parent_offer_id: int | None
    proposed_by_role: str
    status: str
    price: Decimal
    structure: str
    contingencies: str | None
    proposed_close_date: date
    created_at: datetime
    decided_at: datetime | None
    buyer: BuyerProfile

    @field_serializer("price", when_used="json")
    def _ser_price(self, v: Decimal) -> str:
        return str(v)


# ── Notifications, saved searches & account lifecycle (M8) ───────────────────

class NotificationRead(SQLModel):
    """One inbox row (spec 008 S3).

    **`recipient_id` is deliberately absent.** It is always the caller — the
    gate guarantees that — so exposing it adds nothing a client can use and
    gives a future refactor a place to leak someone else's id. Same reasoning
    as `UserRead`'s missing `password_hash`: the absence *is* the control.

    Nothing private appears here either, because nothing private is ever
    written (spec D2) — this model does not have to strip anything, which is a
    stronger position than stripping correctly.
    """

    id: int
    type: str
    title: str
    listing_id: int | None
    conversation_id: int | None
    offer_id: int | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountRead(SQLModel):
    """The nav badge's number. Field name matches `ConversationRead`'s existing
    `unread_count` so the two badges read the same way."""

    unread_count: int


class NotificationQuery(SQLModel):
    """Inbox query parameters, bounded at the boundary.

    The `limit` ceiling is the DoS control M4's `ListingQuery` established, and
    it is an explicit 422 rather than a silent clamp for the same reason: a
    clamp hides the caller's mistake and makes the ceiling invisible (E8, X5).
    """

    unread: bool = False
    limit: int = Field(default=20, ge=1, le=settings.notifications_page_limit)
    offset: int = Field(default=0, ge=0)


class SavedSearchFilters(BaseModel):
    """The stored filter set — a strict subset of M4's browse filters.

    `extra="forbid"` is the security control, not a nicety: it is what makes a
    filter naming a `ListingPrivate` column (`company_name`) a 422 at the
    boundary rather than something the matcher has to remember to reject
    (spec A7, S5). The alert engine can only ever match on columns the public
    browse already exposes.
    """

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=40)
    min_price: Decimal | None = Field(default=None, ge=0, max_digits=14)
    max_price: Decimal | None = Field(default=None, ge=0, max_digits=14)
    min_profit: Decimal | None = Field(default=None, max_digits=14)

    @model_validator(mode="after")
    def _price_range_is_coherent(self) -> "SavedSearchFilters":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot exceed max_price")
        return self


class SavedSearchCreate(SQLModel):
    """Create body. No `user_id` field, so a client cannot assign one (A6)."""

    name: str = Field(min_length=1, max_length=80)
    filters: SavedSearchFilters


class SavedSearchRead(SQLModel):
    id: int
    name: str
    filters: SavedSearchFilters
    created_at: datetime


class WatchlistEntryRead(SQLModel):
    """One row of the caller's watchlist (M9, FR-12) — the entry joined to its
    listing's public card.

    Deliberately a **standalone model**, not a subclass of `ListingPublic` or
    `ListingRead`, for exactly the reason `ListingPublic`'s docstring gives:
    inheritance would silently join a private field added to one model onto
    this one. The duplication is the control, and spec 009 W11 asserts the
    absent field set directly so it cannot drift unnoticed.

    Absent by construction, the same list `ListingPublic` excludes: `owner_id`,
    `status`, `company_name`, `website_url`, `detailed_financials`. `status` is
    excluded for the same reason it is there — every row returned is already
    known-`live` by construction of the query (D3), so the field would be a
    constant that tells a caller nothing while opening a channel for a future
    state to leak by accident.

    `added_at` is the entry's `created_at`, not the listing's — the listing's
    own age is already carried by `published_at`.
    """

    listing_id: int
    added_at: datetime
    type: str
    headline: str
    description: str
    asking_price: Decimal
    ttm_revenue: Decimal
    ttm_profit: Decimal
    mrr: Decimal
    churn_pct: Decimal
    customers: int
    published_at: datetime | None = None

    @field_serializer(*_MONEY_FIELDS, when_used="json")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)


class ForgotPasswordRequest(SQLModel):
    email: EmailStr


class ResetPasswordRequest(SQLModel):
    """Reset body. The token is a **body field, never a query parameter**
    (spec 008 D11): a URL parameter lands in access logs, `Referer` headers and
    browser history, which `security.md` §7 M8 forbids outright."""

    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(SQLModel):
    token: str = Field(min_length=1, max_length=512)


# ── M10 — buyer verification (the manual Persona mock) ───────────────────────
#
# Naming note: these are **buyer** verification (a proof-of-funds document an
# admin reviews), not `VerifyEmailRequest` above (a token redemption, M8). Two
# unrelated state machines that share a word in prose; the models keep them apart.


class VerificationDocumentRead(SQLModel):
    """One submitted proof-of-funds file, as its uploader and an admin see it.

    **No `storage_key`** (spec 010 S9), and its absence is the control — the same
    construction as `UserRead` and `password_hash`. The key is `{owner}/{uuid}`:
    returning it would hand a caller both a live user-id enumeration and the exact
    shape of the paths behind the download route, which is the first thing anyone
    probing for a static-serving mistake or a traversal wants.

    **No `user_id` either**, unlike M2's `DocumentRead.listing_id`. Every surface
    this appears on already establishes whose documents these are — the caller's
    own (`VerificationRead`) or the queue row's buyer — so the field would be
    redundant on one and a cross-user identifier on the other.
    """

    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class VerificationRead(SQLModel):
    """The caller's own verification state (`GET /api/verification`).

    Carries the *outcome* and nothing else about the submission — the one part of
    `data_protection.md` §4's letter this milestone can keep while holding the
    document itself (spec 010 D9). `verification_reason` is echoed back
    deliberately: a rejection the buyer cannot act on is worse than none (the same
    reasoning that makes M3's listing-rejection reason required), and it is
    length-capped at the boundary it is written through for exactly that reason
    (`verification_reason_max_chars`).
    """

    verification_status: str
    verification_reviewed_at: datetime | None
    verification_reason: str | None
    documents: list[VerificationDocumentRead]
