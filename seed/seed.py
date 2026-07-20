"""Seed the local database with a browsable marketplace (M4, spec 004 E1-E3).

An empty marketplace tells a visitor the product is dead, so seeded supply is
not optional polish (`milestones.md` § Scope fold-ins → M4, research synthesis
risk #1).

Two properties this script is built around:

- **`seed(session)` is importable**, so the tests exercise it against the
  per-test in-memory database instead of the developer's real `nextowner.db`.
- **Re-running is safe** (E2). Every seeded listing carries a deterministic
  marker in its private row, so a second run finds them and does nothing rather
  than doubling the marketplace.

Also seeds one buyer (`buyer.seed@example.com`) with the NDA already signed,
three access requests in three different states (approved / requested /
denied), and a short conversation already sitting in the approved one — so
M5's gate and M6's chat have something to look at locally without walking
request → approve → open-chat by hand first (owner request, 2026-07-21).

Everything here is fictional. The script creates only its own seed sellers and
must never be pointed at production data.

Usage:  python -m seed.seed
"""

from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select

# Import the app as `app`, exactly as the backend and its tests do. Importing it
# as `backend.app` instead would load a *second* copy of the module: the
# `Listing` class here would then be a different object from the one the running
# app registered with SQLModel's metadata, and rows seeded through it would not
# be the rows the API reads.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.models import (  # noqa: E402
    AccessRequest,
    Conversation,
    Listing,
    ListingPrivate,
    Message,
    User,
    _utcnow,
)
from app.security import hash_password  # noqa: E402

# Marks a row as seed-generated, so a re-run is a no-op (E2). Stored in the
# private row: it is bookkeeping, and the public card must stay clean.
SEED_MARKER = "nextowner-seed-v1"

SELLER_EMAILS = [
    "dana.seed@example.com",
    "amir.seed@example.com",
    "rowan.seed@example.com",
]

# A buyer with the trust flow already walked (owner request, 2026-07-21): sign
# the NDA, request access to three listings in three different states, and
# leave one conversation with a short exchange already in it — so a fresh
# local database has something for M5/M6 to show without a developer having to
# drive the whole product by hand first.
BUYER_EMAIL = "buyer.seed@example.com"

# (type, headline, description, company, domain)
_TEMPLATES: list[tuple[str, str, str, str, str]] = [
    ("saas", "Profitable B2B scheduling SaaS for clinics",
     "Appointment scheduling used by small medical practices. Low churn, mostly annual contracts.",
     "ClearSlot Systems LLC", "clearslot"),
    ("saas", "Invoicing tool for independent trades",
     "Invoicing and quoting for electricians and plumbers. Growing steadily on word of mouth.",
     "TradeBooks Software Inc", "tradebooks"),
    ("saas", "Email deliverability monitoring service",
     "Monitors inbox placement for marketing teams. Almost entirely self-serve signups.",
     "InboxWatch Ltd", "inboxwatch"),
    ("saas", "Applicant tracking for small agencies",
     "Lightweight hiring pipeline for recruiting shops under twenty seats.",
     "HireLane Corp", "hirelane"),
    ("saas", "Uptime and status-page service",
     "Status pages and downtime alerts for developer teams. Runs largely unattended.",
     "PulsePage LLC", "pulsepage"),
    ("ecommerce", "DTC specialty coffee subscription",
     "Single-origin coffee shipped monthly. Strong repeat purchase rate and an engaged list.",
     "Northbound Roasters LLC", "northboundroasters"),
    ("ecommerce", "Pet supply store with private-label line",
     "Durable dog toys, half private label. Established supplier relationships.",
     "Ruff Standard Goods", "ruffstandard"),
    ("ecommerce", "Ergonomic desk accessories brand",
     "Standing-desk mats and monitor risers sold direct and through one marketplace channel.",
     "Upright Works Inc", "uprightworks"),
    ("ecommerce", "Outdoor cooking equipment shop",
     "Cast iron and camp cookware. Highly seasonal with a strong fourth quarter.",
     "Emberfield Supply Co", "emberfield"),
    ("content", "Niche publishing site on home automation",
     "Long-form reviews and guides. Revenue from display ads and affiliate links.",
     "Wired Cottage Media", "wiredcottage"),
    ("content", "Personal finance newsletter",
     "Twice-weekly newsletter with a large engaged list. Sponsorship-funded.",
     "Ledger & Latte Media", "ledgerandlatte"),
    ("content", "Recipe site focused on slow cooking",
     "Evergreen recipe archive with steady organic search traffic.",
     "Low & Slow Kitchen", "lowandslow"),
    ("agency", "SEO retainer agency for local services",
     "Recurring retainers with dentists and law firms. Small contractor bench.",
     "Anchor Point Digital", "anchorpointdigital"),
    ("agency", "Shopify design and build studio",
     "Storefront builds and ongoing care plans for mid-size merchants.",
     "Fold Studio LLC", "foldstudio"),
    ("marketplace", "Regional equipment rental marketplace",
     "Connects contractors with idle equipment owners. Takes a percentage per booking.",
     "Sitelend Holdings", "sitelend"),
]


