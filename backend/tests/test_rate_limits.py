"""spec pre-011 — Rate limiting the routes that never got it (R1-R7, S1-S5).

Written failing first (constitution Article 3 §2). Nothing this file exercises
exists yet: `ratelimit.client_ip`, `ratelimit.enforce_per_ip`,
`ratelimit.enforce_per_user`, `ratelimit.reset_all`, the limiter registry, and
every call site in plan.md § Call sites are all unwritten, and the new
`config.py` settings (`browse_rate_limit_max` and friends, `trusted_proxies`)
do not exist. Every test below is expected to fail — most with an `AttributeError`
on a limiter or setting that has not been built yet, which is the correct
failure mode: it proves the test reaches for the real thing rather than a mock
of it.

**Caps are reached by monkeypatching a limiter's `max_attempts` down, never by
firing volume at it** — deterministic, fast, and it keeps each test about
*behavior at the cap* rather than about today's configured number.

**`TestClient` always reports `request.client.host` as `"testclient"`.** That
shapes three tests here directly, and is called out again in each one's
docstring so it doesn't read as an accident:

- S1 gets a shared IP for free — it only needs two different authenticated
  users.
- S2 and R6 need to *vary* the apparent source address, which is only possible
  by sending `X-Forwarded-For` with the peer added to `trusted_proxies`
  — the exact deployment shape D3 describes, not a way of cheating the test.
- S3 is the mirror image: `trusted_proxies` stays empty (the default), the
  client varies `X-Forwarded-For` on every request, and the limit must still
  bite. This is the most important test in the file — a limiter that trusts a
  client-supplied header is weaker than no limiter at all, because the caller
  picks a fresh counter key per request.

R6 is written to stay enumeration-safe (M8 G2/G14: `forgot-password` must
answer identically for a known and an unknown address, including under load).
So R6 does **not** assert a visibly different status for the capped attempt —
it asserts the *mail was not dispatched*, via the existing `outbox` fixture.
A 429 there would itself be the oracle the uniform-202 rule exists to close.
"""

from __future__ import annotations

import importlib

import pytest

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _upload_listing_doc(client, listing_id, headers, filename="pnl.pdf"):
    return client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": (filename, _PDF, "application/pdf")},
        headers=headers,
    )


# plan.md's call-site table names `_upload_limiter` identically for both
# `POST /listings/{id}/documents` and `POST /verification/documents`, and its
# config comment calls the cap "shared by both document routes" — one limiter,
# not two independent ones that happen to share a name. Which module
# constructs it is an implementation choice the plan does not pin down
# (`uploads.py` already hosts the other logic the two routes share, so it is
# at least as plausible a home as either router). Trying each plausible
# location keeps this test about the *behavior* — one shared per-user upload
# budget — rather than a guess about file layout it would then be free to
# contradict.
_UPLOAD_LIMITER_CANDIDATES = [
    ("app.uploads", "_upload_limiter"),
    ("app.routers.listings", "_upload_limiter"),
    ("app.routers.verification", "_upload_limiter"),
]


def _locate_upload_limiter():
    for module_path, attr in _UPLOAD_LIMITER_CANDIDATES:
        module = importlib.import_module(module_path)
        if hasattr(module, attr):
            return getattr(module, attr)
    pytest.fail(
        f"no {_UPLOAD_LIMITER_CANDIDATES[0][1]!r} found in any of "
        f"{[m for m, _ in _UPLOAD_LIMITER_CANDIDATES]} — plan pre-011's shared "
        "upload rate limiter does not exist yet"
    )


# ── R — the limits themselves ────────────────────────────────────────────────


def test_r1_anonymous_browse_cap_is_429_rate_limited(client, monkeypatch):
    """R1 — the weakest implementation that would still pass is a browse route
    with no limiter at all: every request just returns 200. Lowering
    `max_attempts` to 2 and asserting the 3rd request specifically carries the
    `rate_limited` code (not merely a non-200) is what catches a route that
    happens to 429 for an unrelated reason, or that limits browsing under some
    *other* code.
    """
    from app.routers import listings as listings_router

    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 2, raising=False)

    first = client.get("/api/listings")
    second = client.get("/api/listings")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    third = client.get("/api/listings")

    assert third.status_code == 429, third.text
    assert third.json().get("code") == "rate_limited"


