"""Password hashing (bcrypt) and JWT mint/verify.

These are pure functions — no request context. The permission *gates* live in
`permissions.py`; this module is the crypto they lean on. Constitution Article 1:
JWTs are issued by our own endpoints, bcrypt for passwords.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from .config import settings


def _bcrypt_input(password: str) -> bytes:
    """SHA-256 → base64 so any-length password fits bcrypt's 72-byte limit.

    bcrypt hard-rejects secrets >72 bytes; feeding it a fixed-length digest (44
    base64 bytes) removes that cliff **without silent truncation** and keeps
    hashing and verifying symmetric. Standard pattern (Django/Dropbox variants).
    """
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    """bcrypt hash (salt included in the digest)."""
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time bcrypt compare; never raises on a malformed hash."""
    try:
        return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str) -> str:
    """Sign a short-lived access token whose `sub` is the user id (a string)."""
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify signature + expiry with the **pinned** algorithm.

    Passing a single-element `algorithms` list is what rejects `alg:none` and
    algorithm-confusion attacks — PyJWT will not accept a token whose header
    algorithm isn't in the list. Raises `jwt.ExpiredSignatureError` /
    `jwt.InvalidTokenError`; the caller maps those to 401.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
