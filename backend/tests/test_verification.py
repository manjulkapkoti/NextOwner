"""M10 — buyer verification (spec 010): V — the verification core (FR-3/FR-14/F11,
the manual Persona mock) and X — errors & failure modes.

Written failing first: `backend/app/routers/verification.py` (and its schema/model
deltas) do not exist yet, so every route this file calls 404s right now — through
`app/main.py`'s catch-all "no matching route" path, which returns Starlette's bare
`{"detail": "Not Found"}` with no `code` key. That is exactly why every 4xx
assertion below also asserts the machine `code` (per plan.md § Errors): a
status-only assertion on `POST /api/verification/documents` would coincidentally
pass on the *current*, unmounted router (both a real 415 and today's 404 are
"not 2xx"), never turning red at all. Asserting `code` closes that hole, since
`res.json().get("code")` is `None` today and only becomes `"unsupported_media_type"`,
`"upload_quota_exceeded"`, `"already_verified"`, or `"invalid_transition"` once
the real route and its transition logic exist.

The security/abuse half (S1-S9 — cross-user IDOR on the document-download gate,
403s on the admin routes, the 401 sweep, path-traversal, the two schema-leak
tests) lives in `test_verification_security.py`, owned by a parallel agent. This
file is the happy path, the D1 state machine's legal transitions (including the
D3/D1 edges — resubmission after rejection, refusal to re-trigger review once
verified, and the `verified -> rejected` revoke path), the D6 audit-row shape,
D7's badge surfacing on `UserRead` and `BuyerProfile`, the D5 upload-rule reuse,
D8's shared upload quota (parametrized across both surfaces it applies to), and
the X-group failure contract.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# A minimal well-formed PDF — mirrors `test_listing_upload.py`'s `_PDF` and
# `conftest.py`'s `VALID_PDF` (same bytes, redefined locally per the project's
# per-file convention rather than importing across test modules).
_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _listing_doc(client, listing_id, headers, filename="doc.pdf", content=_PDF, content_type="application/pdf"):
    """Upload a document to an owned listing — the M2 route D8 retrofits.

    Mirrors `test_listing_upload.py::_upload`; kept local (not imported across
    test files) per this suite's convention of one small helper per file.
    """
    return client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def _budget_equals(value, expected: str) -> bool:
    """Decimal-tolerant comparison for `AdminVerificationQueueRead.budget`.

    Plan.md's snippet for this model shows no `field_serializer` (unlike
    `BuyerProfile._ser_budget`), so whether `budget` comes back as a JSON string
    ("250000.00") or a bare number (250000.0) is genuinely unspecified by the
    plan. Comparing as `Decimal` is correct under either serialization and does
    not couple this test to a choice the plan never made — see the report back
    to the orchestrator for the flag.
    """
    return Decimal(str(value)) == Decimal(expected)


# ── V — verification core ────────────────────────────────────────────────────


def test_v1_first_submission_moves_to_pending_and_lists_the_document(
    client, auth_headers, submit_verification
):
    """V1 — a fresh buyer's first upload: 201, then `GET /verification` shows
    `pending` with the document listed."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    upload = submit_verification(buyer)
    assert upload.status_code == 201, upload.text

    status = client.get("/api/verification", headers=buyer)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["verification_status"] == "pending"
    assert len(body["documents"]) == 1
    assert body["documents"][0]["original_filename"] == "proof-of-funds.pdf"


def test_v2_a_user_with_no_submission_ever_is_unverified_with_no_documents(
    client, auth_headers
):
    """V2 — no upload has ever happened: `unverified` + an empty document list."""
    user = auth_headers(email="nobody@example.com", role="buyer")

    res = client.get("/api/verification", headers=user)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verification_status"] == "unverified"
    assert body["documents"] == []