def _money(value: int | float) -> Decimal:
    """Money is always Decimal, never float — including in fixtures."""
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _already_seeded(session: Session) -> bool:
    return session.exec(
        select(ListingPrivate).where(ListingPrivate.detailed_financials.like(f"%{SEED_MARKER}%"))
    ).first() is not None


def _ensure_sellers(session: Session) -> list[User]:
    sellers: list[User] = []
    for email in SELLER_EMAILS:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password("correct horse battery staple"),
                is_seller=True,
                display_name=email.split(".")[0].title(),
                tos_accepted_at=_utcnow(),
                tos_version="v1",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        sellers.append(user)
    return sellers


def _ensure_buyer(session: Session) -> User:
    """The seed buyer, NDA already signed — B1/D3-style setup with no request
    to click through, since the point is to skip the manual walk."""
    from app.config import settings

    user = session.exec(select(User).where(User.email == BUYER_EMAIL)).first()
    if user is None:
        user = User(
            email=BUYER_EMAIL,
            password_hash=hash_password("correct horse battery staple"),
            is_buyer=True,
            display_name="Buyer Seed",
            tos_accepted_at=_utcnow(),
            tos_version="v1",
            nda_signed_at=_utcnow(),
            nda_version=settings.nda_version,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _seed_access_and_chat(session: Session, buyer: User, live_listings: list[Listing]) -> None:
    """Three access-request states + one conversation with messages already
    in it, so M5's gate and M6's chat both have something to look at locally
    without walking the request → approve → open-chat flow by hand first.

    Direct model construction, matching this script's own precedent for
    listings (`seed()` never drives the real submit/approve endpoints either)
    — a seed script optimizes for "fast, obviously fictional data," not for
    proving a transition is reachable, which is the test suite's job.
    """
    if len(live_listings) < 3:
        return  # not enough live listings yet to pick three distinct ones from

    # Idempotent on its own (E2's rule, extended): no longer covered by the
    # listing marketplace's early return now that the two run independently,
    # so this function needs its own "already did this" check.
    if session.exec(select(AccessRequest).where(AccessRequest.buyer_id == buyer.id)).first() is not None:
        return

    approved_listing, requested_listing, denied_listing = live_listings[:3]

    approved_request = AccessRequest(
        listing_id=approved_listing.id,
        buyer_id=buyer.id,
        status="approved",
        decided_at=_utcnow(),
        decided_by_id=approved_listing.owner_id,
    )
    session.add(approved_request)
    session.add(AccessRequest(listing_id=requested_listing.id, buyer_id=buyer.id, status="requested"))
    session.add(
        AccessRequest(
            listing_id=denied_listing.id,
            buyer_id=buyer.id,
            status="denied",
            decided_at=_utcnow(),
            decided_by_id=denied_listing.owner_id,
        )
    )
    session.commit()

    # Mirrors approve_access_request's own side effect (M6, spec 006 A1): the
    # conversation exists only because this request is approved.
    conversation = Conversation(listing_id=approved_listing.id, buyer_id=buyer.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)

    for sender_id, text in (
        (approved_listing.owner_id, "Thanks for requesting access — happy to answer any questions."),
        (buyer.id, "Appreciate it. Is the churn number trailing twelve months or last quarter?"),
        (approved_listing.owner_id, "Trailing twelve months — quarter-over-quarter has actually been lower."),
    ):
        session.add(Message(conversation_id=conversation.id, sender_id=sender_id, text=text))
    session.commit()


def seed(session: Session, *, count: int = 32) -> int:
    """Create a browsable marketplace, a seed buyer, and that buyer's access
    requests + one conversation. Returns the number of listings created (`0`
    if the marketplace half was already seeded).

    Idempotent, but as **two independent checks**, not one (E2, extended
    2026-07-21): the listing marketplace detects its own marker, and the
    buyer/access/chat fixtures detect their own prior existence — so running
    this against a database that already has listings (seeded before this
    capability existed) still adds the buyer fixtures instead of leaving them
    permanently unreachable behind the marketplace's own early return.

    Guarded on the **session's own bound engine**, not on global settings, so
    the check travels with the capability: any caller handing this function a
    session — a startup hook, a migration step, an engineer copy-pasting the
    test fixture's two lines — is checked, not just `python -m seed.seed`. The
    branch review's re-verification round caught that guarding only the CLI
    entry point left the write path itself open (spec E5).
    """
    driver = session.get_bind().url.drivername
    if not driver.startswith("sqlite"):
        raise SystemExit(
            f"Refusing to seed: the session is bound to {driver!r}, not local SQLite. "
            "This script creates accounts with a password committed to the repository."
        )

    buyer = _ensure_buyer(session)
    created = 0

    # The listing marketplace and the buyer/access/chat fixtures are
    # idempotent **independently** (owner request, 2026-07-21) — not one
    # early return covering both. A database seeded before this capability
    # existed already has its listings, so gating the buyer fixtures behind
    # "listings already seeded" would make them permanently unreachable on
    # any database that predates this change; each half checks its own state
    # instead.
    if _already_seeded(session):
        live_listings = list(session.exec(select(Listing).where(Listing.status == "live")).all())
    else:
        live_listings = _seed_listings(session, count=count)
        created = count

    _seed_access_and_chat(session, buyer, live_listings)

    return created


def _seed_listings(session: Session, *, count: int) -> list[Listing]:
    """The listing half of `seed()` (spec 004 E1-E2) — split out so `seed()`
    itself can decide, per the note above, whether this half needs to run at
    all. Returns every `live` listing created, for `_seed_access_and_chat`."""
    rng = random.Random(20260719)          # fixed seed → reproducible fixtures
    sellers = _ensure_sellers(session)
    now = datetime.now(UTC)
    live_listings: list[Listing] = []

    for i in range(count):
        kind, headline, description, company, domain = _TEMPLATES[i % len(_TEMPLATES)]
        # Later copies of a template get a suffix so headlines stay distinct.
        suffix = "" if i < len(_TEMPLATES) else f" ({i // len(_TEMPLATES) + 1})"

        mrr = rng.randrange(2_000, 40_000, 500)
        ttm_revenue = mrr * 12
        ttm_profit = int(ttm_revenue * rng.uniform(0.25, 0.65))
        asking_price = int(ttm_profit * rng.uniform(2.2, 4.1))

        # Most seeded listings are live so browse looks populated; a handful sit
        # in other states so the seller dashboard and admin queue have something
        # real to show too.
        if i < count - 5:
            status, published_at = "live", now - timedelta(days=rng.randint(1, 120))
        else:
            status, published_at = rng.choice(["draft", "pending_review", "paused"]), None

        listing = Listing(
            owner_id=sellers[i % len(sellers)].id,
            status=status,
            type=kind,
            headline=headline + suffix,
            description=description,
            asking_price=_money(asking_price),
            ttm_revenue=_money(ttm_revenue),
            ttm_profit=_money(ttm_profit),
            mrr=_money(mrr),
            churn_pct=_money(round(rng.uniform(0.8, 6.5), 2)),
            customers=rng.randint(40, 2400),
            published_at=published_at,
        )
        session.add(listing)
        session.commit()
        session.refresh(listing)

        session.add(
            ListingPrivate(
                listing_id=listing.id,
                company_name=company,
                website_url=f"https://{domain}{suffix.strip(' ()')}.example.com",
                # The marker lives here, never on the public card.
                detailed_financials=f'{{"source": "{SEED_MARKER}"}}',
            )
        )
        session.commit()
        if status == "live":
            live_listings.append(listing)

    return live_listings


def main() -> None:
    from app.config import settings
    from app.db import engine, init_db

    # Refuse to write anywhere but a local SQLite file.
    #
    # The seed sellers' password is a constant in this file, so it is public to
    # anyone who can read the repo. That is fine for a throwaway local database
    # and unacceptable anywhere else: run this against a shared or deployed DB
    # and it silently creates real `is_seller=True` accounts whose credentials
    # everyone knows. The guard is here rather than in `seed()` so the tests can
    # still drive the function directly against their in-memory session.
    if not settings.database_url.startswith("sqlite"):
        raise SystemExit(
            "Refusing to seed: DATABASE_URL is not a local SQLite database.\n"
            "This script creates accounts with a password that is committed to "
            "the repository, so it must never run against a shared or deployed "
            "database."
        )

    init_db()
    with Session(engine) as session:
        created = seed(session)
    if created:
        print(
            f"Seeded {created} listings, a buyer ({BUYER_EMAIL}), three access "
            "requests (approved/requested/denied), and a conversation with messages."
        )
    else:
        print("Already seeded — nothing to do.")


if __name__ == "__main__":
    main()
