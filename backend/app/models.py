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

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Index, String, TypeDecorator, UniqueConstraint, text
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

    # M8. A timestamp, not a bool, matching the two pairs above — one stored
    # source of truth for the fact; `UserRead` derives the boolean the API
    # exposes. Spec D6: this gates outbound *notification* mail and nothing
    # else yet (transactional mail must still reach an unverified address, or
    # verification could never bootstrap).
    email_verified_at: datetime | None = None

    # M10 buyer verification (spec 010 D1) — **not** M8's email verification
    # above. Two unrelated state machines that both got called "verification" in
    # prose: `email_verified_at` is a token redemption, this is a proof-of-funds
    # document an admin reviewed.
    #
    # A status string rather than a timestamp-as-boolean like the three pairs
    # above, because this machine has four values, not two:
    # `unverified → pending → verified | rejected`, plus `rejected → pending`
    # (resubmit) and `verified → rejected` (admin revoke). Indexed because the
    # admin queue selects on it.
    #
    # All three are **server-controlled**: no request body in this milestone has a
    # field they could be assigned from (`ProfileUpdate` does not declare them,
    # and the reject route's model carries only `reason`), so mass-assignment is
    # impossible by schema rather than filtered at runtime (spec 010 S1).
    #
    # `verification_reason` holds only the *current* decision and is overwritten
    # by the next one — which is exactly what `BuyerVerificationEvent` exists to
    # preserve (Article 2 #5, spec 010 D6).
    verification_status: str = Field(default="unverified", index=True)
    verification_reviewed_at: datetime | None = None
    verification_reason: str | None = None

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
    # Records **first** publication and is never restamped — a re-listed deal
    # that fell through keeps its original date (M12, spec 012 D7).
    published_at: datetime | None = Field(default=None, index=True)
    # ── The close (M12, spec 012 D4) ────────────────────────────────────────
    # Written only by `POST /listings/{id}/mark-sold`, in the same conditional
    # UPDATE that claims the `under_offer → sold` transition, and never
    # overwritten afterwards (`sold` is terminal in both directions).
    #
    # `final_price` is **derived server-side from the accepted offer's price** —
    # a client that sends one is ignored (Article 2 #4, spec 012 S1). It is a
    # stored column rather than a read-time join onto the `completed` offer
    # because a re-listed listing can sell twice: after that, "the completed
    # offer" is no longer unique, and a derivation would have to encode an
    # implied ordering. The column records the answer at the one moment it is
    # unambiguous. Neither field is on `ListingPublic` — a sale price is never
    # anonymous data (spec 012 S11).
    sold_at: datetime | None = None
    final_price: Decimal | None = Field(default=None, sa_type=Money)


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
    # approved | rejected (M3) · sold | fell_through (M12, shipped 2026-07-28)
    action: str
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


class Conversation(SQLModel, table=True):
    """One chat thread per `(listing, buyer)` pair (M6, FR-16).

    Created only by `approve_access_request` (spec 006 A1) — never directly.
    The seller is `listing.owner_id`, not duplicated here, the same choice
    `AccessRequest` makes. `*_last_read_at` is two columns rather than a
    participant table (spec 006 D3): a conversation has exactly two possible
    participants, the same shape `AccessRequest` already has, so a general
    multi-participant table would model a feature (group chat) nothing here
    asks for.
    """

    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_id", name="uq_conversation_listing_buyer"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    buyer_id: int = Field(foreign_key="user.id", index=True)     # from the approved AccessRequest
    created_at: datetime = Field(default_factory=_utcnow)
    buyer_last_read_at: datetime | None = None
    seller_last_read_at: datetime | None = None


class Message(SQLModel, table=True):
    """One chat message (M6, FR-16). `sender_id` is derived from the
    WebSocket connection's verified token, never from the message payload
    (spec 006 C3, `security.md` §1.5)."""

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    sender_id: int = Field(foreign_key="user.id")
    text: str
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


