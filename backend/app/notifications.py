"""Notification projection — **the recipient-derivation trust boundary** (M8).

Spec 008 D3: every notification's recipient is computed *here*, from the domain
object, server-side. No router passes a recipient in; no request body can
influence one. That is the whole reason this module exists as a module rather
than a few `session.add(Notification(...))` calls scattered across five
routers — "who is allowed to learn that this happened" is a privilege decision,
and privilege decisions live in one place in this codebase (Article 2 #1).

The rule each helper below encodes is the same one the underlying gate already
enforces, restated for delivery:

- a listing's curation outcome is its **owner's** business;
- an access decision is its **buyer's**; a new request is the **seller's**;
- a message belongs to the conversation's **other** party;
- an offer event belongs to whoever did **not** cause it — with `accept`,
  `decline` and `counter` resolving to the party who proposed the current terms
  (M7's bilateral rule, spec 007 D1), not to a fixed role.

**Titles carry public data only** (spec D2). `listing.headline` is on
`ListingPublic`; `company_name`, message bodies and offer prices are not, and
must never be composed in — a stale notification that outlives a revocation
would otherwise leak the very thing M5's gate exists to protect.
"""

from __future__ import annotations

from sqlmodel import Session, select

from .models import (
    AccessRequest,
    Conversation,
    Listing,
    Notification,
    Offer,
    User,
    _utcnow,
)

# Titles are short, server-composed, and public-only. Kept together so FR-22's
# "notification templates are centrally managed" is literally true of one dict
# rather than aspirationally true of code spread across the routers.
_TEMPLATES: dict[str, str] = {
    "listing_approved": "Your listing “{headline}” is now live",
    "listing_rejected": "Your listing “{headline}” needs changes: {reason}",
    "listing_matched": "New listing matches your saved search: “{headline}”",
    "access_requested": "A buyer requested access to “{headline}”",
    "access_approved": "Your access request for “{headline}” was approved",
    "access_denied": "Your access request for “{headline}” was declined",
    "access_revoked": "Your access to “{headline}” was revoked",
    "message_received": "New message about “{headline}”",
    "offer_submitted": "New offer on “{headline}”",
    "offer_countered": "Your offer on “{headline}” received a counter",
    "offer_accepted": "Your offer on “{headline}” was accepted",
    "offer_declined": "Your offer on “{headline}” was declined",
    "offer_auto_declined": "Your offer on “{headline}” was declined — another offer was accepted",
    "offer_withdrawn": "An offer on “{headline}” was withdrawn",
}


def _headline(session: Session, listing_id: int | None) -> str:
    if listing_id is None:
        return "a listing"
    listing = session.get(Listing, listing_id)
    return listing.headline if listing is not None else "a listing"


def notify(
    session: Session,
    *,
    recipient_id: int,
    type: str,
    listing_id: int | None = None,
    conversation_id: int | None = None,
    offer_id: int | None = None,
    **title_fields: object,
) -> Notification | None:
    """Write one notification. **The only writer of the `notification` table.**

    `recipient_id` is a required keyword because every call site must be seen
    to have derived it — a positional argument is easy to pass through from
    somewhere untrusted, a named one that only this module's helpers supply is
    not.

    Returns `None` when the recipient no longer exists or has been anonymized:
    a delivery record for an erased user is pointless, and the FK would fail
    anyway. The row is **added, not committed** — the caller's transaction owns
    the commit, so a notification can never survive an action that rolled back.
    """
    recipient = session.get(User, recipient_id)
    if recipient is None or recipient.deleted_at is not None:
        return None

    template = _TEMPLATES.get(type)
    if template is None:                       # unknown type = a programming error
        raise ValueError(f"unknown notification type: {type}")

    title = template.format(
        headline=_headline(session, listing_id),
        **{k: v for k, v in title_fields.items()},
    )
    notification = Notification(
        recipient_id=recipient_id,
        type=type,
        title=title,
        listing_id=listing_id,
        conversation_id=conversation_id,
        offer_id=offer_id,
    )
    session.add(notification)
    return notification


# ── per-event recipient derivation ───────────────────────────────────────────


def notify_listing_decision(
    session: Session, listing: Listing, action: str, reason: str | None = None
) -> None:
    """Curation outcome → the listing's owner (spec C1, C2)."""
    notify(
        session,
        recipient_id=listing.owner_id,
        type="listing_approved" if action == "approve" else "listing_rejected",
        listing_id=listing.id,
        reason=reason or "",
    )


