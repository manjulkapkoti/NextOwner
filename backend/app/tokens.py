"""One-time account tokens — issue, hash, redeem (M8, security.md §7 M8).

**A reset token is account takeover if it leaks**, which is why every rule here
is structural rather than advisory:

- **High entropy.** `secrets.token_urlsafe(32)` is 256 bits from the OS CSPRNG.
  Nothing about the value is guessable or derivable from the user.
- **Hashed at rest** (spec 008 D5). The database stores SHA-256, never the
  token — a leaked dump yields nothing redeemable. SHA-256 and *not* bcrypt on
  purpose: bcrypt defends a low-entropy guess space, and there isn't one here,
  so it would add latency to every redemption and buy nothing.
- **Single use.** `used_at` is stamped on redemption and checked before it.
- **Short lived.** Expiry is checked on every redemption, not just at issue.
- **Uniform failure.** Missing, wrong, expired, already-used and malformed all
  return `None` through the same path, so redemption is never an oracle for
  which tokens exist (spec G12, X4).
- **Two separate tables, so a token cannot be redeemed for the wrong purpose**
  (spec D4). The functions below take no `purpose` argument because there is
  nothing to get wrong: `redeem_password_reset` can only ever read
  `PasswordResetToken`, and a verification token is simply not in that table
  (H5/H6).

Nothing in this module logs a raw token, and no caller may either
(spec G10) — that is the rule the whole design collapses without.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from .config import settings
from .models import EmailVerificationToken, PasswordResetToken, User, _utcnow


def new_token() -> tuple[str, str]:
    """`(raw, hash)`. The raw value leaves in an email and is never persisted."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_expired(expires_at: datetime) -> bool:
    """Compare safely regardless of what the driver hands back.

    SQLite returns **naive** datetimes while `_utcnow()` is timezone-aware, and
    comparing the two raises `TypeError` — a 500 where a 400 belongs. Postgres
    will return aware values after the swap, so normalizing here (rather than
    at every call site) keeps one comparison correct on both.
    """
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= _utcnow()


# ── password reset ───────────────────────────────────────────────────────────


def issue_password_reset(session: Session, user: User) -> str:
    """Mint a reset token, invalidating any still outstanding for this user.

    Superseding the old ones is the point: two live reset links doubles the
    window an intercepted email is useful for, and a user who clicks "forgot
    password" twice means the first mail did not reach them.
    """
    _invalidate_password_resets(session, user.id)
    raw, hashed = new_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=_utcnow()
            + timedelta(minutes=settings.password_reset_token_ttl_minutes),
        )
    )
    return raw


def redeem_password_reset(session: Session, raw: str) -> User | None:
    """Consume a reset token and return its user, or `None` for any failure.

    Every rejection returns `None` — there is deliberately no way for a caller
    to learn *why* a token failed, because "expired" and "never existed" are
    exactly the distinction an attacker enumerating tokens wants (G12).
    """
    row = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw))
    ).first()
    if row is None or row.used_at is not None or _is_expired(row.expires_at):
        return None

    user = session.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        return None

    # Invalidate every outstanding token for this user, not just this one (G8):
    # the password is about to change, which is precisely the event that should
    # void every pending recovery grant.
    _invalidate_password_resets(session, user.id)
    return user


def _invalidate_password_resets(session: Session, user_id: int) -> None:
    now = _utcnow()
    rows = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),          # type: ignore[union-attr]
        )
    ).all()
    for row in rows:
        row.used_at = now
        session.add(row)


# ── email verification ───────────────────────────────────────────────────────


def issue_email_verification(session: Session, user: User) -> str:
    """Mint a verification token, superseding any outstanding one (H7)."""
    _invalidate_email_verifications(session, user.id)
    raw, hashed = new_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=_utcnow()
            + timedelta(hours=settings.email_verification_token_ttl_hours),
        )
    )
    return raw


def redeem_email_verification(session: Session, raw: str) -> User | None:
    """Consume a verification token and return its user, or `None`.

    Reads `EmailVerificationToken` **only**, which is the whole of spec D4's
    cross-purpose defense: a password-reset token is not in this table, so H5
    cannot pass no matter what this function does next.
    """
    row = session.exec(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(raw)
        )
    ).first()
    if row is None or row.used_at is not None or _is_expired(row.expires_at):
        return None

    user = session.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        return None

    _invalidate_email_verifications(session, user.id)
    return user


def _invalidate_email_verifications(session: Session, user_id: int) -> None:
    now = _utcnow()
    rows = session.exec(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),       # type: ignore[union-attr]
        )
    ).all()
    for row in rows:
        row.used_at = now
        session.add(row)
