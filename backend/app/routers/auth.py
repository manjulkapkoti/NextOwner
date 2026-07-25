"""Auth router — register, login, me, role upgrade.

Never trusts the client for `is_admin` or the role flags (they're derived
server-side). Login returns a uniform 401 for both unknown-email and
wrong-password, and burns equal time in both paths, so neither the body nor the
latency reveals whether an account exists (`security.md` §6 — enumeration).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..errors import BadRequest, Conflict, RateLimited, Unauthorized
from ..mailer import queue_email
from ..models import User, _utcnow
from ..permissions import get_current_user
from ..ratelimit import RateLimiter
from ..schemas import (
    ForgotPasswordRequest,
    LoginResponse,
    ResetPasswordRequest,
    RoleUpdate,
    UserRead,
    UserRegister,
    VerifyEmailRequest,
)
from ..security import create_access_token, hash_password, verify_password
from ..tokens import (
    issue_email_verification,
    issue_password_reset,
    redeem_email_verification,
    redeem_password_reset,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Module-level limiters → one in-process counter per app. The swappable backend
# (ratelimit.py) is the horizontal-scale seam. Both login AND register are
# limited (security.md §1.1 — brute force on login, signup spam on register).
_login_limiter = RateLimiter(
    max_attempts=settings.login_rate_limit_max,
    window_seconds=settings.login_rate_limit_window_seconds,
)
_register_limiter = RateLimiter(
    max_attempts=settings.register_rate_limit_max,
    window_seconds=settings.register_rate_limit_window_seconds,
)

# A precomputed hash to verify against when the email is unknown, so the unknown
# and wrong-password paths take the same time (no timing oracle).
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/register", response_model=UserRead, status_code=201)
def register(
    body: UserRegister,
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    key = request.client.host if request.client else "unknown"
    if not _register_limiter.check(key):
        raise RateLimited("Too many sign-up attempts — try again later")
    if session.exec(select(User).where(User.email == body.email)).first():
        raise Conflict("Email already registered", code="email_taken")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        is_buyer=body.role == "buyer",
        is_seller=body.role == "seller",
        tos_accepted_at=_utcnow(),
        tos_version=settings.tos_version,
    )
    session.add(user)
    session.flush()                      # assigns user.id for the token row
    # M8 (spec F3, S9): mail the confirmation link. This is **transactional**
    # mail, so it deliberately bypasses the `email_verified` gate that governs
    # notification mail — otherwise verification could never bootstrap. Note
    # where it sits: after the duplicate-email 409 above, so re-registering
    # someone else's address cannot be used to mail them on demand (S9).
    _send_verification(session, user)
    session.commit()
    session.refresh(user)
    return user


def _send_verification(session: Session, user: User) -> None:
    """Issue a verification token and queue its email (shared by register and
    resend). Queued, not sent — it goes out only if the transaction commits,
    so a link can never reference a token row that rolled away."""
    raw = issue_email_verification(session, user)
    queue_email(
        session,
        user.email,
        "Confirm your NextOwner email address",
        "Confirm your address to start receiving NextOwner email:\n\n"
        f"{settings.app_base_url}/verify-email?token={raw}\n\n"
        f"This link expires in {settings.email_verification_token_ttl_hours} hours.\n",
    )


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> LoginResponse:
    key = request.client.host if request.client else "unknown"
    if not _login_limiter.check(key):
        raise RateLimited("Too many login attempts — try again later")

    user = session.exec(select(User).where(User.email == form.username)).first()
    if user is None or user.deleted_at is not None:
        verify_password(form.password, _DUMMY_HASH)          # equalize timing
        raise Unauthorized("Incorrect email or password")
    if not verify_password(form.password, user.password_hash):
        raise Unauthorized("Incorrect email or password")

    _login_limiter.reset(key)
    return LoginResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/nda", response_model=UserRead)
def sign_nda(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    """FR-13 — sign the one platform-wide NDA (click-wrap), spec 005 A1-A4.

    **Idempotent by design (spec 005 D4).** The first signature is the retained
    legal record, so a second call is a no-op that returns the original stamp
    rather than moving it. That is why this is a plain `if ... is None` instead
    of an unconditional write: re-signing must not be able to rewrite when the
    user accepted, or which text they accepted.

    Both values are server-derived — the clock and `settings.nda_version` — so
    there is deliberately **no request body**. A client that sends
    `nda_signed_at` or `nda_version` is ignored entirely (A4, Article 2 #4):
    FastAPI never reads a body this function does not declare.
    """
    if user.nda_signed_at is None:
        user.nda_signed_at = _utcnow()
        user.nda_version = settings.nda_version
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@router.post("/roles", response_model=UserRead)
def add_role(
    body: RoleUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    """FR-2: grant the caller an additional role on their own account."""
    if body.role == "buyer":
        user.is_buyer = True
    else:
        user.is_seller = True
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ── Account lifecycle (M8) — password reset + email verification ─────────────
#
# Moved here from M1 (2026-07-17) because these flows *are* email, and M8 is
# where the email channel is built. `security.md` §7 M8 governs every line.

_forgot_password_limiter = RateLimiter(
    max_attempts=settings.forgot_password_rate_limit_max,
    window_seconds=settings.forgot_password_rate_limit_window_seconds,
)


@router.post("/forgot-password", status_code=202)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Request a reset link (spec G1, G2, G9, G13, X3).

    **Returns the same 202 and the same body no matter what** — whether the
    address is registered, anonymized, or belongs to nobody. That uniformity is
    the entire security property: this endpoint is otherwise a free
    "does an account exist here?" oracle, which is M1's login rule applied to a
    second door.

    The rate limit matters more here than on login, because the cost of abuse
    lands on a **third party**: an attacker who can call this without bound
    mails somebody else's inbox on demand.

    An SMTP failure is swallowed by the queue's `send_safe` and never changes
    the response — surfacing it would recreate the very oracle the uniform 202
    exists to close (X3).
    """
    key = request.client.host if request.client else "unknown"
    if not _forgot_password_limiter.check(key):
        raise RateLimited("Too many password-reset requests — try again later")

    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is not None and user.deleted_at is None:
        raw = issue_password_reset(session, user)
        queue_email(
            session,
            user.email,
            "Reset your NextOwner password",
            "Use this link to choose a new password:\n\n"
            f"{settings.app_base_url}/reset-password?token={raw}\n\n"
            f"It expires in {settings.password_reset_token_ttl_minutes} minutes. "
            "If you didn't ask for this, you can ignore this email.\n",
        )
        session.commit()

    # Identical for every caller. Nothing above may change what is returned.
    return {"status": "accepted"}


@router.post("/reset-password")
def reset_password(
    body: ResetPasswordRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Redeem a reset token and set a new password (spec G3-G8, G11, S7, X4).

    The token arrives in the **body**, never the query string (spec D11): a URL
    parameter is recorded by proxies, access logs, `Referer` headers and
    browser history, which `security.md` §7 M8 rules out.

    `redeem_password_reset` is the only thing that decides whose password this
    changes. The body's other fields cannot influence it — an `email` a caller
    adds is not a field of this schema and is ignored, so a token for user A
    can never touch user B (G6).
    """
    user = redeem_password_reset(session, body.token)
    if user is None:
        # One refusal for missing, expired, used, malformed, and wrong-purpose.
        raise BadRequest("Invalid or expired link", code="invalid_token")

    user.password_hash = hash_password(body.password)
    session.add(user)
    session.commit()
    # Deliberately returns a bare status, **not** the user record. This route is
    # unauthenticated by necessity, and redeeming a token proves control of a
    # mailbox — not that the caller should be handed a profile. Returning
    # `UserRead` here would make an anonymous route a data route for no gain
    # (`security.md` § data minimization); the client's next step is to log in.
    return {"status": "password_reset"}


@router.post("/verify-email")
def verify_email(
    body: VerifyEmailRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Confirm an address (spec H2-H6).

    Reads only `EmailVerificationToken`, so a password-reset token cannot land
    here (H5) — that is spec D4's two-table split doing the work rather than a
    `purpose` check that a future edit could drop.
    """
    user = redeem_email_verification(session, body.token)
    if user is None:
        raise BadRequest("Invalid or expired link", code="invalid_token")

    if user.email_verified_at is None:      # idempotent — the first stamp stands
        user.email_verified_at = _utcnow()
        session.add(user)
    session.commit()
    # Bare status, for the same reason `reset_password` returns one: an
    # unauthenticated route should hand back the minimum that answers the
    # question it was asked.
    return {"status": "email_verified"}


@router.post("/resend-verification", status_code=202)
def resend_verification(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Send a fresh confirmation link (spec H7, H9).

    Authenticated, unlike `forgot-password`, which is what makes a uniform
    response unnecessary here: the caller already proved who they are, so a 409
    for "already verified" reveals nothing they did not know and saves a
    pointless email.
    """
    if user.email_verified_at is not None:
        raise Conflict("This address is already verified", code="already_verified")

    _send_verification(session, user)
    session.commit()
    return {"status": "accepted"}
