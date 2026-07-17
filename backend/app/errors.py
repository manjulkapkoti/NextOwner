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


class RateLimited(AppError):
    status_code, code = 429, "rate_limited"
