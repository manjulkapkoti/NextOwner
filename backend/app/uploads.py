"""The upload seam — one validator, one storage instance, every hostile file.

M2 built the rule set (`security.md` §2): a content-type **and** extension
whitelist, a magic-byte check so a whitelisted type cannot smuggle a different
file, a streamed size ceiling that never materializes more than one chunk over
the limit, and a server-generated key so the client filename never touches a
path. It lived inline in `routers/listings.py` because there was exactly one
upload route.

M10 adds a second one (`POST /api/verification/documents`, spec 010 D5 — "a
narrower reuse of the same seam"), and D5's whole claim is that the two routes
**cannot** differ. Two copies of an upload validator is the one shape that
guarantees they eventually do: a magic signature added for a new type, or a
tightened extension check, lands on one route and not the other, and the weaker
copy becomes the way in. So the rules move here and both routes call them.

`storage` is module-level for the same reason it was module-level in
`listings.py` — one backend per process, the swappable seam for horizontal
scale (blocker #2). Now it is genuinely one per process rather than one per
router, and both callers share the confinement `storage.py` enforces.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func
from sqlmodel import Session, SQLModel, select

from .config import ALLOWED_UPLOAD_TYPES, settings
from .errors import PayloadTooLarge, UnsupportedMediaType
from .ratelimit import RateLimiter
from .storage import LocalDiskStorageBackend

# One storage backend per process — the swappable seam (horizontal-scale #2).
storage = LocalDiskStorageBackend(settings.upload_dir)

# **One** upload rate limiter for **both** document routes (pre-011 R8), keyed
# per user. It lives here for the same reason the validator does: two instances
# that agree today are the shape that drifts, and here the drift is invisible —
# each route would still refuse at its own cap while the caller quietly enjoys
# double the budget `upload_rate_limit_max` promises. One instance makes the
# sharing true by construction rather than by two modules agreeing.
#
# Complements the *stored* quota below: `enforce_upload_quota` bounds how much a
# caller keeps, this bounds how fast it arrives — which is what actually narrows
# the read-then-insert race that quota check accepts (spec 010 D11).
_upload_limiter = RateLimiter(
    max_attempts=settings.upload_rate_limit_max,
    window_seconds=settings.upload_rate_limit_window_seconds,
    name="upload",
)

ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg"}

_UPLOAD_CHUNK = 1024 * 1024           # 1 MB read chunk

# Magic bytes — the actual content must match its declared type, so a whitelisted
# content-type can't smuggle a different file (defense that matters at M5, when a
# buyer downloads a seller's doc, and again at M10, when an admin opens a
# stranger's proof-of-funds file).
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


async def read_validated_upload(file: UploadFile) -> tuple[bytes, str]:
    """Validate a hostile upload and return ``(bytes, storage suffix)``.

    Raises `UnsupportedMediaType` (415) for a type/extension outside the
    whitelist or content that does not match its declared type, and
    `PayloadTooLarge` (413 `file_too_large`) above `settings.max_upload_bytes`.

    The read is streamed with a hard ceiling: never more than one chunk over the
    limit is held, so a huge upload cannot exhaust memory (the DoS the M2 appsec
    review caught). `main.py`'s Content-Length middleware is the pre-parse outer
    guard, and a reverse proxy is the third layer in production.

    Returns the *suffix* rather than a path or a key — choosing where the bytes
    land is the caller's business (a listing id at M2, a user id at M10), and
    the confinement of whatever it chooses is `storage.py`'s.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if file.content_type not in ALLOWED_UPLOAD_TYPES or ext not in ALLOWED_EXTS:
        raise UnsupportedMediaType("Only PDF, PNG, or JPEG documents are allowed")

    buf = bytearray()
    while chunk := await file.read(_UPLOAD_CHUNK):
        buf.extend(chunk)
        if len(buf) > settings.max_upload_bytes:
            raise PayloadTooLarge("File exceeds the maximum upload size")
    data = bytes(buf)

    # The bytes must actually match the declared type (not just its header).
    if not any(data.startswith(sig) for sig in _MAGIC[file.content_type]):
        raise UnsupportedMediaType("File content does not match its declared type")

    return data, ALLOWED_UPLOAD_TYPES[file.content_type]


