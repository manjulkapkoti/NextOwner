"""Admin router — a minimal probe so `require_admin` has a testable surface at M1.

The real admin queue arrives at M3. This route exists only to prove the second
trust boundary: non-admins get 403 (D1), and admin status is re-read from the DB
so a post-issuance promotion is honored (D2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import User
from ..permissions import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
def admin_ping(user: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok", "admin": user.email}
