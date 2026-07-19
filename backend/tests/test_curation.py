"""M3 — admin curation (spec 003).

Approve/reject is the only path to `live`. The forbidden paths in group E are
the point of the milestone: if a seller can publish themselves, the product's
quality promise is void.

Written failing first, forbidden paths before happy paths.
"""

from sqlalchemy import text


def _seller_with_pending_listing(auth_headers, make_listing, client, email="seller@example.com"):
    """A seller whose listing is submitted and awaiting review."""
    headers = auth_headers(email=email, role="seller")
    listing_id = make_listing(headers).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=headers)
    return headers, listing_id


# ── A — the curation queue ───────────────────────────────────────────────────

def test_a4_queue_without_credentials_is_401(client):
    assert client.get("/api/admin/listings").status_code == 401


def test_a3_queue_as_non_admin_is_403(client, auth_headers, admin_headers):
    admin_headers()                                    # an admin exists, but not this caller
    plain = auth_headers(email="bob@example.com", role="buyer")
    assert client.get("/api/admin/listings", headers=plain).status_code == 403


def test_a1_queue_filters_to_pending_review(client, auth_headers, admin_headers, make_listing, force_status):
    seller = auth_headers(email="seller@example.com", role="seller")
    pending = make_listing(seller).json()["id"]
    client.post(f"/api/listings/{pending}/submit", headers=seller)
    draft = make_listing(seller, headline="Still a draft").json()["id"]

    res = client.get("/api/admin/listings?status=pending_review", headers=admin_headers())
    assert res.status_code == 200
    ids = [row["id"] for row in res.json()]
    assert pending in ids
    assert draft not in ids


def test_a2_queue_without_filter_returns_every_status(client, auth_headers, admin_headers, make_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    pending = make_listing(seller).json()["id"]
    client.post(f"/api/listings/{pending}/submit", headers=seller)
    draft = make_listing(seller, headline="Still a draft").json()["id"]

    res = client.get("/api/admin/listings", headers=admin_headers())
    assert res.status_code == 200
    ids = [row["id"] for row in res.json()]
    assert {pending, draft} <= set(ids)


def test_a5_queue_carries_the_detail_an_admin_needs_to_judge(client, auth_headers, admin_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)

    res = client.get("/api/admin/listings?status=pending_review", headers=admin_headers())
    row = next(r for r in res.json() if r["id"] == listing_id)
    # Public judging fields...
    for field in ("headline", "type", "asking_price", "status", "created_at"):
        assert field in row, f"queue row is missing {field}"
    # ...and the private detail: an admin is authorised to see it and cannot
    # curate blind (spec A5). This is the one place private data is exposed
    # outside the owner before M5's NDA gate.
    assert row["company_name"] == "Acme Internal Tools LLC"
    assert row["website_url"] == "https://acme.example.com"


# ── B — approve ──────────────────────────────────────────────────────────────

def test_b5_approve_as_non_admin_is_403(client, auth_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    # The listing's own seller is still not an admin.
    res = client.post(f"/api/listings/{listing_id}/approve", headers=seller)
    assert res.status_code == 403
    assert client.get("/api/my/listings", headers=seller).json()[0]["status"] == "pending_review"


def test_b1_approve_moves_pending_review_to_live(client, auth_headers, admin_headers, make_listing):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    res = client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())
    assert res.status_code == 200
    assert res.json()["status"] == "live"


def test_b2_approve_stamps_published_at(client, auth_headers, admin_headers, make_listing, session):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())
    published_at = session.execute(
        text("SELECT published_at FROM listing WHERE id = :i"), {"i": listing_id}
    ).scalar()
    assert published_at is not None


def test_b3_approving_an_already_live_listing_is_409(client, auth_headers, admin_headers, make_listing):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    admin = admin_headers()
    client.post(f"/api/listings/{listing_id}/approve", headers=admin)
    res = client.post(f"/api/listings/{listing_id}/approve", headers=admin)
    assert res.status_code == 409


def test_b4_approving_a_draft_is_409(client, auth_headers, admin_headers, make_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]        # never submitted
    res = client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())
    assert res.status_code == 409


# ── C — reject ───────────────────────────────────────────────────────────────

