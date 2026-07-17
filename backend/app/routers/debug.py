"""Test-only debug router — mounted only when `settings.enable_debug_routes`.

Its sole purpose is to give the 500-contract tests (G1/G3) a route that raises,
so the generic-error handler can be exercised over HTTP. It grants no data and no
privilege — it is not a backdoor — and it is **off by default**, so it never
mounts in production (`security.md` §6 — no test-only routes in prod).
"""

from fastapi import APIRouter

router = APIRouter(tags=["debug"])


@router.get("/_debug/boom")
def boom() -> None:
    raise RuntimeError("intentional test explosion — exercises the 500 handler")
