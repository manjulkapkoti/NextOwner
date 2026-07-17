"""Health router — the liveness probe.

``GET /api/health`` is unauthenticated and leaks nothing. (The M0 sandbox pair
that used to live here was deleted at M1 slice 11 — the DB write→read path is
now proven by the auth tests.)
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no auth, no data, leaks nothing."""
    return {"status": "ok"}