def test_c5_reject_as_non_admin_is_403(client, auth_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    res = client.post(
        f"/api/listings/{listing_id}/reject", json={"reason": "nope"}, headers=seller
    )
    assert res.status_code == 403


def test_c3_reject_without_a_reason_is_422(client, auth_headers, admin_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    admin = admin_headers()
    assert client.post(f"/api/listings/{listing_id}/reject", json={}, headers=admin).status_code == 422
    assert (
        client.post(
            f"/api/listings/{listing_id}/reject", json={"reason": "   "}, headers=admin
        ).status_code
        == 422
    )
    # Status untouched by a rejected rejection.
    assert client.get("/api/my/listings", headers=seller).json()[0]["status"] == "pending_review"


def test_c1_reject_moves_pending_review_to_rejected(client, auth_headers, admin_headers, make_listing):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    res = client.post(
        f"/api/listings/{listing_id}/reject",
        json={"reason": "Financials do not reconcile with the stated MRR."},
        headers=admin_headers(),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"


def test_c2_reject_stores_the_reason_verbatim(
    client, auth_headers, admin_headers, make_listing, listing_events
):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    reason = "Financials do not reconcile with the stated MRR."
    client.post(f"/api/listings/{listing_id}/reject", json={"reason": reason}, headers=admin_headers())
    assert listing_events(listing_id)[-1]["reason"] == reason


def test_c4_rejecting_a_live_listing_is_409(client, auth_headers, admin_headers, make_listing):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    admin = admin_headers()
    client.post(f"/api/listings/{listing_id}/approve", headers=admin)
    res = client.post(f"/api/listings/{listing_id}/reject", json={"reason": "too late"}, headers=admin)
    assert res.status_code == 409


def test_c6_owner_sees_the_rejection_reason(client, auth_headers, admin_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    reason = "Screenshots are inconsistent with the described traffic."
    client.post(f"/api/listings/{listing_id}/reject", json={"reason": reason}, headers=admin_headers())

    row = next(r for r in client.get("/api/my/listings", headers=seller).json() if r["id"] == listing_id)
    assert row["rejection_reason"] == reason


# ── D — the audit trail ──────────────────────────────────────────────────────

def test_d1_approval_writes_one_audit_row(
    client, auth_headers, admin_headers, make_listing, listing_events, session
):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())

    events = listing_events(listing_id)
    assert len(events) == 1
    event = events[0]
    assert event["action"] == "approved"
    assert event["from_status"] == "pending_review"
    assert event["to_status"] == "live"
    assert event["created_at"] is not None
    admin_id = session.execute(
        text('SELECT id FROM "user" WHERE email = :e'), {"e": "admin@example.com"}
    ).scalar()
    assert event["actor_id"] == admin_id, "actor must be the admin from the JWT, not the seller"


def test_d2_rejection_row_carries_the_reason(
    client, auth_headers, admin_headers, make_listing, listing_events
):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    client.post(f"/api/listings/{listing_id}/reject", json={"reason": "Not enough detail."}, headers=admin_headers())

    event = listing_events(listing_id)[-1]
    assert event["action"] == "rejected"
    assert event["to_status"] == "rejected"
    assert event["reason"] == "Not enough detail."


def test_d3_a_failed_transition_writes_no_audit_row(
    client, auth_headers, admin_headers, make_listing, listing_events
):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]          # draft — approve must 409
    assert client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers()).status_code == 409
    # The audit records what happened, not what was attempted.
    assert listing_events(listing_id) == []


def test_d4_events_are_append_only_across_two_decisions(
    client, auth_headers, admin_headers, make_listing, listing_events, force_status
):
    _, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    admin = admin_headers()
    client.post(f"/api/listings/{listing_id}/reject", json={"reason": "First pass: too thin."}, headers=admin)
    # Seller revises and resubmits (forced: the resubmit flow is out of scope).
    force_status(listing_id, "pending_review")
    client.post(f"/api/listings/{listing_id}/approve", headers=admin)

    events = listing_events(listing_id)
    assert [e["action"] for e in events] == ["rejected", "approved"]
    assert events[0]["reason"] == "First pass: too thin."


# ── E — no seller path to `live` (the crown jewels) ──────────────────────────

def test_e1_seller_cannot_set_status_live_by_mass_assignment(client, auth_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    client.put(
        f"/api/listings/{listing_id}",
        json={"headline": "Edited", "status": "live", "published_at": "2020-01-01T00:00:00"},
        headers=seller,
    )
    status = client.get("/api/my/listings", headers=seller).json()[0]["status"]
    assert status != "live", "client-supplied status must be ignored"


def test_e2_submitting_twice_is_409(client, auth_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    res = client.post(f"/api/listings/{listing_id}/submit", headers=seller)
    assert res.status_code == 409, "submit must not become a publish loop"


def test_e3_owner_approving_their_own_listing_is_403(client, auth_headers, make_listing):
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    assert client.post(f"/api/listings/{listing_id}/approve", headers=seller).status_code == 403


def test_e4_an_admin_may_approve_a_listing_they_own(client, admin_headers, make_listing):
    """Admin authority is by role, not ownership (spec E4 — a recorded policy
    decision, not an oversight). Forbidding self-approval is a separate call."""
    admin = admin_headers()
    listing_id = make_listing(admin).json()["id"]
    client.post(f"/api/listings/{listing_id}/submit", headers=admin)
    res = client.post(f"/api/listings/{listing_id}/approve", headers=admin)
    assert res.status_code == 200
    assert res.json()["status"] == "live"


def test_e5_pause_edit_resume_cannot_republish_unreviewed_content(
    client, auth_headers, admin_headers, make_listing
):
    """The curation bypass found by the independent security review.

    Every step is individually legal — pause, edit, resume are all the seller's
    own routes — but composed they put unreviewed content in front of buyers
    without a second admin decision. E1-E4 all checked paths that set `status`
    directly, which is why none of them caught it.
    """
    seller, listing_id = _seller_with_pending_listing(auth_headers, make_listing, client)
    client.post(f"/api/listings/{listing_id}/approve", headers=admin_headers())

    client.post(f"/api/listings/{listing_id}/pause", headers=seller)
    swapped = "TOTALLY DIFFERENT — never reviewed"
    client.put(
        f"/api/listings/{listing_id}",
        json={"headline": swapped, "asking_price": "999999.00"},
        headers=seller,
    )
    res = client.post(f"/api/listings/{listing_id}/resume", headers=seller)

    row = next(r for r in client.get("/api/my/listings", headers=seller).json() if r["id"] == listing_id)
    assert row["status"] != "live", (
        "a seller republished edited content without a second admin decision — "
        "approval must be the only path to live"
    )
    # Editing while paused returns it to the queue, so resume has nothing to resume.
    assert row["status"] == "pending_review"
    assert res.status_code == 409
