"""M2 — Document uploads, treated as hostile (spec 002 acceptance criteria D1–D6)."""

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _upload(client, listing_id, headers, filename="pnl.pdf", content=_PDF, content_type="application/pdf"):
    return client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_d1_owner_uploads_valid_pdf(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = _upload(client, listing_id, h)
    assert r.status_code == 201
    body = r.json()
    assert body["content_type"] == "application/pdf"
    assert "id" in body                              # a ListingDocument row


def test_d2_uploading_to_another_users_listing_is_404(client, auth_headers, make_listing):
    listing_id = make_listing(auth_headers(email="owner@example.com")).json()["id"]
    r = _upload(client, listing_id, auth_headers(email="attacker@example.com"))
    assert r.status_code == 404


def test_d3_disallowed_type_is_415(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = _upload(client, listing_id, h, filename="evil.html", content=b"<script>", content_type="text/html")
    assert r.status_code == 415


def test_d4_oversized_upload_is_413(client, auth_headers, make_listing):
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    big = b"%PDF-1.4\n" + b"A" * (11 * 1024 * 1024)   # > 10 MB
    r = _upload(client, listing_id, h, content=big)
    assert r.status_code == 413


def test_d5_traversal_filename_cannot_escape_uploads(client, auth_headers, make_listing):
    """The client filename is never used to build the path — a server name is
    generated, so `../../../etc/passwd` is neutralized, not honored."""
    h = auth_headers()
    listing_id = make_listing(h).json()["id"]
    r = _upload(client, listing_id, h, filename="../../../etc/passwd.pdf")
    assert r.status_code == 201
    # The document is retrievable (stored under a confined, server-generated path)...
    doc_id = r.json()["id"]
    dl = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=h)
    assert dl.status_code == 200


def test_d6_unauthenticated_upload_is_401(client, auth_headers, make_listing):
    listing_id = make_listing(auth_headers()).json()["id"]
    r = _upload(client, listing_id, {})              # no auth
    assert r.status_code == 401
