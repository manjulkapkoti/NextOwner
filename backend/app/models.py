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

from sqlalchemy import String, TypeDecorator, UniqueConstraint
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

    # Retained legal records. The NDA pair (M5) is the same class as the ToS
    # pair: stamped once, never re-stamped, and `nda_version` records *which*
    # text was signed (spec 005 D4). Re-signing is idempotent — the first
    # signature is the record.
    tos_accepted_at: datetime | None = None
    tos_version: str | None = None
    nda_signed_at: datetime | None = None
    nda_version: str | None = None

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
    # Set by admin at M3; indexed at M4 because it is the public browse's
    # default ordering column, so every anonymous request sorts on it.
    published_at: datetime | None = Field(default=None, index=True)


class ListingPrivate(SQLModel, table=True):
    """Confidential data — owner-only in M2, NDA-gated at M5. Never on a public
    response_model."""

    listing_id: int = Field(foreign_key="listing.id", primary_key=True)
    company_name: str
    website_url: str
    detailed_financials: str | None = None                # JSON string


class ListingEvent(SQLModel, table=True):
    """Append-only audit of listing state changes (M3, FR-21's audit NFR).

    One row per *completed* transition — never per attempt, so the log records
    what happened rather than what was tried (spec D3). `actor_id` is derived
    from the JWT, never from the request body.

    `from_status`/`to_status` make each row self-contained: a reader knows what
    changed without replaying the whole history. That is also what lets M8
    project notifications from these rows instead of M3 designing a
    notification table five milestones before its only consumer
    (`milestones.md` § Scope fold-ins → M8).

    Append-only by discipline: nothing in the codebase updates or deletes a
    row, and spec D4 asserts both rows survive a second decision. SQLite offers
    no cheap enforcement; a Postgres trigger can add it later if it earns one.
    """

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    actor_id: int = Field(foreign_key="user.id")          # server-derived from the JWT
    action: str                                            # approved | rejected (M12 extends)
    from_status: str
    to_status: str
    reason: str | None = None                              # required for rejections
    created_at: datetime = Field(default_factory=_utcnow)


class AccessRequest(SQLModel, table=True):
    """One buyer's request to see one listing's data room (M5, FR-13).

    **The row `require_private_access` consults.** `status` is the state machine
    — `requested → approved|denied` and `approved → revoked` — and, like every
    other status in this codebase, it changes only inside an endpoint that
    validates the move (Article 2 #3). `buyer_id` is derived from the JWT, never
    from the request body (Article 2 #4).

    The unique constraint on `(listing_id, buyer_id)` is FR-13's "one request per
    buyer-listing pair" made a *database* guarantee rather than a check someone
    can forget to write. It is also what makes a decided request **terminal**:
    a denied or revoked buyer cannot re-request, and re-granting is deliberately
    post-MVP (owner-approved 2026-07-20 — see FR-13 in `docs/requirements.md`).

    `decided_at` / `decided_by_id` are the convenient denormalized "current"
    answer. They are **not** the audit trail: a row that travels
    `requested → approved → revoked` overwrites them, losing *when access was
    granted*. `AccessRequestEvent` below is the history that survives that.
    """

    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_id", name="uq_accessrequest_listing_buyer"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    buyer_id: int = Field(foreign_key="user.id", index=True)     # server-derived from the JWT
    status: str = Field(default="requested", index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    decided_at: datetime | None = None
    decided_by_id: int | None = Field(default=None, foreign_key="user.id")


class AccessRequestEvent(SQLModel, table=True):
    """Append-only audit of access decisions (M5, spec 005 D6).

    A direct mirror of `ListingEvent`: one row per *completed* transition, so the
    log records what happened rather than what was tried, and `actor_id` comes
    from the JWT.

    **Why this table exists at all** — the constitution (Article 2 #5) has always
    required timestamped event rows for access decisions, and `security.md` read
    that as satisfied by `access_request.decided_at`. That was true while the only
    decisions were approve and deny: one decision per row, one timestamp. The
    revocation fold-in invalidated it. Once a row can travel
    `requested → approved → revoked`, a single `decided_at` holds only the *last*
    decision — so revoking silently erased when the buyer gained access to the
    financials, which is exactly the question an audit trail exists to answer.
    **General rule recorded in `security.md` § Audit & logging: adding a
    transition to a state machine can invalidate an audit design that was correct
    for the old one.** Spec criterion C10 is the test that fails against the
    superseded design.
    """

    id: int | None = Field(default=None, primary_key=True)
    access_request_id: int = Field(foreign_key="accessrequest.id", index=True)
    actor_id: int = Field(foreign_key="user.id")          # server-derived from the JWT
    # approved | denied | revoked — **decisions only.** Creating a request writes
    # no event: this table protects values a later transition overwrites, and
    # `AccessRequest.created_at` is never overwritten, so a `requested` row would
    # duplicate a fact that cannot drift. M8 reads creation time off the request
    # row itself.
    action: str
    from_status: str
    to_status: str
    created_at: datetime = Field(default_factory=_utcnow)


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
