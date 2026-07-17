"""NextOwner API — FastAPI application entry point.

The API is the only door to the data (constitution Article 2 #1). Every router
mounts under the ``/api`` prefix (WebSockets under ``/ws``); locally the Vite dev
proxy forwards both to this app, so there is no CORS anywhere.

This module also installs the error contract (`docs/error_handling.md`): a
request-id per request, an `AppError` handler rendering the 4xx shape, and a
catch-all that turns any unhandled exception into a generic 500 that leaks
nothing.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .db import init_db
from .errors import AppError
from .routers import admin, auth, debug, health, profile

logger = logging.getLogger("nextowner")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create tables on startup."""
    init_db()
    yield


app = FastAPI(title="NextOwner API", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Assign a request id (honoring an inbound ``X-Request-ID``) and echo it."""
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex[:12]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Render the 4xx business/permission contract (detail + machine code)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: a generic 500 with a request id, and **no** internals.

    The full traceback is logged server-side keyed by the request id; the client
    gets only a safe message + the id (for support). Never leaks stack, SQL, or
    file paths (`security.md` §Info leakage).
    """
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or f"req_{uuid4().hex[:12]}"
    )
    logger.exception("unhandled error [request_id=%s]", request_id)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end.", "request_id": request_id},
    )


# REST routers mount under /api; WebSocket routers will mount under /ws.
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

if settings.enable_debug_routes:            # test-only; off in production
    app.include_router(debug.router, prefix="/api")