def test_r2_paging_within_the_cap_never_trips_the_limiter(client, monkeypatch):
    """R2 — the limit must not break the ordinary reading pattern the
    marketplace depends on. The weakest implementation that would still pass
    R1 alone is an off-by-one that counts the (N+1)th hit as already over
    cap — this sends exactly `max_attempts` requests, no more, and requires
    every single one to succeed.
    """
    from app.routers import listings as listings_router

    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 3, raising=False)

    responses = [
        client.get("/api/listings", params={"offset": offset, "limit": 5})
        for offset in (0, 5, 10)
    ]

    assert [r.status_code for r in responses] == [200, 200, 200], [r.text for r in responses]


def test_r3_access_request_cap_blocks_the_write_not_just_the_response(
    client, auth_headers, live_listing, request_access, session, monkeypatch
):
    """R3 — a limiter that checks *after* the row is written is not a limiter,
    it is a decoration. The weakest implementation that would still pass a
    status-only assertion is exactly that: it 429s the response but the
    `AccessRequest` row for the refused attempt is already committed. This
    asserts the row's absence directly from the table, not through any
    response the app controls.
    """
    from sqlalchemy import text

    from app.routers import access as access_router

    monkeypatch.setattr(
        access_router._access_request_limiter, "max_attempts", 2, raising=False
    )

    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_ids = [live_listing(seller) for _ in range(3)]

    assert request_access(listing_ids[0], buyer).status_code == 201
    assert request_access(listing_ids[1], buyer).status_code == 201

    refused = request_access(listing_ids[2], buyer)

    assert refused.status_code == 429, refused.text
    assert refused.json().get("code") == "rate_limited"

    row_count = session.execute(
        text("SELECT COUNT(*) FROM accessrequest WHERE listing_id = :i"),
        {"i": listing_ids[2]},
    ).scalar()
    assert row_count == 0, "a refused request must leave no AccessRequest row"


def test_r4_seller_document_upload_rate_cap_is_429_not_413(
    client, auth_headers, make_listing, monkeypatch
):
    """R4 — must be distinguishable from M10's 413 `file_too_large` /
    `upload_quota_exceeded`: that is about how much is *stored*, this is about
    how fast it arrives. The weakest implementation that would still pass
    `test_listing_upload.py` is one that folds the rate check into the
    existing quota check and 413s instead — this asserts the machine `code`,
    not just a 4xx, so that confusion cannot pass silently.
    """
    limiter = _locate_upload_limiter()
    monkeypatch.setattr(limiter, "max_attempts", 2, raising=False)

    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]

    first = _upload_listing_doc(client, listing_id, seller, filename="pnl1.pdf")
    second = _upload_listing_doc(client, listing_id, seller, filename="pnl2.pdf")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    third = _upload_listing_doc(client, listing_id, seller, filename="pnl3.pdf")

    assert third.status_code == 429, third.text
    assert third.json().get("code") == "rate_limited"


def test_r5_buyer_verification_upload_rate_cap_is_429(
    client, auth_headers, submit_verification, monkeypatch
):
    """R5 — the verification-document mirror of R4, on the other route that
    shares `_upload_limiter`. Each upload here also legally advances
    `verification_status` (unverified/rejected/pending are all resubmission-
    allowed), so the weakest implementation that would still pass is one that
    only ever refuses via the *state machine* (e.g. treats a third upload as
    "nothing changed, so decline") rather than via the rate limiter — the
    `rate_limited` code is what rules that out.
    """
    limiter = _locate_upload_limiter()
    monkeypatch.setattr(limiter, "max_attempts", 2, raising=False)

    buyer = auth_headers(email="buyer@example.com", role="buyer")

    first = submit_verification(buyer, filename="proof1.pdf")
    second = submit_verification(buyer, filename="proof2.pdf")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    third = submit_verification(buyer, filename="proof3.pdf")

    assert third.status_code == 429, third.text
    assert third.json().get("code") == "rate_limited"