def notify_access_requested(session: Session, listing: Listing) -> None:
    """A new access request → the seller, never the requesting buyer (C3)."""
    notify(
        session,
        recipient_id=listing.owner_id,
        type="access_requested",
        listing_id=listing.id,
    )


def notify_access_decision(
    session: Session, access_request: AccessRequest, action: str
) -> None:
    """An access decision → the buyer it was made about (C4, C5, C6)."""
    notify(
        session,
        recipient_id=access_request.buyer_id,
        type={
            "approve": "access_approved",
            "deny": "access_denied",
            "revoke": "access_revoked",
        }[action],
        listing_id=access_request.listing_id,
    )


def notify_message(session: Session, conversation: Conversation, sender_id: int) -> None:
    """A message → the conversation's **other** party (C7, C14).

    The body is deliberately not passed in at all, so there is no argument for
    a future edit to start interpolating (D2).
    """
    listing = session.get(Listing, conversation.listing_id)
    if listing is None:
        return
    recipient_id = (
        conversation.buyer_id if sender_id == listing.owner_id else listing.owner_id
    )
    notify(
        session,
        recipient_id=recipient_id,
        type="message_received",
        listing_id=conversation.listing_id,
        conversation_id=conversation.id,
    )


def _offer_parties(session: Session, offer: Offer) -> tuple[int, int] | None:
    """`(buyer_id, seller_id)` for an offer, or `None` if the listing is gone."""
    listing = session.get(Listing, offer.listing_id)
    if listing is None:
        return None
    return offer.buyer_id, listing.owner_id


def notify_offer(session: Session, offer: Offer, action: str) -> None:
    """An offer event → the party who did not cause it (C8-C13).

    The recipient follows M7's bilateral rule (spec 007 D1) rather than a fixed
    role: `proposed_by_role` records who authored *this row's* terms, so a
    decision lands on the proposer and a new proposal lands on the counterparty.
    Encoding it from `proposed_by_role` — instead of assuming "offers come from
    buyers" — is what makes a seller's counter behave correctly.
    """
    parties = _offer_parties(session, offer)
    if parties is None:
        return
    buyer_id, seller_id = parties
    proposer_id = buyer_id if offer.proposed_by_role == "buyer" else seller_id
    counterparty_id = seller_id if offer.proposed_by_role == "buyer" else buyer_id

    # A new proposal reaches the counterparty; a resolution reaches the proposer.
    recipient_id = {
        "submitted": counterparty_id,
        "countered": counterparty_id,
        "withdrawn": counterparty_id,
        "accepted": proposer_id,
        "declined": proposer_id,
        "auto_declined": proposer_id,
    }[action]

    notify(
        session,
        recipient_id=recipient_id,
        type=f"offer_{action}",
        listing_id=offer.listing_id,
        offer_id=offer.id,
    )


def fan_out_saved_searches(session: Session, listing: Listing) -> int:
    """Publication → every buyer whose saved search matches (spec B1-B8).

    Matching runs through **M4's own filter predicate** against this one
    listing, so an alert can never be based on a column browse would not expose
    (S5). Three rules the loop encodes deliberately:

    - the listing's **owner is skipped** (B5) — you do not get alerted about
      your own supply;
    - a buyer already alerted about this listing is **skipped, not re-alerted**
      (B7), because M3's edit→`pending_review`→approve corridor makes a second
      publication reachable;
    - alerts are **forward-only** (D7) — this runs at publication, so a search
      created afterwards never backfills.

    Returns how many notifications were written (used by the caller's logging,
    and it makes the function testable on its own terms).
    """
    from .saved_search_matching import listing_matches, parse_filters
    from .models import SavedSearch

    written = 0
    for saved in session.exec(select(SavedSearch)).all():
        if saved.user_id == listing.owner_id:
            continue
        already = session.exec(
            select(Notification).where(
                Notification.recipient_id == saved.user_id,
                Notification.listing_id == listing.id,
                Notification.type == "listing_matched",
            )
        ).first()
        if already is not None:
            continue
        if not listing_matches(listing, parse_filters(saved.filters_json)):
            continue
        if notify(
            session,
            recipient_id=saved.user_id,
            type="listing_matched",
            listing_id=listing.id,
        ) is not None:
            written += 1
    return written


def mark_all_read(session: Session, user: User) -> int:
    """Mark every unread notification of this caller read (spec E7)."""
    rows = session.exec(
        select(Notification).where(
            Notification.recipient_id == user.id,
            Notification.read_at.is_(None),          # type: ignore[union-attr]
        )
    ).all()
    now = _utcnow()
    for row in rows:
        row.read_at = now
        session.add(row)
    return len(rows)