def test_v3_admin_queue_lists_a_pending_submission_with_buyer_profile_and_documents(
    client, auth_headers, admin_headers, pending_verification
):
    """V3 — the admin queue shows the buyer's profile fields and the submitted
    document's metadata, so an admin can curate without a second lookup."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    profile = client.put(
        "/api/profile",
        json={
            "display_name": "Jamie Buyer",
            "budget": "250000.00",
            "target_industries": "saas, ecommerce",
            "experience": "Two prior acquisitions",
        },
        headers=buyer,
    )
    assert profile.status_code == 200, profile.text
    buyer_id, document_id = pending_verification(buyer)

    res = client.get("/api/admin/verifications", headers=admin_headers())

    assert res.status_code == 200, res.text
    rows = res.json()
    row = next((r for r in rows if r["user_id"] == buyer_id), None)
    assert row is not None, rows
    assert row["display_name"] == "Jamie Buyer"
    assert _budget_equals(row["budget"], "250000.00")
    assert row["target_industries"] == "saas, ecommerce"
    assert row["experience"] == "Two prior acquisitions"
    assert any(d["id"] == document_id for d in row["documents"])


def test_v4_admin_approve_moves_pending_to_verified_and_records_the_event(
    client, auth_headers, admin_headers, pending_verification, verification_events, user_id
):
    """V4 — approve: status -> `verified`, `verification_reviewed_at` stamped,
    and a `BuyerVerificationEvent` row records the transition (D6)."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id, _ = pending_verification(buyer)
    admin = admin_headers()
    admin_id = user_id(admin)

    res = client.post(f"/api/admin/verifications/{buyer_id}/approve", headers=admin)

    assert res.status_code == 200, res.text
    status = client.get("/api/verification", headers=buyer).json()
    assert status["verification_status"] == "verified"
    assert status["verification_reviewed_at"] is not None

    events = verification_events(buyer_id)
    assert len(events) == 1, events
    assert events[0]["actor_id"] == admin_id
    assert events[0]["action"] == "approved"
    assert events[0]["from_status"] == "pending"
    assert events[0]["to_status"] == "verified"


def test_v5_admin_reject_moves_pending_to_rejected_stores_the_reason_and_records_the_event(
    client, auth_headers, admin_headers, pending_verification, verification_events, user_id
):
    """V5 — reject-from-pending (the "deny" reading of D1): status -> `rejected`,
    the reason is stored and readable back via `GET /verification`, and an event
    row is written — the reason is what `verification_reason` alone would lose
    the moment a later decision overwrites it (D6)."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id, _ = pending_verification(buyer)
    admin = admin_headers()
    admin_id = user_id(admin)

    res = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "Statement is illegible"},
        headers=admin,
    )

    assert res.status_code == 200, res.text
    status = client.get("/api/verification", headers=buyer).json()
    assert status["verification_status"] == "rejected"
    assert status["verification_reason"] == "Statement is illegible"

    events = verification_events(buyer_id)
    assert len(events) == 1, events
    assert events[0]["actor_id"] == admin_id
    assert events[0]["action"] == "rejected"
    assert events[0]["from_status"] == "pending"
    assert events[0]["to_status"] == "rejected"
    assert events[0]["reason"] == "Statement is illegible"


def test_v6_resubmission_after_rejection_returns_to_pending(
    client, auth_headers, admin_headers, pending_verification, submit_verification
):
    """V6 — D1's resubmission edge: a `rejected` buyer's fresh upload is 201 and
    status moves back to `pending` (story 2 — a fixable mistake isn't final)."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id, _ = pending_verification(buyer)
    rejected = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "Blurry scan"},
        headers=admin_headers(),
    )
    assert rejected.status_code == 200, rejected.text

    res = submit_verification(buyer, filename="resubmission.pdf")

    assert res.status_code == 201, res.text
    status = client.get("/api/verification", headers=buyer).json()
    assert status["verification_status"] == "pending"


def test_v7_uploading_while_already_verified_is_409(
    client, auth_headers, verified_buyer, submit_verification
):
    """V7 — D3: a `verified` buyer cannot re-trigger review by uploading again."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    verified_buyer(buyer)

    res = submit_verification(buyer, filename="another.pdf")

    assert res.status_code == 409, res.text
    assert res.json().get("code") == "already_verified"


def test_v8_a_sellers_access_request_queue_shows_the_buyers_verified_badge(
    client, auth_headers, live_listing, request_access, verified_buyer
):
    """V8 — FR-14 completed: the seller's access-request list (`AccessRequestWithBuyer`
    -> nested `BuyerProfile`) carries the buyer's verification status and the
    computed `verified` boolean (D7)."""
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    verified_buyer(buyer)
    request_access(listing_id, buyer)

    res = client.get(f"/api/my/listings/{listing_id}/access-requests", headers=seller)

    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) == 1, rows
    assert rows[0]["buyer"]["verification_status"] == "verified"
    assert rows[0]["buyer"]["verified"] is True


def test_v9_the_callers_own_profile_shows_their_pending_verification_status(
    client, auth_headers, pending_verification
):
    """V9 — D7's other surface: `GET /auth/me` carries the caller's own
    `verification_status` + computed `verified`, mirroring `email_verified`."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    pending_verification(buyer)

    res = client.get("/api/auth/me", headers=buyer)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verification_status"] == "pending"
    assert body["verified"] is False