def display_filename(client_filename: str | None) -> str:
    """The stored, display-only name — path components stripped at the boundary.

    Never used to build a path (the key is server-generated), but stripping here
    keeps a traversal string out of the column in the first place, so nothing
    downstream has to remember that the value is hostile.
    """
    return os.path.basename(client_filename or "upload")


def enforce_upload_quota(
    session: Session,
    *,
    model: type[SQLModel],
    owner_column: Any,
    owner_id: int,
    new_size_bytes: int,
) -> None:
    """Refuse an upload that would take an owner past their document quota (D8).

    The `milestones.md` M10 fold-in asks for *"a per-listing upload count /
    total-size quota (extends the M2 upload rules)"* — read literally, that is
    M2's listing-document route, which caps each file (`max_upload_bytes`) but
    never the *set*: twenty files of 10 MB were always allowed. Spec 010 D8
    honours both surfaces the bullet plausibly means rather than quietly
    narrowing it to the new route, and "per-listing" generalizes to **per owning
    entity** — a listing for `ListingDocument`, a user for
    `BuyerVerificationDocument`. That generalization is the whole reason this is
    one function taking an owner column instead of two checks that agree today.

    Two limits, one error, because a client's remedy is the same for both
    ("upload less"): `PayloadTooLarge(code="upload_quota_exceeded")` — 413, but a
    **different code** from M2's `file_too_large`, since "this file is too big"
    and "you have too much stored" need different UI copy and the machine code is
    what a client branches on.

    `settings` is read here, at call time, not captured at import: the caps are
    operational knobs, and a value frozen into a default argument is one a
    deployment cannot actually change.

    Called **after** the bytes are read and validated but **before**
    `storage.save`, so a refused upload leaves nothing on disk. The count check
    could technically run earlier and spare the server the read, but the size
    check cannot — and splitting the quota across two places in the request is
    exactly the drift this shared helper exists to prevent. `max_request_bytes`
    is what actually bounds the read.

    Deliberately *not* here (spec 010 D11): any exemption for a resubmission. A
    buyer sitting at the cap when they are rejected is refused, and the way out
    is an admin, not a retry — accepted and recorded, with the defaults chosen
    (20 documents / 50 MB against a review cycle that needs one) so it is a DoS
    control rather than a workflow limit.
    """
    existing_count, existing_bytes = session.exec(
        select(func.count(), func.coalesce(func.sum(model.size_bytes), 0))
        .select_from(model)
        .where(owner_column == owner_id)
    ).one()

    if existing_count + 1 > settings.max_documents_per_owner:
        raise PayloadTooLarge("Document quota exceeded", code="upload_quota_exceeded")
    if existing_bytes + new_size_bytes > settings.max_total_upload_bytes_per_owner:
        raise PayloadTooLarge("Document quota exceeded", code="upload_quota_exceeded")


def attachment_headers(original_filename: str) -> dict[str, str]:
    """The response headers for serving a stored file back (M2 rule, M10 reuse).

    The *serving* half of the seam, and it is hostile input too: the column holds
    whatever a multipart parser accepted, and `a";\\r\\nX-Injected: 1.pdf` passes
    an extension whitelist unharmed. Dropped straight into a header it breaks out
    of `filename="…"` and starts a header of its own — so the name is run through
    `basename`, stripped of quotes and CR/LF, and capped.

    **Returns the whole header, not just the sanitized name**, so `attachment` is
    not something a caller can forget or downgrade to `inline`. That word is the
    control that stops a buyer-supplied file from rendering same-origin, which
    matters more here than at M2: a verification document is uploaded by the
    least-trusted party in the product and opened by an admin.

    The 200-char cap is a bound on a header we did not author, nothing subtler.
    """
    safe = os.path.basename(original_filename)
    safe = safe.replace('"', "").replace("\r", "").replace("\n", "")[:200]
    return {"Content-Disposition": f'attachment; filename="{safe or "document"}"'}