class Offer(SQLModel, table=True):
    """One proposal in a negotiation (M7, FR-17, spec 007 D1/D6).

    A negotiation is a **chain** of rows linked by `parent_offer_id`, never a
    single row mutated in place: a buyer's original ask and a seller's counter
    are different proposals with different terms, and collapsing them into one
    row would silently lose whichever one arrived first the moment a second
    counter landed (spec D1).

    `buyer_id` is the negotiation's buyer — read from the JWT at root creation
    and carried unchanged onto every counter in the chain, never from the
    request body (A6). `proposed_by_role` records who authored **this row's**
    terms (`"buyer"` or `"seller"`), server-derived from which endpoint created
    it — this is what `offer_role_for`'s bilateral decision check reads (D1).

    `status` is `submitted → accepted|declined|withdrawn|countered`; all four
    are terminal for this row, and `countered` additionally spawns a child row.
    No *plain* unique constraint on `(listing_id, buyer_id)` — unlike
    `AccessRequest`, many historical rows per pair are expected. D7's "at most
    one active (`submitted`) offer per pair" is enforced by a **partial** unique
    index (`WHERE status = 'submitted'`), so terminal rows coexist freely while
    two live offers cannot; the endpoint's application-level pre-check gives the
    common case a clean 409, and the index is the concurrent-create backstop
    (`security.md` §6 — the check-then-insert TOCTOU a prior read can't close).
    """

    __table_args__ = (
        # A PARTIAL unique index, not a plain one: it constrains only rows with
        # `status = 'submitted'`, so an old declined/withdrawn/countered offer
        # for the same pair is unaffected. SQLite has supported partial indexes
        # since 3.8.0 (2013), Postgres far longer — the two `*_where` kwargs give
        # the identical DB-level guarantee on both, surviving the eventual swap.
        Index(
            "uq_offer_one_active_per_pair",
            "listing_id",
            "buyer_id",
            unique=True,
            sqlite_where=text("status = 'submitted'"),
            postgresql_where=text("status = 'submitted'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    buyer_id: int = Field(foreign_key="user.id", index=True)     # server-derived from the JWT
    parent_offer_id: int | None = Field(default=None, foreign_key="offer.id")
    proposed_by_role: str                                         # "buyer" | "seller"
    status: str = Field(default="submitted", index=True)
    price: Decimal = Field(sa_type=Money)
    structure: str
    contingencies: str | None = None
    proposed_close_date: date
    created_at: datetime = Field(default_factory=_utcnow)
    decided_at: datetime | None = None
    decided_by_id: int | None = Field(default=None, foreign_key="user.id")


class Notification(SQLModel, table=True):
    """One delivered notification (M8, spec 008 D1/D2/D3, FR-22).

    **A delivery record, not an audit row.** `ListingEvent`,
    `AccessRequestEvent` and `OfferEvent` remain the immutable history; this
    table is a *projection* of them, mutable (`read_at`), per-recipient, and
    safely deletable. It must never become a second, drifting account of what
    happened — when the two disagree, the event tables are the fact.

    **It carries no private payload (D2).** `title` is composed server-side
    from public data only (`listing.headline` is on `ListingPublic`;
    `company_name` is not), and no message body, offer price, or
    `ListingPrivate` value is ever copied in. That is what makes a stale row
    safe: a buyer whose access was revoked may still hold a notification, but
    following it lands on `require_private_access` / `conversation_role_for`
    and is refused (spec S1). Copying content in here would have quietly built
    a bypass around M5's crown-jewel gate.

    `recipient_id` is **always derived server-side** from the domain object
    (`notifications.py`), never from a request body — Article 2 #4 applied to
    the one field that decides who reads this.

    The three nullable link FKs are the click-through target, kept as real
    foreign keys rather than a polymorphic `(kind, id)` pair: referential
    integrity, and it is what lets the "don't alert twice for one listing"
    rule (spec B7) be a **partial unique index** instead of a check someone can
    forget — the same construction `Offer` already uses for its one-active-
    offer rule, so both survive the Postgres swap.
    """

    __table_args__ = (
        # Partial: constrains only `listing_matched` rows, so the many other
        # notification types about the same listing (approved, offer, message)
        # are unaffected. M3's edit→`pending_review`→approve corridor makes a
        # second publication genuinely reachable, and without this each pass
        # would re-alert every matching buyer.
        Index(
            "uq_notification_one_alert_per_listing",
            "recipient_id",
            "listing_id",
            unique=True,
            sqlite_where=text("type = 'listing_matched'"),
            postgresql_where=text("type = 'listing_matched'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    recipient_id: int = Field(foreign_key="user.id", index=True)   # server-derived
    type: str = Field(index=True)
    title: str                                                      # public data only
    listing_id: int | None = Field(default=None, foreign_key="listing.id", index=True)
    conversation_id: int | None = Field(default=None, foreign_key="conversation.id")
    offer_id: int | None = Field(default=None, foreign_key="offer.id")
    read_at: datetime | None = Field(default=None)                  # the one mutable field
    created_at: datetime = Field(default_factory=_utcnow)


class SavedSearch(SQLModel, table=True):
    """A buyer's stored browse filters (M8, FR-11).

    `filters_json` is a JSON blob (the shape `ListingPrivate.detailed_financials`
    already established) and is **never interpolated into SQL**: it is parsed
    back through the same Pydantic model M4's browse route validates, and
    matching re-uses that predicate builder. That is what makes "a filter can
    only ever name a public column" a schema fact rather than an allow-list
    someone maintains (spec S5) — reaching into `ListingPrivate` here would
    turn saved searches into the identity oracle M4's keyword search refuses to
    be.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)         # server-derived
    name: str
    filters_json: str
    created_at: datetime = Field(default_factory=_utcnow)


class WatchlistEntry(SQLModel, table=True):
    """One user's favorited listing (M9, FR-12, spec 009).

    The simplest caller-owned artifact in the codebase: a boolean membership
    fact with no state machine, no payload, and no fan-out cost. `user_id` is
    **server-derived from the JWT** — none of the three M9 routes takes a
    request body at all, so the ownership field is not merely stripped, it has
    no field to be assigned from (spec S4).

    The unique constraint on `(user_id, listing_id)` is what makes D1's
    idempotent add safe under a race: the endpoint's check-then-insert handles
    the common path, and the constraint is the backstop for two concurrent
    `POST`s from a double-clicked heart icon — a caught `IntegrityError` is
    treated as "already present," which *is* the D1 semantics, not a 409.
    A **plain** unique index, unlike `Offer`/`Notification`'s partial ones:
    there is no soft-delete or status column here to scope it to (D7 —
    erasure hard-deletes the row, because a favorite is not evidence).

    No `status` column and no audit table by design: nothing here overwrites a
    value a later reader needs (Article 2 #5).
    """

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_watchlistentry_user_listing"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)         # server-derived
    listing_id: int = Field(foreign_key="listing.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow)           # `added_at` on the wire


class PasswordResetToken(SQLModel, table=True):
    """A single-use password-reset grant (M8, security.md §7 M8).

    **Deliberately a separate table from `EmailVerificationToken`** rather than
    one table with a `purpose` column (spec 008 D4): two tables make
    cross-purpose redemption *structurally* impossible instead of dependent on
    every lookup remembering to filter. The codebase already prefers
    duplication over sharing when a boundary is at stake —
    `conversation_role_for` duplicates the NDA-gate query so M6 cannot regress
    M5 — and this is the same trade for the same reason.

    `token_hash` is **SHA-256 of a 256-bit `secrets.token_urlsafe(32)`**, not
    bcrypt (D5): there is no low-entropy guess space for a slow KDF to defend,
    so bcrypt would add latency to every redemption and buy nothing. Hashing at
    all is the point — a leaked database must not yield usable tokens.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(unique=True, index=True)      # never the raw token
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class EmailVerificationToken(SQLModel, table=True):
    """A single-use address-confirmation grant (M8). Twin of
    `PasswordResetToken` above — see its docstring for why these are two tables
    and not one (spec 008 D4)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class BuyerVerificationDocument(SQLModel, table=True):
    """A buyer's uploaded proof-of-funds file (M10, FR-3/F11, spec 010 D5).

    The same shape as `ListingDocument`, keyed by `user_id` instead of
    `listing_id` — and stored through the same seam: `StorageBackend.save()`'s
    first positional parameter names *an owning entity*, not specifically a
    listing, so `save(user.id, ...)` reuses M2's confinement, server-generated
    uuid key and never-statically-served path verbatim. `storage_key` is opaque
    and never leaves the server (spec 010 S9); `original_filename` is
    display-only and NEVER used to build a path.

    **This milestone's most sensitive artifact** — a financial/identity document
    we hold ourselves rather than handing to a KYC vendor, which is an explicit,
    recorded deviation from `data_protection.md` §4 for the MVP (spec 010 D9):
    F11 ships *manual* review, and an admin cannot review a file no system of
    ours holds. Erasure therefore **hard-deletes** row + file (D10), unlike the
    audit table below.

    No status column: the submission's state lives on `User.verification_status`
    (one home per fact), because the decision is about the *buyer*, not about a
    particular file — a resubmission adds a row and moves the user's status.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)   # server-derived from the JWT
    # `{user_id}/{uuid}{suffix}` — the SAME directory namespace `ListingDocument`
    # uses for `{listing_id}/…`, because both go through `save()`'s one owning-id
    # slot. Harmless for confidentiality (uuid names; access is authorized off
    # this row, never off the path) but a real hazard for D10's erasure: delete
    # each key individually via `storage.delete(doc.storage_key)` and NEVER
    # `rmtree({base}/{user_id})`, which would destroy listing `user_id`'s data
    # room. Closing this structurally means a namespaced key, which changes the
    # `StorageBackend` port's `int` contract (that `int()` coercion is itself a
    # control) — deliberately not done mid-milestone; see spec 010 D10.
    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=_utcnow)


class BuyerVerificationEvent(SQLModel, table=True):
    """Append-only audit of buyer-verification decisions (M10, spec 010 D6).

    Justified against Article 2 #5's test — *what does this preserve that the row
    itself loses?* `User.verification_reason` holds only the current decision, so
    a rejection reason is silently overwritten the moment a resubmission is later
    approved. "Was this buyer ever rejected, and why" is precisely the question a
    future fraud review asks and the `User` row alone cannot answer.
    `from_status` carries the other loss: it is the only thing distinguishing a
    *deny* (`pending → rejected`) from a *revoke* (`verified → rejected`), which
    are the same endpoint by design (D1).

    Mirrors `ListingEvent`: one row per *completed* transition — never per
    attempt, so an illegal move (409) leaves no trace of what was tried — and
    `actor_id` comes from the JWT, never a request body.

    **Decisions only.** A buyer's own upload writes no event: the
    `BuyerVerificationDocument` row is already an unoverwritable record of it,
    and duplicating it here would be the projection-masquerading-as-audit mistake
    M8 warns about.

    Audit-exempt on erasure (D10): ids, status strings, and an operator-authored
    reason — no document content and no buyer-authored PII.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)   # the buyer whose status changed
    actor_id: int = Field(foreign_key="user.id")              # the admin — from the JWT
    action: str                                                # approved | rejected
    from_status: str                                           # pending | verified (D1/X4)
    to_status: str                                             # verified | rejected
    reason: str | None = None                                  # copied at write time
    created_at: datetime = Field(default_factory=_utcnow)


class OfferEvent(SQLModel, table=True):
    """Append-only audit of an offer's negotiation (M7, spec 007 § Schema deltas).

    A direct mirror of `ListingEvent`/`AccessRequestEvent`, with one deliberate
    difference: **this table logs creation too** (`action="submitted"`,
    `from_status=null`), which `AccessRequestEvent` deliberately does not.
    `AccessRequestEvent` exists only to preserve values a later decision
    overwrites on the *same* row; `OfferEvent` is asked to serve a second job —
    it is the narrative of a multi-row negotiation thread (FR-17's "both
    parties see offer history"), and a thread's first chapter ("buyer proposed
    X") is a fact worth a row of its own, because the *next* row in the chain
    is what changes next, unlike `AccessRequest` where the same row's
    `decided_at` is what changes. Every `Offer` row this milestone creates —
    root or counter-spawned child — gets its own `action="submitted"` event at
    the moment it's inserted.
    """

    id: int | None = Field(default=None, primary_key=True)
    offer_id: int = Field(foreign_key="offer.id", index=True)
    actor_id: int = Field(foreign_key="user.id")          # server-derived from the JWT
    # submitted | accepted | declined | withdrawn | countered | auto_declined
    action: str
    from_status: str | None = None        # null only for action="submitted"
    to_status: str
    created_at: datetime = Field(default_factory=_utcnow)


class ValuationLead(SQLModel, table=True):
    """A prospective seller who ran the calculator and left an address (M11,
    FR-23, spec 011).

    The only table in the codebase whose subject is **not a user**. Everything
    else here references someone who registered; this references someone who has
    not — which is the whole point of a lead magnet, and drives three decisions
    that read as omissions unless you know they were chosen:

    - **No `user_id` FK** (D10). Adding one "just in case" would create exactly
      the identity linkage spec S9 exists to prevent: a lead captured by a
      signed-in visitor must not silently become an identified lead.
    - **`email` is indexed but NOT unique** (D7). A unique constraint would
      produce a distinguishable duplicate error, turning a public form into an
      email-enumeration oracle — the same question M1's login and M8's
      forgot-password both refuse to answer. Repeat submissions are bounded by
      the rate limit instead, which refuses without revealing anything.
    - **No event/audit table** (D9). Article 2 #5's test — *what does this
      preserve that the row itself loses?* — returns nothing: a lead has no state
      machine, nothing overwrites it, and it never justifies a decision about
      anybody. It is a marketing artifact, and M8's rule that a projection must
      never become an audit row applies here to a different kind of row.

    `estimate_low`/`estimate_high`/`driver` are **server-computed** and stored
    alongside the inputs (spec L2/S5): this is the number an admin will quote
    back, so a client-supplied one reaching this table is the one mass-assignment
    in the milestone with a lasting consequence.

    **Erasure: hard-delete the rows matching the address** (`data_protection.md`
    §3's per-child-table question, answered in D10). Nothing references a lead, so
    anonymizing in place would leave a row of business figures attached to a
    tombstone with no evidentiary purpose — contrast offers and access requests,
    which are kept for audit with the author anonymized.
    """

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True)                      # PII — never logged (D10)
    type: str
    ttm_revenue: Decimal = Field(sa_type=Money)
    ttm_profit: Decimal = Field(sa_type=Money)
    growth_pct: Decimal = Field(sa_type=Money)
    churn_pct: Decimal = Field(sa_type=Money)
    # Server-computed, never read from the request body (L2/S5).
    estimate_low: Decimal = Field(sa_type=Money)
    estimate_high: Decimal = Field(sa_type=Money)
    driver: str
    # Indexed: the admin list's only ordering is newest-first, and its only
    # bound is a page cap (A1/A2).
    created_at: datetime = Field(default_factory=_utcnow, index=True)
