"""File storage — behind a swappable backend (horizontal-scale blocker #2).

Local disk is the MVP implementation and it is **per-instance state**: instance A
writes a file, instance B can't serve it. That's why storage sits behind
`StorageBackend` — an object-storage (S3-class) backend is constructed
differently, not a rewrite, and the routers never learn the difference.

**Path confinement lives here** (`security.md` §2), not in the routers: the
stored name is server-generated (a uuid), the client filename never touches a
path, and every resolved path is asserted inside the uploads base.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """The seam. A shared-store backend implements the same contract."""

    def save(self, listing_id: int, data: bytes, suffix: str) -> str: ...
    def open(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalDiskStorageBackend:
    """Writes under ``{base_dir}/{listing_id}/{uuid}{suffix}``; confines every
    path to the base."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()

    def _resolve_within_base(self, key: str) -> Path:
        """Resolve ``key`` against the base and reject anything that escapes it
        (``..``, absolute paths, symlink games)."""
        target = (self._base / key).resolve()
        if not target.is_relative_to(self._base):
            raise ValueError("path escapes the uploads base")
        return target

    def save(self, listing_id: int, data: bytes, suffix: str) -> str:
        # Server-generated name — the client filename is NEVER used in the path.
        key = f"{int(listing_id)}/{uuid.uuid4().hex}{suffix}"
        target = self._resolve_within_base(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return key

    def open(self, key: str) -> bytes:
        return self._resolve_within_base(key).read_bytes()

    def delete(self, key: str) -> None:
        target = self._resolve_within_base(key)
        if target.exists():
            os.remove(target)
