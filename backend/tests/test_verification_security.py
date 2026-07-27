"""M10 buyer verification — the crown-jewel security criteria (S1-S9), spec 010.

Written failing first. M10 is on the security-critical list because it adds a
badge that is *the* trust signal a seller uses to decide who reads their data
room (FR-14), fed by a hostile file upload. `security.md` §7's M10 line is
*"buyer cannot self-verify (`verified` ignored/403); only admin flips it;
proof-of-funds upload obeys the M2 upload rules"* — three sentences with four
failure modes worth a test file:

1. **The buyer flips their own badge.** Either by mass-assigning the column
   through the one route that already writes to `User` (S1), or by calling the
   admin decision routes directly (S2). Both produce a `verified: true` a seller
   will trust, from a person no admin ever looked at.
2. **The queue or the file leaks sideways.** The admin queue is every pending
   buyer's identity in one response (S3, S8); a proof-of-funds document is this
   milestone's most sensitive artifact and lives under an id an attacker can
   simply increment (S4/S5).
3. **The upload escapes.** A client filename reaching the storage path is
   arbitrary file write (S7) — the M2 rule this route reuses (spec 010 D5), on a
   new caller and a new key space.
4. **A route ships without a gate at all.** S6 is the default-deny floor across
   all six new routes.

Two conventions, both load-bearing:

**Every 404 assertion also asserts the machine `code`.** An unmounted route 404s
too — with Starlette's bare `{"detail": "Not Found"}` — so a status-only
assertion passes vacuously today and never has a red phase (the trap named in
`test_watchlist_security.py`, `test_offers.py::test_a5`, `test_nda_gate.py::test_d8`).
S4 is where this bites hardest: it asserts a 404 on a route that does not exist
yet, so without the `code` it would be green from birth. The same reasoning
drives S4's *positive* control assertion (the owner can fetch their own
document) — "everything 404s" must not be able to satisfy an IDOR test.

**Criteria owned by another file are written hyphenated — `V-3`, never the bare
form** — so this file cannot accidentally satisfy
`scripts/check_spec_coverage.py`'s citation check for a criterion it does not
test. The V- and X-group criteria live in `tests/test_verification.py`.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from tests.conftest import VALID_PDF

# ── Declared response shapes (plan 010 § Response models) ────────────────────
#
# Allow-lists, not deny-lists: a deny-list only catches the leaks we thought of,
# while `set(row) <= ALLOWED` also fails on any field a *future* edit adds. That
# is the difference between a schema boundary that is enforced and one that is
# aspirational (the `test_watchlist_security.py::test_w11` technique).

# `VerificationDocumentRead`. Both filename spellings are permitted because the
# spec's criterion says `filename` and plan.md's model says `original_filename`;
# `storage_key` is absent from both, deliberately (S9).
ALLOWED_DOCUMENT_FIELDS = {
    "id",
    "original_filename",
    "filename",
    "content_type",
    "size_bytes",
    "uploaded_at",
}
FILENAME_KEYS = {"original_filename", "filename"}

# `AdminVerificationQueueRead` — admin-only, so `email` is deliberately in scope
# here (same class as `AdminListingRead`'s seller identity at M3) and nothing
# else about the user is.
ALLOWED_QUEUE_FIELDS = {
    "user_id",
    "email",
    "display_name",
    "budget",
    "target_industries",
    "experience",
    "verification_status",
    "documents",
}

# Never on any surface: the credential, the other role/identity columns, and the
# internal storage path.
FORBIDDEN_ANYWHERE = {
    "password_hash",
    "hashed_password",
    "is_admin",
    "storage_key",
    "nda_signed_at",
    "deleted_at",
}

PROFILE = {
    "display_name": "Dana Buyer",
    "budget": "750000",
    "target_industries": "SaaS, marketplaces",
    "experience": "one prior acquisition",
}


def _upload_base() -> Path:
    """The configured uploads root, resolved — a temp dir in tests (conftest)."""
    from app.config import settings

    return Path(settings.upload_dir).resolve()


def _files_under(base: Path) -> set[Path]:
    return {p for p in base.rglob("*") if p.is_file()} if base.exists() else set()


def _stored_key(session, document_id: int) -> str:
    """The server-generated storage key of a verification document.

    Read straight from the table because the response model has no such field
    (S9) — inspecting only what the API returns cannot prove what was written.
    """
    row = session.execute(
        text("SELECT storage_key FROM buyerverificationdocument WHERE id = :i"),
        {"i": document_id},
    ).first()
    assert row is not None, f"no verification document row with id {document_id}"
    return row[0]


# ── S1-S2 — the buyer cannot flip their own badge ────────────────────────────


def test_s1_verification_status_cannot_be_mass_assigned_via_the_profile_route(
    client, auth_headers
):
    """S1 — `PUT /api/profile` is the one route that already writes to `User`.

    The attacker's request, written first: the profile route loops over
    `body.model_dump(exclude_unset=True)` and `setattr`s each field onto the
    caller's own `User` row (`app/routers/profile.py`). If M10's new column ever
    appears on `ProfileUpdate` — or if that loop is ever rewritten to dump the
    raw request JSON instead of the schema — then a buyer self-verifies with one
    PUT and every seller's `BuyerProfile` view starts lying.

    The assertion is deliberately *ignored*, not 422: `ProfileUpdate` is a plain
    SQLModel with no `extra="forbid"`, so an undeclared field is dropped at
    parse time. That is the control being pinned — the field has no way in, so
    it does not need to be rejected. Three checks, because "200" alone would
    also be true of a route that applied the field: the echoed `UserRead` must
    not claim `verified`, the legitimate fields in the same body must still have
    landed (proving the body was honored, not silently discarded whole), and the
    authoritative read must still say `unverified`.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")

    res = client.put(
        "/api/profile",
        json={
            **PROFILE,
            "verification_status": "verified",
            "verification_reviewed_at": "2020-01-01T00:00:00",
            "verification_reason": "self-approved",
            "verified": True,
        },
        headers=buyer,
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("verification_status") != "verified", body
    assert body.get("verified") is not True, body
    assert body["display_name"] == "Dana Buyer", body      # the body was honored

    after = client.get("/api/verification", headers=buyer)
    assert after.status_code == 200, after.text
    assert after.json()["verification_status"] == "unverified", after.text


def test_s2_non_admin_cannot_approve_or_reject_a_verification(
    client, auth_headers, user_id
):
    """S2 — the decision routes are the only path to `verified`; they are admin-only.

    Two shapes of the same attack: the buyer approves *themselves* (the direct
    self-verify), and the buyer approves *someone else* (griefing / manufacturing
    a trusted counterparty). Both must be 403, and `require_admin` reads
    `is_admin` from the DB row per request (`permissions.py`), so a token minted
    before a demotion cannot be replayed into this either.

    **No submission is seeded on purpose.** The gate must refuse before any row
    lookup runs: an implementation that returned 404 "no such pending
    verification" for a non-admin would be handing out an existence oracle over
    the user table to anyone with an account — the refusal has to be about the
    *caller*, not about the target. Asserting 403 (not "403 or 404") is what
    pins that ordering.
    """
    attacker = auth_headers(email="attacker@example.com", role="buyer")
    victim = auth_headers(email="victim@example.com", role="buyer")
    attacker_id, victim_id = user_id(attacker), user_id(victim)

    responses = {
        "approve-self": client.post(
            f"/api/admin/verifications/{attacker_id}/approve", headers=attacker
        ),
        "approve-other": client.post(
            f"/api/admin/verifications/{victim_id}/approve", headers=attacker
        ),
        "reject-self": client.post(
            f"/api/admin/verifications/{attacker_id}/reject",
            json={"reason": "self-approved"},
            headers=attacker,
        ),
        "reject-other": client.post(
            f"/api/admin/verifications/{victim_id}/reject",
            json={"reason": "griefing"},
            headers=attacker,
        ),
    }

    assert {name: r.status_code for name, r in responses.items()} == {
        "approve-self": 403,
        "approve-other": 403,
        "reject-self": 403,
        "reject-other": 403,
    }
    for name, res in responses.items():
        assert res.json().get("code") == "forbidden", f"{name}: {res.text}"


# ── S3, S8 — the admin queue is not a buyer-visible surface ──────────────────


def test_s3_non_admin_cannot_read_the_verification_queue(client, auth_headers):
    """S3 — the queue is every pending buyer's identity in one response.

    A read-only route is the one most likely to be mounted with only
    `get_current_user` (it "just lists things"), and this particular list is
    email + budget + industries + submitted-document ids for every buyer under
    review. The 403 has to come from `require_admin`, so the `code` is asserted
    too — a bare 404 here would mean the route simply is not mounted, which is
    not the same as being gated.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")

    res = client.get("/api/admin/verifications", headers=buyer)

    assert res.status_code == 403, res.text
    assert res.json().get("code") == "forbidden", res.text


def test_s8_the_admin_queue_leaks_no_credential_or_undeclared_user_field(
    client, session, auth_headers, admin_headers, pending_verification
):
    """S8 — the queue's field set is exactly what plan.md declares, and no more.

    The weakest implementation that passes every core criterion is
    `response_model=list[User]` (or a `UserRead` reused because it "already has
    the profile fields") — the queue would show display name, budget, industries
    and documents exactly as required, while also serializing `password_hash`,
    `is_admin`, and `nda_signed_at` to whoever holds an admin token. That is a
    schema boundary bug, not an authorization bug, so no permission test can
    catch it; only an allow-list over the returned keys can.

    Asserted three ways: the key set is a subset of the declared model, the
    nested document entries obey the document allow-list too (a leak one level
    down is still a leak), and the buyer's real bcrypt hash does not appear
    anywhere in the raw response text — a field *renamed* on the way out would
    still be a leak, and only a value comparison catches that.

    The list is asserted non-empty first: an allow-list over zero rows is the
    classic vacuous pass.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")
    assert client.put("/api/profile", json=PROFILE, headers=buyer).status_code == 200
    pending_verification(buyer)
    stored_hash = session.execute(
        text('SELECT password_hash FROM "user" WHERE email = :e'),
        {"e": "dana@example.com"},
    ).first()[0]

    res = client.get("/api/admin/verifications", headers=admin_headers())

    assert res.status_code == 200, res.text
    rows = res.json()
    assert isinstance(rows, list) and rows, res.text
    for row in rows:
        leaked = set(row) & FORBIDDEN_ANYWHERE
        assert not leaked, f"forbidden field(s) exposed: {leaked}"
        assert set(row) <= ALLOWED_QUEUE_FIELDS, (
            f"undeclared field(s): {set(row) - ALLOWED_QUEUE_FIELDS}"
        )
        for doc in row.get("documents", []):
            assert set(doc) <= ALLOWED_DOCUMENT_FIELDS, (
                f"undeclared document field(s): {set(doc) - ALLOWED_DOCUMENT_FIELDS}"
            )
    assert stored_hash and stored_hash not in res.text
    assert "password" not in res.text.lower()


# ── S4, S5 — the document download boundary (owner or admin, nobody else) ────


def test_s4_one_buyers_document_is_404_for_another_buyer(
    client, auth_headers, pending_verification
):
    """S4 — IDOR on the most sensitive artifact this milestone stores.

    Document ids are sequential integers, so the attacker's request is `GET
    /api/verification/documents/1..N` with a valid account — the whole attack is
    a for-loop. `get_owned_or_admin_verification_document` (plan 010) is the one
    thing standing between that loop and every buyer's bank statement.

    Constructed so it cannot pass for the wrong reason, in three ways:

    * **B's document genuinely exists.** A test that asked for a nonexistent id
      would prove nothing — "404 because nothing is there" is indistinguishable
      from "404 because it is not yours", and the IDOR would be untested.
    * **A can fetch A's own document (200).** Without this control, the
      degenerate implementation that 404s everything — including a route that
      does not exist at all — satisfies the criterion.
    * **A's 404 is byte-identical to the 404 for an id that was never issued.**
      The 4xx contract is `{detail, code}` with no request id (`main.py`), so a
      well-meaning split — `NotFound("Not your document")` on one path,
      `NotFound("Document not found")` on the other — is a working oracle for
      which document ids exist, i.e. for how many buyers have submitted. This is
      `test_watchlist_security.py::test_w10`'s existence-oracle discipline.
    """
    buyer_a = auth_headers(email="a@example.com", role="buyer")
    buyer_b = auth_headers(email="b@example.com", role="buyer")
    _, doc_a = pending_verification(buyer_a)
    _, doc_b = pending_verification(buyer_b)
    assert doc_a != doc_b

    own = client.get(f"/api/verification/documents/{doc_a}", headers=buyer_a)
    foreign = client.get(f"/api/verification/documents/{doc_b}", headers=buyer_a)
    never_issued = client.get("/api/verification/documents/987654", headers=buyer_a)

    assert own.status_code == 200, own.text            # the route works for its owner
    assert foreign.status_code == 404, foreign.text
    assert foreign.json().get("code") == "not_found", foreign.text
    assert (foreign.status_code, foreign.json()) == (
        never_issued.status_code,
        never_issued.json(),
    )


def test_s5_an_admin_can_download_any_buyers_verification_document(
    client, auth_headers, admin_headers, pending_verification
):
    """S5 — the *positive* half of the same boundary; D9 depends on it.

    Manual review (F11) is impossible if the reviewer cannot open the file, and
    spec D9 records holding the document ourselves precisely because there is no
    vendor to hold it. So this is the one identity other than the uploader that
    passes — and it must pass on the real bytes, not merely on a 200: an
    implementation that returned the *metadata* here would satisfy a
    status-only assertion while leaving the admin unable to review anything.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")
    _, document_id = pending_verification(buyer)

    res = client.get(f"/api/verification/documents/{document_id}", headers=admin_headers())

    assert res.status_code == 200, res.text
    assert res.content == VALID_PDF


# ── S6 — default-deny across every route the milestone adds ──────────────────


def test_s6_all_six_verification_routes_require_authentication(
    client, auth_headers, submit_verification, pending_verification, user_id
):
    """S6 — the floor: no route in this milestone is reachable anonymously.

    Every route is exercised against a resource that **really exists** (a real
    buyer id, a real document id), following `test_watchlist_security.py::test_s3`:
    otherwise a 401 could be an accident of the target being absent, and the
    test would not prove the auth dependency ran *before* any lookup. The upload
    is sent with a valid file part for the same reason — a 422 for the missing
    part would mask a missing gate.

    Asserted as one dict comparison rather than six separate asserts so a
    partial pass cannot hide: pytest shows the whole map, and the route that
    answers 200 (or 404, i.e. never mounted) is visible immediately.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")
    buyer_id, document_id = pending_verification(buyer)
    assert user_id(buyer) == buyer_id

    responses = {
        "POST /verification/documents": submit_verification({}),
        "GET /verification": client.get("/api/verification"),
        "GET /verification/documents/{id}": client.get(
            f"/api/verification/documents/{document_id}"
        ),
        "GET /admin/verifications": client.get("/api/admin/verifications"),
        "POST /admin/verifications/{id}/approve": client.post(
            f"/api/admin/verifications/{buyer_id}/approve"
        ),
        "POST /admin/verifications/{id}/reject": client.post(
            f"/api/admin/verifications/{buyer_id}/reject", json={"reason": "no"}
        ),
    }

    assert {route: r.status_code for route, r in responses.items()} == {
        "POST /verification/documents": 401,
        "GET /verification": 401,
        "GET /verification/documents/{id}": 401,
        "GET /admin/verifications": 401,
        "POST /admin/verifications/{id}/approve": 401,
        "POST /admin/verifications/{id}/reject": 401,
    }


# ── S7 — the upload is hostile input (M2's rules, a new key space) ───────────


def test_s7_a_traversal_filename_cannot_escape_the_uploads_base(
    client, session, auth_headers, submit_verification
):
    """S7 — arbitrary file write is the worst outcome available on this route.

    The attacker's request: a multipart part whose `filename` is
    `../../etc/passwd`. `storage.save(user.id, data, suffix)` builds
    `{base}/{user_id}/{uuid}{suffix}` — a server-generated uuid, so the client
    name is never in the path (`storage.py`, and `_resolve_within_base` refuses
    an escape as a second layer). This test pins that property on M10's new
    caller, where the first path segment is now a *user* id (spec D5).

    Both dressings of the attack are sent, because they exercise different
    layers and the criterion ("the client filename never reaches the storage
    path") covers both:

    * the spec's literal `../../etc/passwd` — no whitelisted extension, so M2's
      extension check refuses it before storage is reached at all;
    * the same traversal wearing `.pdf` — this one gets past validation and
      **must** be stored confined, which is where the real assertion is.

    Proving confinement takes more than "it 201'd" (M2's `test_d5` proves it by
    fetching the document back; this does that **and** goes to the filesystem):
    the stored key contains no `..` and no attacker-chosen name, the resolved
    path is inside the configured base, and the traversal's actual targets —
    `{base}/..`-relative `etc/passwd*` — do not exist afterwards. A snapshot
    diff of the base is used rather than "exactly one file", because the uploads
    temp dir is session-scoped and shared with every other test that uploads.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")
    base = _upload_base()
    before = _files_under(base)
    targets = [
        base.parent / "etc" / "passwd",
        base.parent / "etc" / "passwd.pdf",
        base / "etc" / "passwd",
        base / "etc" / "passwd.pdf",
    ]
    target_existed = {t: t.exists() for t in targets}

    bare = submit_verification(buyer, filename="../../etc/passwd")
    dressed = submit_verification(buyer, filename="../../etc/passwd.pdf")

    # The bare form has no whitelisted extension: refused (415) or — if a future
    # implementation accepts it — still confined, which the checks below cover.
    assert bare.status_code in (201, 415), bare.text
    assert dressed.status_code == 201, dressed.text

    document_id = dressed.json()["id"]
    key = _stored_key(session, document_id)
    assert ".." not in key and "passwd" not in key and not Path(key).is_absolute(), key
    stored = (base / key).resolve()
    assert stored.is_relative_to(base), f"{stored} escaped {base}"
    assert stored.is_file(), stored

    for t in targets:
        assert t.exists() == target_existed[t], f"traversal wrote to {t}"
    new_files = _files_under(base) - before
    assert new_files, "nothing was written under the uploads base"
    for created in new_files:
        assert created.resolve().is_relative_to(base), created
        assert "passwd" not in created.name, created

    # ...and the confined file is still the one the gated route serves back.
    dl = client.get(f"/api/verification/documents/{document_id}", headers=buyer)
    assert dl.status_code == 200, dl.text
    assert dl.content == VALID_PDF


# ── S9 — the caller's own view exposes metadata, never the storage path ──────


def test_s9_the_verification_read_never_exposes_the_storage_key(
    client, session, auth_headers, pending_verification
):
    """S9 — `storage_key` is an internal path component, not client data.

    The weakest implementation of `GET /api/verification` is
    `response_model=list[BuyerVerificationDocument]` — every core criterion
    passes (id, filename, type, size, timestamp are all there) while the server's
    key space leaks: `{user_id}/{uuid}.pdf` hands a caller both a live user-id
    enumeration and the exact shape of the paths behind the download route,
    which is the first thing anyone probing for a static-serving mistake or a
    traversal wants.

    Allow-list rather than `"storage_key" not in row`, so a future edit that
    adds any undeclared field fails here too — and the *value* of the real key
    is asserted absent from the raw response text, because a key re-exposed
    under a friendlier name (`path`, `url`, `location`) is the same leak.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")
    _, document_id = pending_verification(buyer)
    key = _stored_key(session, document_id)

    res = client.get("/api/verification", headers=buyer)

    assert res.status_code == 200, res.text
    documents = res.json()["documents"]
    assert isinstance(documents, list) and documents, res.text
    for doc in documents:
        assert set(doc) <= ALLOWED_DOCUMENT_FIELDS, (
            f"undeclared field(s): {set(doc) - ALLOWED_DOCUMENT_FIELDS}"
        )
        assert doc.keys() & FILENAME_KEYS, f"no display filename in {doc}"
    assert "storage_key" not in res.text
    assert key and key not in res.text
    # The uuid stem alone, in case only the directory part were stripped.
    assert Path(key).stem not in res.text


# ── S10 — the *serving* half of the reused upload seam ───────────────────────


def test_s10_the_download_response_sanitizes_the_filename_header(
    client, session, auth_headers, pending_verification
):
    """S10 — a stored filename reaching a response header unescaped.

    M2's `download_document` already does this correctly — `os.path.basename`,
    then strip `"`/CR/LF, cap at 200, serve as `attachment` (`listings.py`). Spec
    010 D5 calls this route a "narrower reuse of the same seam", and the seam has
    two halves: storing the bytes *and* serving them back. Nothing in the V or S
    groups originally asked about the second half, so a new route that returns
    `Response(content=..., headers={"Content-Disposition": f'inline;
    filename="{doc.original_filename}"'})` would pass every other criterion in
    this file — including S4, S5 and S9 — while handing an uploader control of a
    response header, and rendering a buyer-supplied file same-origin.

    **Why the hostile name is seeded into the row rather than uploaded:** httpx
    applies HTML5 form encoding to a multipart `filename`, rewriting `"` to
    `%22` and CR/LF to `%0D`/`%0A`, so our own test client physically cannot
    deliver the raw bytes. That is a property of the client, not of the server —
    `curl`, or any hand-rolled request, is under no such obligation, and the
    column holds whatever the parser hands it. Seeding the state the API cannot
    express is exactly the `testing_guide.md` §3.4 fixture exception; the
    assertion under test is the *response*, which is reached through the real
    gated route either way.
    """
    buyer = auth_headers(email="dana@example.com", role="buyer")
    _, document_id = pending_verification(buyer)
    hostile = 'a";\r\nX-Injected: 1.pdf'
    session.execute(
        text(
            "UPDATE buyerverificationdocument SET original_filename = :f WHERE id = :i"
        ),
        {"f": hostile, "i": document_id},
    )
    session.commit()

    res = client.get(f"/api/verification/documents/{document_id}", headers=buyer)

    assert res.status_code == 200, res.text
    disposition = res.headers["content-disposition"]
    assert disposition.startswith("attachment"), disposition
    assert "\r" not in disposition and "\n" not in disposition, repr(disposition)
    # The quote is what breaks out of `filename="..."`; the CRLF is what starts a
    # new header. Neither survives, so the smuggled header never materializes.
    assert "x-injected" not in {k.lower() for k in res.headers}, dict(res.headers)
    assert disposition.count('"') <= 2, disposition


# ── S11 — the badge must not outlive the fact it reports ─────────────────────


def test_s11_a_revoked_badge_disappears_from_the_sellers_access_request_queue(
    client, auth_headers, live_listing, request_access, verified_buyer, admin_headers
):
    """S11 — V-8's negative twin: the seller's badge is *current*, not a snapshot.

    V-8 proves a verified buyer reads as verified; V-14 proves an admin revoke
    flips the column. Neither asks the composition question, and the composition
    is where the trust failure lives: the badge is the seller's decision input
    for opening their data room (FR-14), so a badge that survives its own
    revocation is precisely the mis-trust event this milestone exists to prevent.

    The implementation that fails here is the tempting one — denormalizing
    `verified` onto the `AccessRequest` row at request time, or caching the
    profile on approval — which M8's D1/D2 lesson already names: a projection can
    outlive the fact it projects, and the gate stays "correct" while the answer
    it gives goes stale. `BuyerProfile` must read through to the live `User` row.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="dana@example.com", role="buyer")
    admin = admin_headers()
    listing_id = live_listing(seller)
    buyer_id, _ = verified_buyer(buyer, admin=admin)
    request_access(listing_id, buyer)

    before = client.get(f"/api/my/listings/{listing_id}/access-requests", headers=seller)
    assert before.status_code == 200, before.text
    assert before.json()[0]["buyer"]["verified"] is True, before.text

    revoked = client.post(
        f"/api/admin/verifications/{buyer_id}/reject",
        json={"reason": "Fraud reported after approval"},
        headers=admin,
    )
    assert revoked.status_code == 200, revoked.text

    after = client.get(f"/api/my/listings/{listing_id}/access-requests", headers=seller)

    assert after.status_code == 200, after.text
    entry = after.json()[0]["buyer"]
    assert entry["verification_status"] == "rejected", after.text
    assert entry["verified"] is False, after.text
