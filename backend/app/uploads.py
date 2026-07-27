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

from fastapi import UploadFile

from .config import ALLOWED_UPLOAD_TYPES, settings
from .errors import PayloadTooLarge, UnsupportedMediaType
from .storage import LocalDiskStorageBackend

# One storage backend per process — the swappable seam (horizontal-scale #2).
storage = LocalDiskStorageBackend(settings.upload_dir)

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
