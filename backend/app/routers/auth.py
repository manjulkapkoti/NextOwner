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
from ..errors import Conflict, RateLimited, Unauthorized
from ..models import User, _utcnow
from ..permissions import get_current_user
from ..ratelimit import RateLimiter
from ..schemas import LoginResponse, RoleUpdate, UserRead, UserRegister
from ..security import create_access_token, hash_password, verify_password

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
    session.commit()
    session.refresh(user)
    return user


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