def test_v10_a_disallowed_file_type_is_415(client, auth_headers, submit_verification):
    """V10 — the M2 whitelist reused verbatim (D5): a non-PDF/PNG/JPEG type is 415."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    res = submit_verification(
        buyer,
        filename="malware.exe",
        content=b"MZ\x90\x00\x03\x00\x00\x00",
        content_type="application/x-msdownload",
    )

    assert res.status_code == 415, res.text
    assert res.json().get("code") == "unsupported_media_type"


def test_v11_an_oversized_upload_is_413(client, auth_headers, submit_verification):
    """V11 — the M2 streamed-size-cap reused verbatim (D5): over `max_upload_bytes`
    is 413 `file_too_large` — distinct from V12/V13's `upload_quota_exceeded`."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    big = b"%PDF-1.4\n" + b"A" * (11 * 1024 * 1024)  # > the 10 MB default cap

    res = submit_verification(buyer, content=big)

    assert res.status_code == 413, res.text
    assert res.json().get("code") == "file_too_large"


@pytest.mark.parametrize("surface", ["verification_documents", "listing_documents"])
def test_v12_uploading_past_the_document_count_cap_is_413(
    client, auth_headers, make_listing, submit_verification, monkeypatch, surface
):
    """V12 — D8: the shared per-owner document-count quota, checked on both
    surfaces it applies to — a buyer's own verification documents, and a
    seller's own listing documents (the M2 retrofit)."""
    from app.config import settings

    monkeypatch.setattr(settings, "max_documents_per_owner", 1)
    headers = auth_headers(email="owner@example.com", role="buyer")

    if surface == "verification_documents":
        first = submit_verification(headers)
        assert first.status_code == 201, first.text
        second = submit_verification(headers, filename="second.pdf")
    else:
        listing_id = make_listing(headers).json()["id"]
        first = _listing_doc(client, listing_id, headers)
        assert first.status_code == 201, first.text
        second = _listing_doc(client, listing_id, headers, filename="second.pdf")

    assert second.status_code == 413, second.text
    assert second.json().get("code") == "upload_quota_exceeded"


@pytest.mark.parametrize("surface", ["verification_documents", "listing_documents"])
def test_v13_uploading_past_the_total_size_cap_is_413(
    client, auth_headers, make_listing, submit_verification, monkeypatch, surface
):
    """V13 — D8: the shared per-owner total-upload-size quota. The second file is
    individually within `max_upload_bytes` (it's the same small PDF as the
    first) — only the *cumulative* total, capped at exactly the first upload's
    size, is what pushes the second one over."""
    from app.config import settings

    monkeypatch.setattr(settings, "max_documents_per_owner", 1000)   # isolate from V12's cap
    monkeypatch.setattr(settings, "max_total_upload_bytes_per_owner", len(_PDF))
    headers = auth_headers(email="owner@example.com", role="buyer")

    if surface == "verification_documents":
        first = submit_verification(headers)
        assert first.status_code == 201, first.text
        second = submit_verification(headers, filename="second.pdf")
    else:
        listing_id = make_listing(headers).json()["id"]
        first = _listing_doc(client, listing_id, headers)
        assert first.status_code == 201, first.text
        second = _listing_doc(client, listing_id, headers, filename="second.pdf")

    assert second.status_code == 413, second.text
    assert second.json().get("code") == "upload_quota_exceeded"


def test_v14_admin_reject_can_revoke_an_already_verified_buyer(
    client, auth_headers, admin_headers, verified_buyer, verification_events, user_id
):
    """V14 — D1's revoke path (story 4): `reject` also moves `verified -> rejected`,
    and the new event row's `from_status` is `"verified"` — the detail that
    distinguishes a revoke from a deny, and that only the audit row preserves
    once `User.verification_reason` is overwritten again."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    admin = admin_headers()
    admin_id = user_id(admin)
    buyer_id, _ = verified_buyer(buyer, admin=admin)

    res = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "Fraud reported after approval"},
        headers=admin,
    )

    assert res.status_code == 200, res.text
    status = client.get("/api/verification", headers=buyer).json()
    assert status["verification_status"] == "rejected"

    events = verification_events(buyer_id)
    assert len(events) == 2, events   # approve, then the revoke
    revoke_event = events[-1]
    assert revoke_event["actor_id"] == admin_id
    assert revoke_event["action"] == "rejected"
    assert revoke_event["from_status"] == "verified"
    assert revoke_event["to_status"] == "rejected"
    assert revoke_event["reason"] == "Fraud reported after approval"


def test_v15_the_queue_filter_reaches_verified_buyers_for_the_revoke_path(
    client, auth_headers, admin_headers, pending_verification, verified_buyer
):
    """V15 — D13: `?status=verified` is how story 4 finds its subject.

    D1 makes `reject` do double duty as revoke, acting on an already-`verified`
    buyer. Without this filter that endpoint is reachable only by an admin who
    already knows the user id — a route with no discovery path, which is a
    feature that exists in the API and not in the product.

    Asserts the filter *discriminates* rather than merely returning something: a
    `pending` buyer exists at the same time and must be absent, so an
    implementation that ignores the parameter and returns everything fails here.
    """
    admin = admin_headers()
    pending_buyer = auth_headers(email="pending@example.com", role="buyer")
    approved_buyer = auth_headers(email="approved@example.com", role="buyer")
    pending_id, _ = pending_verification(pending_buyer)
    verified_id, _ = verified_buyer(approved_buyer, admin=admin)

    res = client.get("/api/admin/verifications?status=verified", headers=admin)

    assert res.status_code == 200, res.text
    returned = {row["user_id"] for row in res.json()}
    assert verified_id in returned, res.text
    assert pending_id not in returned, res.text


# ── X — errors & failure modes ───────────────────────────────────────────────


def test_x1_a_missing_file_part_is_422(client, auth_headers):
    """X1 — no `file` part in the multipart body: a shape error, not a business one."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    res = client.post("/api/verification/documents", headers=buyer)

    assert res.status_code == 422, res.text


