"""The error hierarchy — one place that maps a failure to (status, machine code).

Endpoints and `permissions.py` raise these instead of scattering `HTTPException`
literals, so status/`code` mapping stays central (`docs/error_handling.md` §2).
The handlers in `main.py` render them as the §1 contract.
"""

from __future__ import annotations


class AppError(Exception):
    """Base: a client-safe failure with an HTTP status and a stable machine code."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.message = message
        self.code = code or self.code
        # Extra response headers the handler in `main.py` must carry onto the
        # response. Empty for every error whose whole contract is the body; a
        # 429's `Retry-After` is the first case where dropping a header would
        # silently break the contract (pre-011 D7).
        self.response_headers: dict[str, str] = {}
        super().__init__(message)


class BadRequest(AppError):
    status_code, code = 400, "bad_request"


class Unauthorized(AppError):
    status_code, code = 401, "unauthorized"


class Forbidden(AppError):
    status_code, code = 403, "forbidden"


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class InvalidTransition(AppError):
    status_code, code = 409, "invalid_transition"


class UnsupportedMediaType(AppError):
    status_code, code = 415, "unsupported_media_type"


class PayloadTooLarge(AppError):
    status_code, code = 413, "file_too_large"


class RateLimited(AppError):
    """429 — plus `Retry-After` (pre-011 D7).

    A caller told to back off but not for how long will poll, which is the
    behavior the limiter exists to prevent. The header is the *only* thing this
    error adds: the body stays the generic `{detail, code}` shape, so a 429 on a
    public route reveals nothing about how the key was derived (R7).
    """

    status_code, code = 429, "rate_limited"

    def __init__(
        self, message: str, *, code: str | None = None, retry_after: int | None = None
    ) -> None:
        super().__init__(message, code=code)
        self.retry_after = retry_after
        if retry_after is not None and retry_after > 0:
            self.response_headers["Retry-After"] = str(int(retry_after))
