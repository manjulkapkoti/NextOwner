"""M2 — Document download, owner-only (spec 002 acceptance criteria E1–E2).

E3 (path confinement) is a storage-backend unit test in test_storage_port.py —
the download URL takes an integer doc_id, not a filename, so there's no path to
traverse at the HTTP layer; confinement is enforced in the adapter.
"""

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _upload(client, listing_id, headers):
    return client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": ("pnl.pdf", _PDF, "application/pdf")},
        headers=headers,
    )


def test_e1_owner_downloads_own_document_as_attachment(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    doc_id = _upload(client, listing_id, h).json()["id"]
    r = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=h)
    assert r.status_code == 200
    # Served as a download, never inline (no HTML execution).
    assert "attachment" in r.headers.get("content-disposition", "").lower()


def test_e2_downloading_another_users_document_is_404(client, auth_headers, make_listing):
    owner = auth_headers(email="owner@example.com")
    listing_id = make_listing(owner).json()["id"]
    doc_id = _upload(client, listing_id, owner).json()["id"]
    r = client.get(
        f"/api/listings/{listing_id}/documents/{doc_id}",
        headers=auth_headers(email="attacker@example.com"),
    )
    assert r.status_code == 404          # buyer NDA-gated access is M5; owner-only here