def test_r8_the_upload_budget_is_one_per_user_across_both_routes(
    client, auth_headers, make_listing, submit_verification, monkeypatch
):
    """R8 — the sharing itself, which R4 and R5 between them never assert.

    `upload_rate_limit_max`'s comment says "shared by both document routes",
    and both R4 and R5 pass whether that is true or not: if `listings.py` and
    `verification.py` each construct their own `_upload_limiter`, each route
    still refuses at its own cap and each test still goes green — while a
    caller quietly gets **double** the budget the config promises. The only way
    to see it is to spend the allowance on one route and then present the other.

    So: exhaust the cap entirely via listing documents, then upload a
    verification document as the same user. One shared limiter refuses it. Two
    independent limiters return 201, and that 201 is the bug.

    Per plan.md the shared instance lives in `app/uploads.py` — the module both
    routers already import their validator and storage backend from (M10) — so
    "shared" is true by construction rather than by two modules agreeing.
    """
    limiter = _locate_upload_limiter()
    monkeypatch.setattr(limiter, "max_attempts", 2, raising=False)

    owner = auth_headers(email="dual@example.com", role="seller")
    listing_id = make_listing(owner).json()["id"]

    first = _upload_listing_doc(client, listing_id, owner, filename="one.pdf")
    second = _upload_listing_doc(client, listing_id, owner, filename="two.pdf")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    # The budget is spent. A different route must not hand out a fresh one.
    crossover = submit_verification(owner, filename="proof.pdf")

    assert crossover.status_code == 429, crossover.text
    assert crossover.json().get("code") == "rate_limited"


def test_r6_forgot_password_address_cap_refuses_mail_without_a_visible_429(
    client, auth_headers, outbox, monkeypatch
):
    """R6 — the victim-side cap (D6): three *different* attacker IPs, none of
    which ever reaches the existing per-IP cap, hammer one real address. The
    weakest implementation that would still look correct from the outside is
    one with no address-keyed cap at all — every request just mails again —
    so this counts dispatched mail, not response codes.

    **Deliberately does not assert a distinguishable status for the capped
    request** (M8 G2/G14): a 429 here would itself be an oracle telling an
    attacker the address is real and worth hammering. Every response must
    stay the uniform `202 {"status": "accepted"}`, and the only observable
    difference is that the 3rd mail never goes out.

    Uses `X-Forwarded-For` with the peer and proxy hop in `trusted_proxies` to
    present three distinct source addresses — `TestClient` cannot otherwise
    vary `request.client.host`, and a fixed reverse-proxy hop count is exactly
    the deployment D3 describes, not a way of rigging the test.
    """
    from app.config import settings
    from app.routers import auth as auth_router

    monkeypatch.setattr(
        settings, "trusted_proxies", ["testclient", "10.0.0.1"], raising=False
    )
    monkeypatch.setattr(
        auth_router._forgot_password_address_limiter, "max_attempts", 2, raising=False
    )

    victim_email = "victim@example.com"
    auth_headers(email=victim_email, role="buyer")  # a real, registered address

    responses = [
        client.post(
            "/api/auth/forgot-password",
            json={"email": victim_email},
            headers={"X-Forwarded-For": f"{ip}, 10.0.0.1"},
        )
        for ip in ("11.0.0.1", "22.0.0.2", "33.0.0.3")
    ]

    assert [r.status_code for r in responses] == [202, 202, 202], [r.text for r in responses]
    assert [r.json() for r in responses] == [{"status": "accepted"}] * 3

    # Count *reset* mail specifically, not everything addressed to the victim:
    # registering them (the arrangement above) already sent M8's email
    # verification link to the same address. Asserting on the total would make
    # a signup consume the reset budget — which would be a real bug, not a
    # test detail: a later legitimate "resend verification" could then be
    # suppressed by an attacker's reset flood. The cap is on reset requests,
    # which is what D6 says and what the setting's name says.
    resets = [m for m in outbox.to(victim_email) if m["subject"].startswith("Reset")]
    assert len(resets) == 2, (
        "the address cap must stop the 3rd reset mail even though each of the "
        f"3 requests came from a distinct, never-before-seen IP (saw {len(resets)}: "
        f"{[m['subject'] for m in outbox.to(victim_email)]})"
    )