def test_x2_rejecting_without_a_reason_is_422(
    client, auth_headers, admin_headers, pending_verification
):
    """X2 — mirrors M3's "reject reason stored" requirement: no `reason` field
    at all is refused at the boundary, before any transition is attempted."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id, _ = pending_verification(buyer)

    res = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={},
        headers=admin_headers(),
    )

    assert res.status_code == 422, res.text


def test_x3_approving_a_buyer_with_nothing_pending_is_409(
    client, auth_headers, admin_headers, user_id
):
    """X3 — `unverified` has no `from_status` legal for approve: 409 `invalid_transition`."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id = user_id(buyer)

    res = client.post(f"/api/admin/verifications/{buyer_id}/approve", headers=admin_headers())

    assert res.status_code == 409, res.text
    assert res.json().get("code") == "invalid_transition"


def test_x4_rejecting_an_already_rejected_buyer_is_409(
    client, auth_headers, admin_headers, pending_verification
):
    """X4 — `rejected` is not a legal `from_status` for reject (only `pending`
    and `verified` are, per D1): a second reject is 409 `invalid_transition`."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id, _ = pending_verification(buyer)
    admin = admin_headers()
    first = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "Blurry scan"},
        headers=admin,
    )
    assert first.status_code == 200, first.text

    res = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "still not readable"},
        headers=admin,
    )

    assert res.status_code == 409, res.text
    assert res.json().get("code") == "invalid_transition"


def test_x5_an_internal_error_on_a_verification_route_returns_the_generic_contract(
    client, auth_headers, session
):
    """X5 — the M1 catch-all handler, reused verbatim: a forced failure at the
    session boundary (mirrors `test_watchlist_security.py::test_x2`) turns into
    a generic 500 with a `request_id` — never a stack trace, SQL, or a table name.
    """
    from app.db import get_session
    from app.main import app

    buyer = auth_headers(email="buyer@example.com", role="buyer")

    class BrokenSession:
        def __getattr__(self, name):
            if name in ("exec", "get"):
                raise RuntimeError("injected failure")
            return getattr(session, name)

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    try:
        res = client.get("/api/verification", headers=buyer)
    finally:
        app.dependency_overrides[get_session] = lambda: session

    assert res.status_code == 500, res.text
    body = res.json()
    assert "request_id" in body
    assert "Traceback" not in str(body)
    assert "SELECT" not in str(body).upper()
    assert "buyerverificationdocument" not in str(body).lower()


def test_x6_an_over_long_rejection_reason_is_422(
    client, auth_headers, admin_headers, pending_verification
):
    """X6 — the rejection reason is capped at the boundary.

    `reason` is the milestone's only free-text field, and it is not merely stored:
    `GET /api/verification` hands it back to the buyer (V5). `security.md` §1.1
    wants every string bounded, and `config.py` already carries the precedent
    (`offer_structure_max_chars`, `offer_contingencies_max_chars`) — without a cap
    an admin (or anything holding an admin token) can write an unbounded blob into
    the `user` row on every rejection.

    The cap is read from settings with a fallback rather than hardcoded, so this
    test tracks the configured value instead of pinning plan.md's default: before
    slice 2 the attribute does not exist yet, and `getattr`'s default keeps the
    failure on the 422 assertion (where the criterion lives) rather than on an
    `AttributeError` in the arrangement.
    """
    from app.config import settings

    cap = getattr(settings, "verification_reason_max_chars", 1000)
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    buyer_id, _ = pending_verification(buyer)

    res = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "x" * (cap + 1)},
        headers=admin_headers(),
    )

    assert res.status_code == 422, res.text
