"""M5 — the NDA + access gate (spec 005): D1-D10, E1-E5, S2, S6, S7, S8.

`require_private_access` is the function this whole architecture exists to
make possible (`design_implementation.md` §3.6) — this file is **the most
important test file in the project** (`CLAUDE.md` § Non-negotiable
architecture rules #5). Written failing first: `AccessRequest`,
`require_private_access`, `POST /api/auth/nda`, `POST /api/listings/{id}
/access-request`, and `GET /api/listings/{id}/private` do not exist yet, so
every test here either asserts a status code the app cannot yet produce, or
errors inside a fixture that calls a route that 404s. Both are runtime
failures, not collection failures — the red set is the work queue.

Scope: this file owns **D** (the gate itself) + **E** (the same gate on
document downloads) + the **S** criteria that probe the gate from the
outside (cross-listing IDOR, token attacks, enumeration, no-leak-on-denial).
**A** (NDA signing), **B** (requesting access), **F/G** (the list endpoints)
and **C** (the seller's decision + its own audit/forbidden paths, S1, S5,
X1, X2) live elsewhere — see `test_access_decisions.py` for C/S1/S5/X1/X2.
"""

import datetime
import itertools

import jwt

from tests.conftest import TEST_JWT_ALG, TEST_JWT_SECRET

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


def _upload(client, listing_id, headers):
    return client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": ("pnl.pdf", _PDF, "application/pdf")},
        headers=headers,
    )


# ── D — the gate: require_private_access ⭐ ──────────────────────────────────