def test_r7_a_429_carries_retry_after_and_the_generic_contract(client, monkeypatch):
    """R7 — D7: a caller told to back off but not for how long will poll,
    which is the behavior the limiter exists to prevent. The weakest
    implementation that would still pass R1 is a 429 with a `Retry-After`-free
    body, or one that leaks how the key was derived (e.g. echoing the IP) —
    this pins both the header's presence and the body's exact shape.
    """
    from app.routers import listings as listings_router

    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 1, raising=False)

    ok = client.get("/api/listings")
    assert ok.status_code == 200, ok.text

    limited = client.get("/api/listings")

    assert limited.status_code == 429, limited.text
    body = limited.json()
    assert set(body) == {"detail", "code"}, body
    assert body["code"] == "rate_limited"
    assert "Retry-After" in limited.headers
    retry_after = limited.headers["Retry-After"]
    assert retry_after.isdigit() and int(retry_after) > 0, retry_after


# ── S — the abuse each one blocks, including the ways a limiter can be
#        worse than useless ─────────────────────────────────────────────────


def test_s1_two_users_behind_one_ip_do_not_share_an_identity_keyed_limit(
    client, auth_headers, live_listing, request_access, monkeypatch
):
    """S1 — D2: authenticated routes key on the JWT-derived identity, never
    the address. `TestClient` reporting the same `"testclient"` host for
    every request makes the "shared IP" half of this free — the weakest
    implementation that would still pass every single-user test is one keyed
    on `client_ip` instead of `user.id`, which would make buyer B's own,
    first-ever request 429 for a cap buyer A alone exhausted. A NAT'd office
    sharing one bucket is a self-inflicted outage, and this is the test that
    would catch it.
    """
    from app.routers import access as access_router

    monkeypatch.setattr(
        access_router._access_request_limiter, "max_attempts", 1, raising=False
    )

    seller = auth_headers(email="seller@example.com", role="seller")
    buyer_a = auth_headers(email="a@example.com", role="buyer")
    buyer_b = auth_headers(email="b@example.com", role="buyer")
    listing_1 = live_listing(seller)
    listing_2 = live_listing(seller)

    first = request_access(listing_1, buyer_a)
    assert first.status_code == 201, first.text

    exhausted = request_access(listing_2, buyer_a)
    assert exhausted.status_code == 429, exhausted.text

    unaffected = request_access(listing_1, buyer_b)
    assert unaffected.status_code == 201, unaffected.text


def test_s2_changing_ip_does_not_reset_an_identity_keyed_limit(
    client, auth_headers, live_listing, sign_nda, monkeypatch
):
    """S2 — the other half of D2: identity-keyed limits must survive an IP
    change, or an attacker evades every cap for free by rotating addresses.
    The weakest implementation that would still pass S1 is one keyed on
    `f"{user.id}:{client_ip}"` instead of `user.id` alone — that also
    isolates two users on one IP, but lets one user reset their own cap by
    presenting a new one, which is exactly what this test exhausts and then
    retries against.

    Varies the apparent address via `X-Forwarded-For` with
    the peer and proxy hop placed in `trusted_proxies` (harness note, module
    docstring) — `TestClient` cannot otherwise change `request.client.host`.
    """
    from app.config import settings
    from app.routers import access as access_router

    monkeypatch.setattr(
        settings, "trusted_proxies", ["testclient", "10.0.0.1"], raising=False
    )
    monkeypatch.setattr(
        access_router._access_request_limiter, "max_attempts", 1, raising=False
    )

    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_a = live_listing(seller)
    listing_b = live_listing(seller)
    sign_nda(buyer)

    first = client.post(
        f"/api/listings/{listing_a}/access-request",
        headers={**buyer, "X-Forwarded-For": "1.1.1.1, 10.0.0.1"},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/api/listings/{listing_b}/access-request",
        headers={**buyer, "X-Forwarded-For": "2.2.2.2, 10.0.0.1"},
    )

    assert second.status_code == 429, second.text
    assert second.json().get("code") == "rate_limited"


