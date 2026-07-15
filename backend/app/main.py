"""NextOwner API — FastAPI application entry point.

The API is the only door to the data (constitution Article 2 #1). Every router
mounts under the ``/api`` prefix (WebSockets under ``/ws``); locally the Vite
dev proxy forwards both to this app, so there is no CORS anywhere.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from .db import init_db
from .routers import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create tables on startup."""
    init_db()
    yield


app = FastAPI(title="NextOwner API", lifespan=lifespan)

# REST routers mount under /api; WebSocket routers will mount under /ws.
app.include_router(health.router, prefix="/api")