def test_d1_owner_reads_private_data_is_200(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    res = client.get(f"/api/listings/{listing_id}/private", headers=seller)
    assert res.status_code == 200


def test_d2_approved_buyer_sees_the_private_payload(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)

    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 200
    body = res.json()
    for field in ("company_name", "website_url", "detailed_financials"):
        assert field in body, f"private payload is missing {field!r}"


def test_d3_requested_but_unapproved_is_403(client, auth_headers, live_listing, request_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    request_access(listing_id, buyer)

    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 403
    assert res.json()["code"] == "nda_access_required"


def test_d4_denied_buyer_is_403(client, auth_headers, live_listing, request_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = request_access(listing_id, buyer).json()["id"]
    client.post(f"/api/access-requests/{req_id}/deny", headers=seller)

    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 403


def test_d5_revoked_access_is_immediately_re_denied(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    req_id = granted_access(listing_id, buyer, seller)
    # Prove access was real before proving revoke takes it away — an absence
    # assertion after a call that never worked would pass vacuously.
    assert client.get(f"/api/listings/{listing_id}/private", headers=buyer).status_code == 200

    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)
    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 403, "revocation must re-deny immediately, not eventually"


def test_d6_authenticated_with_no_request_at_all_is_403(client, auth_headers, live_listing, sign_nda):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    sign_nda(buyer)          # signed the platform NDA, but never requested THIS listing
    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 403


def test_d7_no_credentials_is_401(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    res = client.get(f"/api/listings/{listing_id}/private")
    assert res.status_code == 401


def test_d8_never_published_listing_is_404_to_a_non_owner(client, auth_headers, make_listing):
    """A draft's existence is still a secret (spec 005 D1 in § Decisions) — 404,
    not 403, so a non-owner cannot even confirm the listing exists.

    Asserts the machine `code` too, not just the status — a bare 404 also
    comes back from a route that simply isn't mounted yet (Starlette's own
    default `{"detail": "Not Found"}`, with no `code`/`request_id`), which
    would let this test pass vacuously for the wrong reason before the gate
    exists (the same trap `test_browse.py::test_a4`'s comment names)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = make_listing(seller).json()["id"]     # never submitted, never approved
    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 404
    assert res.json()["code"] == "not_found"


def test_d9_approved_access_survives_the_listing_leaving_live(client, auth_headers, live_listing, granted_access):
    """The gate is the access request, not the listing's status (spec 005 D2 in
    § Decisions) — pausing or closing a listing is not the tool for taking
    access back; `revoke` is, and it's the only one (tested separately)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    granted_access(listing_id, buyer, seller)

    client.post(f"/api/listings/{listing_id}/pause", headers=seller)
    assert client.get(f"/api/listings/{listing_id}/private", headers=buyer).status_code == 200

    client.post(f"/api/listings/{listing_id}/close", headers=seller)
    assert client.get(f"/api/listings/{listing_id}/private", headers=buyer).status_code == 200


# ── D10 — reachability: the corridor, not the door ───────────────────────────

# Every action that can move either the access request or the listing status,
# from the two identities that can ever reach the gate for real (the buyer
# signs/requests, the seller decides/moves the listing). MAINTENANCE: this
# list is hand-written, like `SELLER_ACTIONS` in test_curation.py — a new
# route that affects the gate is not covered until it is added here.
D10_ACTIONS = ("sign", "request", "approve", "deny", "revoke", "pause", "resume", "close")


def _apply_d10_action(client, listing_id, buyer_headers, seller_headers, action, model):
    """Perform one action through the real HTTP API and advance `model` — the
    test's own belief about the request's status — **only from what the
    server actually confirmed** (a success status code), never from an
    assumption about which transitions ought to be legal right now. That is
    what makes an illegal action (409/403/404) a harmless no-op instead of
    something the test has to predict: the model simply doesn't move unless
    the server says it moved.
    """
    if action == "sign":
        client.post("/api/auth/nda", headers=buyer_headers)
    elif action == "request":
        res = client.post(f"/api/listings/{listing_id}/access-request", headers=buyer_headers)
        if res.status_code == 201:
            model["req_id"] = res.json()["id"]
            model["status"] = "requested"
    elif action in ("approve", "deny", "revoke"):
        req_id = model["req_id"] if model["req_id"] is not None else 999_999_999
        res = client.post(f"/api/access-requests/{req_id}/{action}", headers=seller_headers)
        if res.status_code == 200:
            model["status"] = {"approve": "approved", "deny": "denied", "revoke": "revoked"}[action]
    elif action in ("pause", "resume", "close"):
        client.post(f"/api/listings/{listing_id}/{action}", headers=seller_headers)
    else:  # pragma: no cover - guards a typo in D10_ACTIONS
        raise ValueError(action)


def test_d10_private_data_is_reachable_only_via_ownership_or_approval(
    client, auth_headers, admin_headers, make_listing
):
    """Exhaustive: every sequence of up to three actions drawn from
    {sign, request, approve, deny, revoke, pause, resume, close}, checked
    **after every step**, must never let a non-owner without approved access
    through, and must never lock the real owner out.

    Why this test exists, and why it is strong: M3's forbidden-path tests
    each named one door (approve-as-non-admin, reject-as-non-admin, ...) and
    missed the corridor — `pause -> edit -> resume` republished unreviewed
    content because no test asked "does the invariant hold after *every*
    step of *every* sequence," only "does this one named action behave."
    M4's first attempt at the equivalent fix could not even reach the
    corridor it claimed to test (constitution amendment 2026-07-19;
    `progress.md` § M4 carryover). This test is M5's answer to the same bug
    class: it does not ask "is `approve` safe" or "is `revoke` safe" in
    isolation — it asks whether "200 only for the owner or an approved
    holder" survives *every* reachable path through the state space, not
    just the paths a human thought to name.

    Verify its strength by reverting `require_private_access` — e.g. make it
    consult `listing.status` instead of the access request's own status, or
    drop the revoke check — this test must fail.

    Ground truth for "does the buyer currently hold approved access" is the
    test's own `model` (see `_apply_d10_action`), advanced only by the
    server's own success responses — never by the test assuming a transition
    is legal. So a false pass here would mean the *gate* is wrong, not that
    the test mis-modeled the state machine.
    """
    admin = admin_headers()
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    failures: list[str] = []
    for sequence in itertools.product(D10_ACTIONS, repeat=3):
        listing_id = make_listing(seller).json()["id"]
        client.post(f"/api/listings/{listing_id}/submit", headers=seller)
        client.post(f"/api/listings/{listing_id}/approve", headers=admin)   # genuinely published

        model = {"status": None, "req_id": None}
        for step, action in enumerate(sequence, start=1):
            _apply_d10_action(client, listing_id, buyer, seller, action, model)
            prefix = sequence[:step]

            owner_res = client.get(f"/api/listings/{listing_id}/private", headers=seller)
            if owner_res.status_code != 200:
                failures.append(f"{prefix}: owner locked out of their own listing ({owner_res.status_code})")

            buyer_res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
            should_be_ok = model["status"] == "approved"
            if should_be_ok and buyer_res.status_code != 200:
                failures.append(f"{prefix}: approved buyer denied private data ({buyer_res.status_code})")
            elif not should_be_ok and buyer_res.status_code == 200:
                failures.append(f"{prefix}: buyer without approval (status={model['status']!r}) read private data")

    assert not failures, (
        f"{len(failures)} reachable-path violation(s) of the NDA gate invariant "
        "(showing first 20):\n" + "\n".join(failures[:20])
    )


# ── E — the same gate on document downloads ──────────────────────────────────

def test_e1_approved_buyer_downloads_the_document(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    doc_id = _upload(client, listing_id, seller).json()["id"]
    granted_access(listing_id, buyer, seller)

    res = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=buyer)
    assert res.status_code == 200
    assert "attachment" in res.headers.get("content-disposition", "").lower()


def test_e2_requested_but_unapproved_cannot_download(client, auth_headers, live_listing, request_access):
    """The download path enforces the **same** gate, not a second copy of it."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    doc_id = _upload(client, listing_id, seller).json()["id"]
    request_access(listing_id, buyer)

    res = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=buyer)
    assert res.status_code == 403


def test_e3_revoked_access_cannot_download(client, auth_headers, live_listing, granted_access):
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    doc_id = _upload(client, listing_id, seller).json()["id"]
    req_id = granted_access(listing_id, buyer, seller)
    client.post(f"/api/access-requests/{req_id}/revoke", headers=seller)

    res = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=buyer)
    assert res.status_code == 403


def test_e4_owner_still_downloads_their_own_document(client, auth_headers, live_listing):
    """M2's behaviour is preserved once the download route is re-gated onto
    `require_private_access` (plan.md Build order, slice 6).

    **This is a regression pin, and it passes before slice 6 is written.** That
    is correct, not a vacuous pass: it asserts behaviour M2 already ships, so
    "fail first" would mean M2 is already broken. Its job is to fail if slice 6
    *breaks* the owner's download while re-gating the route — a guard against
    the change, not a proof of it. See `test_e5` for what this pair cannot do.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    doc_id = _upload(client, listing_id, seller).json()["id"]

    res = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=seller)
    assert res.status_code == 200


def test_e5_non_owner_and_never_published_listing_is_404(client, auth_headers, make_listing):
    """`test_listing_download.py::test_e2` must keep passing **unedited**
    (spec 005 D1) — this pins the same case from M5's own file so the gate's
    existence rule is covered here too, not only by inheritance.

    **A regression pin, like `test_e4` — it passes before slice 6 exists, and
    it cannot tell you whether slice 6 happened.** Be honest about the limit:
    this case already 404s today through M2's `get_owned_listing`, and after
    the re-gating it 404s through `require_private_access`. Both resolve to the
    app's `NotFound`, so *every* assertion here — status and `code` alike —
    reads identically whether slice 6 was done correctly or **not done at all**.
    Nothing in this test moves.

    That does not make it worthless, it makes it a **guard**: it fails if the
    re-gating widens the existence rule and starts confirming an unpublished
    listing to a stranger. The tests that actually *prove* the route was
    re-gated are `test_e1`/`test_e2`/`test_e3` (an approved buyer can now
    download, a requested/revoked one cannot) — all three red until slice 6
    lands. Read this one as "M2 still holds", never as "M5 shipped".
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = make_listing(seller).json()["id"]        # never submitted
    doc_id = _upload(client, listing_id, seller).json()["id"]

    res = client.get(f"/api/listings/{listing_id}/documents/{doc_id}", headers=buyer)
    assert res.status_code == 404
    assert res.json()["code"] == "not_found"


# ── Security & abuse (this file's slice: S2, S6, S7, S8) ─────────────────────

def test_s2_approved_access_does_not_transfer_across_listings(client, auth_headers, live_listing, granted_access):
    """Approval is per `(listing, buyer)` — it never transfers to a second
    listing the same buyer happens to also want into."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_x = live_listing(seller, headline="Listing X")
    listing_y = live_listing(seller, headline="Listing Y")
    granted_access(listing_x, buyer, seller)

    res = client.get(f"/api/listings/{listing_y}/private", headers=buyer)
    assert res.status_code == 403


def test_s6_expired_or_tampered_token_on_private_data_is_401_never_403(client, auth_headers, live_listing):
    """The identity boundary resolves *before* the access boundary — a broken
    token must never fall through to a 403, which would imply the caller was
    at least authenticated."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)

    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    expired = jwt.encode({"sub": "1", "exp": past}, TEST_JWT_SECRET, algorithm=TEST_JWT_ALG)
    tampered = jwt.encode({"sub": "1"}, "attacker-key", algorithm="HS256")

    for token in (expired, tampered):
        res = client.get(
            f"/api/listings/{listing_id}/private",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 401, f"token attack got {res.status_code}, want 401 (never 403)"


def test_s7_probing_access_request_ids_gives_a_uniform_no_existence_signal(
    client, auth_headers, live_listing, request_access
):
    """A real id belonging to someone else's request and a plainly nonexistent
    one must be indistinguishable to a caller who owns neither — no oracle
    for which rows exist (`security.md` §6 Enumeration & scraping)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    listing_id = live_listing(seller)
    real_id = request_access(listing_id, buyer).json()["id"]

    real_probe = client.post(f"/api/access-requests/{real_id}/approve", headers=stranger)
    fake_probe = client.post(f"/api/access-requests/{real_id + 987_654}/approve", headers=stranger)

    assert real_probe.status_code == fake_probe.status_code
    assert real_probe.json().get("code") == fake_probe.json().get("code")


def test_s8_a_403_from_the_gate_leaks_nothing(client, auth_headers, live_listing):
    seller_email = "seller@example.com"
    seller, buyer = _seller_and_buyer(auth_headers, seller_email=seller_email)
    listing_id = live_listing(seller, company_name="SecretCo", website_url="https://secret.example.com")

    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 403

    body = res.json()
    assert "code" in body and "detail" in body        # the generic contract (error_handling.md §7)
    blob = res.text.lower()
    for leak in ("secretco", "secret.example.com", seller_email, "select", "traceback", "sqlalchemy", ".py"):
        assert leak not in blob, f"{leak!r} leaked through a 403"