def test_s3_a_client_supplied_x_forwarded_for_cannot_evade_the_ip_limit(
    client, monkeypatch
):
    """S3 — the crown jewel of this file (D3). `trusted_proxies` stays at its
    default (empty) — deliberately *not* monkeypatched here, because an empty
    allowlist means the immediate peer is never trusted, which is both the
    local-dev configuration and the vulnerable-by-default case if `client_ip`
    ever read the header without checking who the peer is.

    The weakest implementation that would still pass R1 is `client_ip`
    reading `X-Forwarded-For` whenever present, trusted or not — a caller
    would then pick a fresh key on every single request and the counter would
    never advance past 1. That is worse than having no limiter at all,
    because the limiter's presence would be advertised (the route documents
    a cap) while doing nothing. This sends a *different* forged address on
    every request and requires the 3rd one to still 429 — proving the real
    key came from the connection, not the header.
    """
    from app.config import settings
    from app.routers import listings as listings_router

    assert not getattr(settings, "trusted_proxies", [])

    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 2, raising=False)

    first = client.get("/api/listings", headers={"X-Forwarded-For": "1.1.1.1"})
    second = client.get("/api/listings", headers={"X-Forwarded-For": "2.2.2.2"})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    spoofed = client.get("/api/listings", headers={"X-Forwarded-For": "3.3.3.3"})

    assert spoofed.status_code == 429, spoofed.text
    assert spoofed.json().get("code") == "rate_limited"


def test_s4_trusted_proxy_extracts_the_real_client_not_the_proxys_address(
    client, monkeypatch
):
    """S4 — the deployment case D3 exists for, and the mirror of S3: when the
    immediate peer *is* one of our own proxies, two different clients behind it
    must get their own counters rather than sharing the proxy's.

    The weakest implementation that would still pass S3 is one that keys on
    `request.client.host` unconditionally — behind a real proxy that is the
    proxy's address for every caller in the world, so the cap would be shared
    globally and the first busy client would lock everyone out. That is the
    failure this test's second client trips.

    `TestClient` reports `request.client.host` as `"testclient"`, so that is
    what goes in the allowlist — which is exactly the deployment shape D3
    describes (the peer we accept forwarded headers from), not a shortcut.
    """
    from app.config import settings
    from app.routers import listings as listings_router

    monkeypatch.setattr(settings, "trusted_proxies", ["testclient"], raising=False)
    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 1, raising=False)

    client_a_first = client.get("/api/listings", headers={"X-Forwarded-For": "9.9.9.1"})
    assert client_a_first.status_code == 200, client_a_first.text

    client_a_exhausted = client.get(
        "/api/listings", headers={"X-Forwarded-For": "9.9.9.1"}
    )
    assert client_a_exhausted.status_code == 429, client_a_exhausted.text

    # A different client behind the identical trusted proxy gets its own counter.
    client_b = client.get("/api/listings", headers={"X-Forwarded-For": "9.9.9.2"})
    assert client_b.status_code == 200, client_b.text


