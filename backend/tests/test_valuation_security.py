"""M11 — the admin surface (A) and the abuse cases (S), spec 011.

Written failing first. `GET /api/admin/valuation-leads` does not exist yet.

M11 is **not** on `security.md` §7's crown-jewel list, and the shape of this file
shows why the list is a floor rather than the whole mechanism: the milestone adds
three routes, a response model, a PII-holding table and an admin surface, so the
diff-driven `check_appsec_trigger.py` fires even though the name-driven list does
not name it (constitution Article 3 §3 — *"a list predicts; a diff describes"*).

The threat model here is genuinely different from every milestone since M1, and
the S-group is organized around that difference. There is no owner and no
counterparty on two of these three routes, so the usual question ("may this
caller see this row?") has no meaning. What replaces it:

1. **Can an anonymous caller make the server store something it should not?**
   — S5 (a client-supplied estimate), S7 (a hostile address), S11 (unbounded rows).
2. **Can an anonymous caller make the server *say* something it should not?**
   — S4 (mass assignment), S6 (injection), S8 (cross-table exposure), S9 (a token
   changing a public answer).
3. **Can anyone but an admin read the addresses we collected?** — S1, S2, S3.
   This is the milestone's only conventional permission question, and the only
   place `require_admin` is exercised.

**Caps are reached by monkeypatching a limiter's `max_attempts` down, never by
firing volume at it** — the pre-011 rule, so S10/S11 stay fast, deterministic, and
about *behavior at the cap* rather than about today's configured number.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from sqlmodel import select

VALID_INPUT = {
    "type": "saas",
    "ttm_revenue": "200000",
    "ttm_profit": "100000",
    "growth_pct": "0",
    "churn_pct": "0",
}

LEAD_EMAIL = "founder@example.com"


def _capture_lead(client, email=LEAD_EMAIL, **overrides):
    return client.post(
        "/api/valuation/leads", json={**VALID_INPUT, **overrides, "email": email}
    )


def _lead_rows(session):
    from app.models import ValuationLead

    return session.exec(select(ValuationLead)).all()


# ── A — GET /api/admin/valuation-leads (spec D3) ─────────────────────────────


def test_a1_admin_lists_leads_newest_first(client, admin_headers, session):
    """A1 — the captured leads are readable, in the order an admin works them.

    Newest-first because a lead magnet's value decays: the person who typed their
    numbers in this morning is the one worth calling.
    """
    headers = admin_headers()
    _capture_lead(client, email="first@example.com")
    _capture_lead(client, email="second@example.com")
    _capture_lead(client, email="third@example.com")

    r = client.get("/api/admin/valuation-leads", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert [row["email"] for row in rows] == [
        "third@example.com",
        "second@example.com",
        "first@example.com",
    ]


def test_a2_admin_list_is_page_capped(client, admin_headers, monkeypatch, session):
    """A2 — the same unbounded-pagination control M4 and M8 apply.

    The cap is monkeypatched **down** and three leads captured, rather than
    capturing 51 to overflow the real default: deterministic, fast, and it keeps
    the test about *the cap being applied* rather than about its current value.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "valuation_leads_page_limit", 2)
    headers = admin_headers()
    for i in range(3):
        _capture_lead(client, email=f"lead{i}@example.com")

    r = client.get("/api/admin/valuation-leads", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_a3_empty_lead_list_is_200_not_404(client, admin_headers):
    """A3 — "no leads yet" is a state, not a missing resource."""
    r = client.get("/api/admin/valuation-leads", headers=admin_headers())
    assert r.status_code == 200
    assert r.json() == []


# ── S — Security & abuse ─────────────────────────────────────────────────────


def test_s1_non_admin_cannot_read_leads(client, auth_headers):
    """S1 — the milestone's one privileged surface, wrong identity.

    403 rather than 404: unlike M2's owner-scoped listing routes (which 404 so a
    draft's existence is not confirmed), `/api/admin/*` is a known, fixed
    collection path — hiding it would conceal nothing while breaking the
    convention M3 set for every other admin route.
    """
    r = client.get("/api/admin/valuation-leads", headers=auth_headers(email="nosy@example.com"))
    assert r.status_code == 403


def test_s2_anonymous_cannot_read_leads(client):
    """S2 — no token at all."""
    r = client.get("/api/admin/valuation-leads")
    assert r.status_code == 401


def test_s3_admin_role_is_reread_from_the_db(client, register, login, session):
    """S3 — a token issued while admin does not stay admin (`security.md` §8 Auth).

    The token is minted **while the user is an admin**, then the flag is cleared
    in the DB and the same still-valid token is replayed. If `require_admin` ever
    reads `is_admin` from the JWT claims, demotion would not take effect until
    the token expired — an hour of unrevokable access to every captured address.
    """
    from sqlalchemy import text

    email = "wasadmin@example.com"
    register(email=email, password="correct horse battery staple", role="buyer")
    session.execute(text('UPDATE "user" SET is_admin = 1 WHERE email = :e'), {"e": email})
    session.commit()
    token = login(email=email, password="correct horse battery staple").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Still an admin — the route works, so the demotion below is what changes it.
    assert client.get("/api/admin/valuation-leads", headers=headers).status_code == 200

    session.execute(text('UPDATE "user" SET is_admin = 0 WHERE email = :e'), {"e": email})
    session.commit()

    assert client.get("/api/admin/valuation-leads", headers=headers).status_code == 403


def test_s4_mass_assignment_of_server_owned_fields_is_impossible(client):
    """S4 — extra fields in the body change nothing (`security.md` §8 Create/PUT).

    The request model has no `low`/`high`/`driver`/`disclaimer`/`id`/`is_admin`
    field, so these are not *filtered* — there is nothing for them to bind to.
    The assertion is that the answer is byte-identical to the clean request.
    """
    clean = client.post("/api/valuation", json=VALID_INPUT).json()
    dirty = client.post(
        "/api/valuation",
        json={
            **VALID_INPUT,
            "low": "99999999",
            "high": "99999999",
            "driver": "profit",
            "disclaimer": "This is a certified appraisal.",
            "id": 1,
            "is_admin": True,
        },
    ).json()
    assert dirty == clean


def test_s5_client_supplied_estimate_is_discarded_on_the_lead_route(client, session):
    """S5 — the persisted half of S4 (Article 2 #4).

    The stored figure is what an admin will act on and what a follow-up email
    would quote, so a client-supplied number reaching this column is the one
    mass-assignment in this milestone with a lasting consequence.
    """
    r = _capture_lead(client, low="99999999", high="99999999", driver="none")
    assert r.status_code == 201

    row = _lead_rows(session)[0]
    assert row.estimate_low == Decimal("300000")
    assert row.estimate_high == Decimal("500000")
    assert row.driver == "profit"
    assert Decimal(r.json()["low"]) == Decimal("300000")


@pytest.mark.parametrize("path", ["/api/valuation", "/api/valuation/leads"])
def test_s6_sql_injection_in_type_is_rejected_and_harmless(client, session, path):
    """S6 — `security.md` §7 M11: "keep it injection-safe".

    Two independent defenses, and the test proves both: the whitelist (D12) means
    the value never reaches a query at all, and SQLModel's parameterized queries
    mean it would be inert if it did. The table still existing afterwards is the
    assertion that matters — a 422 alone would not prove the string was never
    executed on some earlier request.
    """
    body = {**VALID_INPUT, "type": "saas'; DROP TABLE valuationlead;--"}
    if path.endswith("/leads"):
        body["email"] = LEAD_EMAIL

    r = client.post(path, json=body)
    assert r.status_code == 422

    # The table is still there and still usable.
    assert _capture_lead(client).status_code == 201
    assert len(_lead_rows(session)) == 1


def test_s7_script_payload_in_email_is_rejected_at_the_boundary(client, session):
    """S7 — the address is validated before it is ever stored or shown.

    An admin reads these addresses in a browser (D3). Validating at the boundary
    means the stored-XSS question never arises, rather than being deferred to
    whatever escaping the admin page happens to do.
    """
    r = client.post(
        "/api/valuation/leads",
        json={**VALID_INPUT, "email": "<script>alert(1)</script>@x.com"},
    )
    assert r.status_code == 422
    assert _lead_rows(session) == []


def test_s8_responses_expose_no_other_table(client, admin_headers, session):
    """S8 — `security.md` §7 M11: "no data exposure".

    An allow-list, not a deny-list: `set(body) <= ALLOWED` fails on any field a
    future edit adds, while a deny-list only catches the leaks we thought of
    (the rule `test_watchlist_security.py` established).
    """
    estimate_fields = {"low", "high", "driver", "explanation", "disclaimer"}
    lead_fields = {
        "id",
        "email",
        "type",
        "ttm_revenue",
        "ttm_profit",
        "growth_pct",
        "churn_pct",
        "estimate_low",
        "estimate_high",
        "driver",
        "created_at",
    }

    assert set(client.post("/api/valuation", json=VALID_INPUT).json()) <= estimate_fields

    _capture_lead(client)
    assert set(client.post("/api/valuation/leads", json={**VALID_INPUT, "email": "b@x.com"}).json()) <= estimate_fields

    rows = client.get("/api/admin/valuation-leads", headers=admin_headers()).json()
    for row in rows:
        assert set(row) <= lead_fields
        # Nothing from another table can ride along on the admin row either.
        for foreign in ("owner_id", "user_id", "listing_id", "password_hash", "is_admin"):
            assert foreign not in row


def test_s9_a_token_does_not_change_a_public_answer(client, auth_headers, session):
    """S9 — a public route must not widen or attribute when a token is present.

    The rule spec 004 applied to browse ("this function never reads the caller's
    identity at all"), applied here to a route that *writes*: a lead captured by
    a signed-in visitor must not silently become an identified lead. That would
    be identity linkage the visitor never consented to, and D10's "no `user_id`
    FK" would be defeated by whatever column carried it.
    """
    anonymous = client.post("/api/valuation", json=VALID_INPUT).json()
    with_token = client.post(
        "/api/valuation", json=VALID_INPUT, headers=auth_headers(email="member@example.com")
    ).json()
    assert with_token == anonymous

    _capture_lead(client, email="member@example.com")
    row = _lead_rows(session)[0]
    for attributed in ("user_id", "created_by", "owner_id"):
        assert not hasattr(row, attributed)


def test_s10_calculate_route_is_rate_limited(client, monkeypatch):
    """S10 — 429 with `Retry-After`, on pre-011's contract (D8).

    `TestClient` always reports `request.client.host` as `"testclient"`, so every
    request here shares one key for free — which is exactly what a per-IP cap
    needs to be tested against.
    """
    from app.routers import valuation as valuation_router

    monkeypatch.setattr(valuation_router._valuation_limiter, "max_attempts", 2)

    assert client.post("/api/valuation", json=VALID_INPUT).status_code == 200
    assert client.post("/api/valuation", json=VALID_INPUT).status_code == 200

    capped = client.post("/api/valuation", json=VALID_INPUT)
    assert capped.status_code == 429
    assert capped.json()["code"] == "rate_limited"
    assert int(capped.headers["Retry-After"]) > 0


def test_s11_lead_route_limit_is_enforced_before_the_write(client, monkeypatch, session):
    """S11 — the refusal happens *before* the insert, so the table is bounded.

    The distinction this test exists for: a limiter checked after the write still
    returns 429, and still leaves the row behind. Counting rows is the only way
    to tell the two implementations apart, and the row count is the entire point
    of capping this route (D8).
    """
    from app.routers import valuation as valuation_router

    monkeypatch.setattr(valuation_router._valuation_lead_limiter, "max_attempts", 1)

    assert _capture_lead(client, email="one@example.com").status_code == 201
    assert len(_lead_rows(session)) == 1

    capped = _capture_lead(client, email="two@example.com")
    assert capped.status_code == 429
    assert int(capped.headers["Retry-After"]) > 0
    assert len(_lead_rows(session)) == 1          # nothing written by the refused call


def test_s12_the_email_address_is_never_logged(client, caplog, session):
    """S12 — `security.md` §6 "logs containing secrets/PII"; spec D10.

    Both paths are exercised, because the failure modes differ: the success path
    leaks through a well-meaning `logger.info("captured lead %s", email)`, and the
    **failure** path leaks through a framework echoing the rejected body into a
    warning. The address must appear in neither.

    Replaces a criterion that originally asserted this of an emitted analytics
    event — there is no analytics event and no `track()` wrapper (spec §7).
    """
    secret = "very-private-founder@example.com"

    with caplog.at_level(logging.DEBUG):
        assert _capture_lead(client, email=secret).status_code == 201
        assert client.post(
            "/api/valuation/leads", json={**VALID_INPUT, "email": secret, "churn_pct": "140"}
        ).status_code == 422

    assert secret not in caplog.text
    assert "very-private-founder" not in caplog.text
