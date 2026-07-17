"""M2 — Storage port (spec 002 G1) + path confinement (E3).

Structural + unit tests on the storage seam. The routers never touch the
filesystem or a client filename; all writing/reading goes through this backend,
so the object-storage swap (horizontal-scale blocker #2) is a config change.
"""

import pytest


def test_g1_storage_is_behind_a_swappable_backend():
    from app import storage

    assert hasattr(storage, "StorageBackend")            # the interface
    assert hasattr(storage, "LocalDiskStorageBackend")   # the MVP implementation
    backend = storage.LocalDiskStorageBackend
    # The contract the routers rely on:
    assert hasattr(backend, "save")
    assert hasattr(backend, "open")
    assert hasattr(backend, "delete")


def test_e3_local_backend_confines_writes_to_the_uploads_base(tmp_path):
    """A generated key stays inside uploads/{listing_id}/ — no traversal even
    though the caller passes a hostile suffix."""
    from app.storage import LocalDiskStorageBackend

    backend = LocalDiskStorageBackend(base_dir=str(tmp_path))
    key = backend.save(listing_id=7, data=b"%PDF-1.4 hi", suffix=".pdf")
    resolved = (tmp_path / key).resolve()
    # The stored file is under tmp_path/7/ and cannot be outside the base.
    assert str(resolved).startswith(str((tmp_path / "7").resolve()))
    assert backend.open(key) == b"%PDF-1.4 hi"


def test_e3_open_rejects_a_key_that_escapes_the_base(tmp_path):
    from app.storage import LocalDiskStorageBackend

    backend = LocalDiskStorageBackend(base_dir=str(tmp_path))
    with pytest.raises(Exception):
        backend.open("../../../etc/passwd")              # traversal key rejected