def test_s8_a_header_of_only_trusted_entries_falls_back_to_the_peer(
    client, monkeypatch
):
    """S8 — the loop's fall-through, which no other test exercises.

    When every entry in `X-Forwarded-For` is itself a trusted proxy, the
    right-to-left walk finds no untrusted entry and must fall back to the
    connection address. Two ways to get this wrong: return the last entry
    inspected (a proxy's address, shared by every caller behind it — S4's bug
    reintroduced through the back door), or return an empty string, which makes
    one bucket for the entire internet.

    Both hops are trusted here, so two requests that differ *only* in their
    forwarded chain must still land on the same counter — proving the fallback
    is the peer and not the header.
    """
    from app.config import settings
    from app.routers import listings as listings_router

    monkeypatch.setattr(
        settings, "trusted_proxies", ["testclient", "10.0.0.1", "10.0.0.2"],
        raising=False,
    )
    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 2, raising=False)

    first = client.get("/api/listings", headers={"X-Forwarded-For": "10.0.0.1"})
    second = client.get("/api/listings", headers={"X-Forwarded-For": "10.0.0.2, 10.0.0.1"})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    third = client.get("/api/listings", headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"})

    assert third.status_code == 429, third.text
    assert third.json().get("code") == "rate_limited"


def test_s7_a_second_forwarded_for_header_line_cannot_shadow_our_proxys(
    client, monkeypatch
):
    """S7 — the hole that hides behind `request.headers.get()`.

    `X-Forwarded-For` is a list header, and a sender may split it across
    multiple header *lines* instead of commas — RFC 7230 §3.2.2 makes the two
    forms equivalent, and a proxy appending its own line rather than extending
    the client's is entirely conformant. `.get()` returns only the **first**
    line. So a client that sends its own `X-Forwarded-For` line first gets that
    line walked, our proxy's line never read, and the attacker back in control
    of the key — with `trusted_proxies` configured correctly and S3/S6 both
    still green, because neither sends two lines.

    The fix is to join every line in receipt order before walking. This test is
    what keeps it: a refactor back to `.get()` is a one-character change that
    nothing else in this file would notice.

    Same shape as S6 — the forged line varies per request, so if it were the
    key each request would get a fresh counter and the third would return 200.
    """
    from app.config import settings
    from app.routers import listings as listings_router

    monkeypatch.setattr(settings, "trusted_proxies", ["testclient"], raising=False)
    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 2, raising=False)

    def _two_lines(forged: str):
        # httpx preserves a list of tuples as repeated header lines.
        return client.get(
            "/api/listings",
            headers=[("x-forwarded-for", forged), ("x-forwarded-for", "9.9.9.1")],
        )

    first = _two_lines("1.1.1.1")
    second = _two_lines("2.2.2.2")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    third = _two_lines("3.3.3.3")

    assert third.status_code == 429, third.text
    assert third.json().get("code") == "rate_limited"


def test_s6_a_forged_prepended_entry_is_never_the_key(client, monkeypatch):
    """S6 — the failure mode the replaced hop-count design had (D3's amendment).

    Once the peer is trusted, the header *is* read — so the question becomes
    which entry. A client can prepend anything it likes, and those forgeries
    land to the **left** of the address our own proxy appended. Walking from the
    right and stopping at the first non-trusted entry therefore reads the real
    client and never the forgery.

    The implementation this catches is any that takes the header's *leftmost*
    entry (the widespread "first entry is the client" folklore, true only when
    no client ever lies) or that indexes by a hop count an operator can set too
    high. Either way the attacker picks the key, gets a fresh counter per
    request, and the cap never fires. So: same real client, a *different*
    forged prefix each time, and the third request must still be refused.
    """
    from app.config import settings
    from app.routers import listings as listings_router

    monkeypatch.setattr(settings, "trusted_proxies", ["testclient"], raising=False)
    monkeypatch.setattr(listings_router._browse_limiter, "max_attempts", 2, raising=False)

    first = client.get("/api/listings", headers={"X-Forwarded-For": "1.1.1.1, 9.9.9.1"})
    second = client.get("/api/listings", headers={"X-Forwarded-For": "2.2.2.2, 9.9.9.1"})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    third = client.get("/api/listings", headers={"X-Forwarded-For": "3.3.3.3, 9.9.9.1"})

    assert third.status_code == 429, third.text
    assert third.json().get("code") == "rate_limited"


