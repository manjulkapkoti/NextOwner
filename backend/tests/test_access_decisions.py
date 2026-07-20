"""M5 — the seller's access-request decision (spec 005): C1-C11, S1, S5, X1, X2.

`approve`/`deny`/`revoke` is the state machine `require_request_decider`
guards, and it is the *only* door to `ListingPrivate` besides ownership
(`test_nda_gate.py`'s `require_private_access` reads what this file writes).
C10 is the reason `accessrequestevent` exists at all: revocation must not
erase *when* access was granted — a single `decided_at`/`decided_by_id` pair
on the row can only ever hold the last decision, so it fails exactly the
scenario C10 sets up (spec 005 D6).

Written failing first: `AccessRequest`, `AccessRequestEvent`, and the three
decision routes do not exist yet, so most of these either 404 outright or
error inside a fixture that calls a 404ing route — both are runtime
failures, which is intended.

Scope: **D** (the gate on private data), **E** (the same gate on downloads),
and the S/X criteria that probe the gate itself (S2, S6, S7, S8) live in
`test_nda_gate.py`. **A** (NDA signing) and **B** (requesting access) are
covered elsewhere — this file only drives them through fixtures to reach a
`requested`/`approved` row.
"""


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


# ── C — the seller's decision ────────────────────────────────────────────────

def test_c1_seller_approves_a_requested_row(client, auth_headers, live_listing, request_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/approve", headers=seller)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved"
    assert body["decided_at"] is not None


def test_c2_seller_denies_a_requested_row(client, auth_headers, live_listing, request_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/deny", headers=seller)
    assert res.status_code == 200
    assert res.json()["status"] == "denied"


def test_c3_seller_revokes_an_approved_row(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = granted_access(listing_id, buyer, seller)

    res = client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    assert res.status_code == 200
    assert res.json()["status"] == "revoked"


def test_c4_a_third_party_cannot_decide_the_request(client, auth_headers, live_listing, request_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/approve", headers=stranger)
    assert res.status_code == 403


def test_c5_the_buyer_cannot_approve_their_own_request(client, auth_headers, live_listing, request_access):
    """Self-dealing — the decisive forbidden path of this milestone. Without
    this check a buyer grants themselves access to any listing's financials
    with no seller ever deciding anything."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/approve", headers=buyer)
    assert res.status_code == 403


def test_c6_approving_an_already_approved_request_is_409(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = granted_access(listing_id, buyer, seller)

    res = client.post(f"/api/access-requests/{req_id}/approve", headers=seller)
    assert res.status_code == 409


def test_c7_revoking_a_still_requested_row_is_409(client, auth_headers, live_listing, request_access):
    """`revoke` is legal only from `approved` (spec 005 D3 in § Decisions) — a
    request that was never granted has nothing to take back."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    assert res.status_code == 409


def test_c8_an_admin_who_does_not_own_the_listing_cannot_approve(
    client, auth_headers, admin_headers, live_listing, request_access
):
    """Admin is not special-cased on this boundary — curation authority does
    not extend to NDA access; the seller alone decides who sees their data."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/approve", headers=admin_headers(email="admin2@example.com"))
    assert res.status_code == 403


def test_c9_approval_writes_one_audit_row_with_the_deciding_seller_as_actor(
    client, auth_headers, live_listing, request_access, access_events
):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]
    client.post(f"/api/access-requests/{req_id}/approve", headers=seller)

    events = access_events(req_id)
    assert len(events) == 1
    event = events[0]
    assert event["action"] == "approved"
    assert event["from_status"] == "requested"
    assert event["to_status"] == "approved"
    assert event["created_at"] is not None

    seller_id = client.get("/api/auth/me", headers=seller).json()["id"]
    assert event["actor_id"] == seller_id, "actor must be the deciding seller from the JWT, never the body"


def test_c10_revocation_does_not_erase_when_access_was_granted(
    client, auth_headers, live_listing, granted_access, access_events
):
    """D6's whole reason to exist. A design that stores only the *last*
    decision (`decided_at`/`decided_by_id` on the `AccessRequest` row itself)
    would answer "when was this granted" with the **revocation** time — this
    test fails against that design and passes only once approval and
    revocation are separate, immutable rows in `accessrequestevent`."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = granted_access(listing_id, buyer, seller)
    approved_at = access_events(req_id)[0]["created_at"]

    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    events = access_events(req_id)
    assert len(events) == 2
    assert [e["action"] for e in events] == ["approved", "revoked"]
    assert events[0]["created_at"] == approved_at, "revocation overwrote the approval's own timestamp"


def test_c11_previously_written_rows_are_never_mutated_by_a_later_decision(
    client, auth_headers, live_listing, granted_access, access_events
):
    """Append-only by discipline, mirroring M3's `listingevent` (spec 003 D4,
    itself the audit table this milestone is told to mirror — plan.md
    § Schema deltas)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = granted_access(listing_id, buyer, seller)
    before_revoke = access_events(req_id)

    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    after_revoke = access_events(req_id)

    assert after_revoke[0] == before_revoke[0], "the approval row must not be rewritten by a later transition"
    assert len(after_revoke) == len(before_revoke) + 1


# ── Security & abuse (this file's slice: S1, S5) ─────────────────────────────

def test_s1_idor_guessing_another_sellers_request_id_is_403(client, auth_headers, live_listing, request_access):
    """The row must be authorized through *its own* listing's ownership, not
    merely fetched by id and trusted — probed here by a seller who owns
    listings of their own, guessing at an id that belongs to someone else's."""
    seller_a, buyer = _seller_and_buyer(auth_headers, seller_email="seller_a@example.com")
    seller_b = auth_headers(email="seller_b@example.com", role="seller")
    listing_id = live_listing(seller_a)
    req_id = request_access(listing_id, buyer).json()["id"]

    res = client.post(f"/api/access-requests/{req_id}/approve", headers=seller_b)
    assert res.status_code == 403


def test_s5_mass_assignment_on_approve_is_ignored(client, auth_headers, live_listing, request_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]
    forged_time = "2000-01-01T00:00:00"

    res = client.post(
        f"/api/access-requests/{req_id}/approve",
        json={"status": "revoked", "decided_at": forged_time, "decided_by_id": 999999},
        headers=seller,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved", "the client-sent status must be ignored"
    assert body["decided_at"] != forged_time, "decided_at is server-derived, never client-supplied"


# ── Errors & failure modes (this file's slice: X1, X2) ───────────────────────

def test_x1_a_non_integer_access_request_id_is_422(client, auth_headers):
    """`{id}` is typed as an int at the route; a non-numeric id fails Pydantic's
    path validation before any permission check runs."""
    seller = auth_headers(email="seller@example.com", role="seller")
    res = client.post("/api/access-requests/not-a-number/approve", headers=seller)
    assert res.status_code == 422


def test_x2_an_illegal_transition_409_carries_a_machine_code(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = granted_access(listing_id, buyer, seller)          # already approved
    res = client.post(f"/api/access-requests/{req_id}/approve", headers=seller)   # approve again
    assert res.status_code == 409
    assert res.json()["code"] == "invalid_access_transition"