def test_r9_the_in_memory_backend_evicts_keys_whose_window_has_elapsed(monkeypatch):
    """R9 — the limiter must not become the memory leak it was added to prevent.

    `InMemoryRateLimiterBackend` has never evicted. That was defensible while
    only login/register/forgot-password were keyed per IP: the key space was
    bounded by addresses that bother to attempt authentication. Keying **public
    browse** per IP changes it entirely — the key space becomes every address
    that ever fetches a listing, and an attacker rotating source addresses grows
    the dict without bound *through the control added to stop them*. That is a
    new denial-of-service path opened by a mitigation, which is why it is fixed
    in this pass rather than recorded in §9.

    Tested at the backend rather than through a route because the property is
    about the store, not about any endpoint: ten thousand distinct keys are one
    dict, and no HTTP test can observe a dict's size honestly.

    Time is advanced by monkeypatching the clock rather than by sleeping — the
    backend uses `time.monotonic`, and a real sleep would make this the slowest
    test in the suite for no added confidence.
    """
    from app import ratelimit

    backend = ratelimit.InMemoryRateLimiterBackend()
    fake_now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: fake_now[0])

    for n in range(50):
        backend.hit(f"browse:ip:10.0.0.{n}", window_seconds=60)
    assert len(backend._hits) == 50, "arrangement: 50 distinct keys recorded"

    # Every one of those windows has now fully elapsed.
    fake_now[0] += 3600
    backend.hit("browse:ip:203.0.113.9", window_seconds=60)

    remaining = set(backend._hits)
    assert remaining == {"browse:ip:203.0.113.9"}, (
        f"{len(remaining) - 1} elapsed key(s) retained — the store grows without "
        "bound for every distinct address ever seen"
    )


def test_s5_the_registry_covers_every_rate_limiter_the_app_builds():
    """S5 — D4: a limiter nobody registered is a limiter `reset_all()` cannot
    clear, which reopens exactly the cross-test state leak the registry
    exists to close. The weakest implementation that would still pass every
    other test in this file is a registry that is simply a hand-maintained
    list of the limiters this branch happens to add — every other R/S test
    here only ever touches the one or two limiters it already knows the name
    of, so none of them would notice a stray, unregistered one.

    So this does not hardcode an expected count (which would pass vacuously
    the day someone adds an eleventh limiter and forgets it here too). It
    rediscovers the limiters by introspection and asserts that set is a subset
    of `ratelimit._REGISTRY` — the registry has to cover what was *built*, not
    merely what its author remembered to list.

    **The exact guarantee, stated precisely because the first version of this
    docstring overstated it** (caught by the pre-011 appsec pass): the scan
    walks the five *router* modules, so what it proves is "every limiter
    reachable from a router module is registered" — not "every limiter in the
    app". Today those coincide, and `_upload_limiter` is caught because both
    routers `from ..uploads import _upload_limiter`, which binds it into their
    namespaces too — a real mechanism, not luck. But a limiter defined in a
    non-router module and never imported by one would evade this check. If that
    ever happens, widen the scan rather than trusting this test's name.
    """
    from app import ratelimit
    from app.routers import access as access_router
    from app.routers import auth as auth_router
    from app.routers import chat as chat_router
    from app.routers import listings as listings_router
    from app.routers import verification as verification_router

    router_modules = [
        auth_router,
        chat_router,
        listings_router,
        access_router,
        verification_router,
    ]
    built = {
        id(value)
        for module in router_modules
        for value in vars(module).values()
        if isinstance(value, ratelimit.RateLimiter)
    }
    assert built, "expected at least one RateLimiter across the routers, found none"

    registered = {id(limiter) for limiter in ratelimit._REGISTRY}

    assert built <= registered, (
        f"{len(built - registered)} limiter(s) constructed but never registered "
        "in ratelimit._REGISTRY — reset_all() would silently skip them"
    )
