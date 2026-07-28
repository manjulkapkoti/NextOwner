"""M11 — the two public routes (C, L) and the failure contract (X), spec 011.

Written failing first. Neither `POST /api/valuation` nor `POST /api/valuation/leads`
exists yet, so every test here currently 404s.

**Every X-group 422 additionally asserts the offending field name appears in the
error body.** The neighbouring files warn about status-only assertions passing
vacuously on an unmounted route (`test_offers.py::test_a5`,
`test_watchlist_security.py`) — that trap is about 404, since an unmounted path
404s with Starlette's bare `{"detail": "Not Found"}`. A 422 assertion is red on
an unmounted route for the same reason (the 404 arrives before any body
validation), so these are genuinely failing today; the field-name assertion is
there for the *next* failure mode instead — a route that rejects the request for
some unrelated reason and still scores a 422.

The milestone has **no 409** — nothing here transitions, so no transition can be
illegal. Recorded in spec §5's X preamble so a reviewer running the `security.md`
§8 matrix does not hunt for a test that should not exist.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# Row 1 of spec §6.6 — the case whose expected output V1 already pins.
VALID_INPUT = {
    "type": "saas",
    "ttm_revenue": "200000",
    "ttm_profit": "100000",
    "growth_pct": "0",
    "churn_pct": "0",
}


def _lead_count(session) -> int:
    """Count `ValuationLead` rows. Imported lazily because the model does not
    exist yet — a module-level import would break collection for the whole file
    rather than failing the tests that actually depend on it."""
    from sqlmodel import select

    from app.models import ValuationLead

    return len(session.exec(select(ValuationLead)).all())


def _field_names(body) -> str:
    """Flatten a 422 body to searchable text, so a test can assert *which* field
    was rejected without coupling to Pydantic's exact envelope shape."""
    return str(body).lower()


# ── C — POST /api/valuation (public, writes nothing) ─────────────────────────


def test_c1_anonymous_calculate_returns_the_estimate(client):
    """C1 — no Authorization header, and a complete estimate comes back."""
    r = client.post("/api/valuation", json=VALID_INPUT)
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"low", "high", "driver", "explanation", "disclaimer"}
    assert body["driver"] == "profit"
    assert Decimal(body["low"]) == Decimal("300000")
    assert Decimal(body["high"]) == Decimal("500000")


def test_c2_route_agrees_with_the_shared_model(client):
    """C2 — the route computes via `app.valuation`, it does not reimplement it.

    Asserted by equality with the module's own answer rather than with a literal:
    a literal would pass if the route grew a *second* implementation that happened
    to agree today, which is precisely the drift D1 exists to prevent.
    """
    from app.valuation import estimate_valuation

    expected = estimate_valuation(
        type="saas",
        ttm_revenue=Decimal("200000"),
        ttm_profit=Decimal("100000"),
        growth_pct=Decimal("0"),
        churn_pct=Decimal("0"),
    )
    body = client.post("/api/valuation", json=VALID_INPUT).json()
    assert Decimal(body["low"]) == expected.low
    assert Decimal(body["high"]) == expected.high
    assert body["driver"] == expected.driver
    assert body["explanation"] == expected.explanation


def test_c3_calculate_persists_nothing(client, session):
    """C3 — the anonymous route everyone hits must not create rows (D2).

    This is the structural claim the whole two-route split rests on: if the
    calculate route ever writes, the milestone's storage surface is unbounded
    anonymous traffic rather than a 5-per-hour lead form.
    """
    before = _lead_count(session)
    for _ in range(3):
        assert client.post("/api/valuation", json=VALID_INPUT).status_code == 200
    assert _lead_count(session) == before


def test_c4_response_carries_the_disclaimer(client):
    """C4 — the caveat travels in the API response, not only in UI chrome (D11).

    A client that renders the number and drops the disclaimer is a client bug;
    an API that never sent one is our bug.
    """
    body = client.post("/api/valuation", json=VALID_INPUT).json()
    assert isinstance(body["disclaimer"], str)
    assert body["disclaimer"].strip()


def test_c5_optional_inputs_may_be_omitted(client):
    """C5 — `growth_pct` / `churn_pct` default to neutral factors (§6.1).

    Omitting them must equal supplying zero for both, or the form silently
    penalizes a visitor for leaving a field blank.
    """
    minimal = {"type": "saas", "ttm_revenue": "200000", "ttm_profit": "100000"}
    r = client.post("/api/valuation", json=minimal)
    assert r.status_code == 200
    assert Decimal(r.json()["low"]) == Decimal("300000")
    assert Decimal(r.json()["high"]) == Decimal("500000")


# ── L — POST /api/valuation/leads (the one writing route) ────────────────────


def test_l1_lead_capture_stores_a_row_and_returns_the_estimate(client, session):
    """L1 — FR-23's second half, and the M11 fold-in."""
    r = client.post(
        "/api/valuation/leads",
        json={**VALID_INPUT, "email": "founder@example.com"},
    )
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["low"]) == Decimal("300000")
    assert body["driver"] == "profit"
    assert _lead_count(session) == 1


def test_l2_stored_estimate_is_server_computed(client, session):
    """L2 — the row records our number, not the client's (Article 2 #4).

    Paired with S5, which sends a *conflicting* value. This half proves the
    stored figure is right; S5 proves a supplied one is ignored.
    """
    from sqlmodel import select

    from app.models import ValuationLead

    client.post(
        "/api/valuation/leads",
        json={**VALID_INPUT, "email": "founder@example.com"},
    )
    row = session.exec(select(ValuationLead)).one()
    assert row.estimate_low == Decimal("300000")
    assert row.estimate_high == Decimal("500000")
    assert row.driver == "profit"


def test_l3_repeat_submissions_both_succeed_and_both_store(client, session):
    """L3 — no unique constraint, no 409, no enumeration oracle (D7).

    The *security* property is that the second response is indistinguishable from
    the first. A duplicate-detecting 409 here would answer "is this address
    already known to NextOwner?" for anyone who asked — the same question M1's
    login and M8's forgot-password refuse to answer.
    """
    first = client.post(
        "/api/valuation/leads", json={**VALID_INPUT, "email": "founder@example.com"}
    )
    second = client.post(
        "/api/valuation/leads",
        json={**VALID_INPUT, "ttm_profit": "150000", "email": "founder@example.com"},
    )
    assert first.status_code == 201
    assert second.status_code == first.status_code
    assert set(second.json()) == set(first.json())
    assert _lead_count(session) == 2


def test_l4_stored_row_carries_the_submitted_inputs(client, session):
    """L4 — the inputs are captured alongside the estimate, so a lead is a lead
    (what they have) and not just an address."""
    from sqlmodel import select

    from app.models import ValuationLead

    client.post(
        "/api/valuation/leads",
        json={
            "type": "ecommerce",
            "ttm_revenue": "150000",
            "ttm_profit": "40000",
            "growth_pct": "25",
            "churn_pct": "3",
            "email": "shop@example.com",
        },
    )
    row = session.exec(select(ValuationLead)).one()
    assert row.email == "shop@example.com"
    assert row.type == "ecommerce"
    assert row.ttm_revenue == Decimal("150000")
    assert row.ttm_profit == Decimal("40000")
    assert row.growth_pct == Decimal("25")
    assert row.churn_pct == Decimal("3")
    assert row.created_at is not None


# ── X — Errors & failure modes (`docs/error_handling.md`) ────────────────────

# Both public routes take the same inputs, so every input-validation rule is
# asserted on both. A rule enforced on one route and forgotten on the other is
# the exact shape of bug this parametrization exists to catch — and the leads
# route is the one that would *persist* the bad value.
BOTH_ROUTES = ["/api/valuation", "/api/valuation/leads"]


def _body_for(path: str, **overrides) -> dict:
    body = {**VALID_INPUT, **overrides}
    if path.endswith("/leads"):
        body["email"] = "founder@example.com"
    return body


@pytest.mark.parametrize("path", BOTH_ROUTES)
def test_x1_negative_revenue_is_422(client, path):
    """X1 — revenue below zero is not a business, it is a typo or a probe."""
    r = client.post(path, json=_body_for(path, ttm_revenue="-1", ttm_profit="-1"))
    assert r.status_code == 422
    assert "ttm_revenue" in _field_names(r.json())


@pytest.mark.parametrize("path", BOTH_ROUTES)
def test_x2_churn_above_100_is_422(client, path):
    """X2 — a "percentage" over 100 is rejected at the boundary.

    Distinct from V9, which *clamps* a valid-but-extreme 95. The line between
    them is deliberate: 95 is a real (catastrophic) churn rate, 140 is not a
    rate at all.
    """
    r = client.post(path, json=_body_for(path, churn_pct="140"))
    assert r.status_code == 422
    assert "churn_pct" in _field_names(r.json())


@pytest.mark.parametrize("path", BOTH_ROUTES)
def test_x3_profit_above_revenue_is_422(client, path):
    """X3 — the cross-field invariant (§6.1), enforced in the request model.

    Absorbing this silently would let a visitor value a business on a profit
    figure its own revenue cannot support — the model would happily multiply it.
    """
    r = client.post(path, json=_body_for(path, ttm_revenue="100000", ttm_profit="200000"))
    assert r.status_code == 422
    assert "ttm_profit" in _field_names(r.json())


@pytest.mark.parametrize("path", BOTH_ROUTES)
def test_x4_amount_beyond_the_ceiling_is_422(client, path):
    """X4 — an unbounded numeric input is an arithmetic and storage surface."""
    from app.config import settings

    over = str(Decimal(settings.valuation_max_amount) + 1)
    r = client.post(path, json=_body_for(path, ttm_revenue=over, ttm_profit="0"))
    assert r.status_code == 422
    assert "ttm_revenue" in _field_names(r.json())


@pytest.mark.parametrize("path", BOTH_ROUTES)
@pytest.mark.parametrize("missing", ["type", "ttm_revenue", "ttm_profit"])
def test_x5_missing_required_field_is_422(client, path, missing):
    """X5 — the three required inputs are required on both routes."""
    body = _body_for(path)
    del body[missing]
    r = client.post(path, json=body)
    assert r.status_code == 422
    assert missing in _field_names(r.json())


def test_x6_malformed_email_is_422_and_writes_nothing(client, session):
    """X6 — a rejected lead leaves no trace.

    The "writes nothing" half is the one worth asserting: a route that validates
    after inserting is a route whose validation does not bound the table.
    """
    before = _lead_count(session)
    r = client.post("/api/valuation/leads", json={**VALID_INPUT, "email": "not-an-email"})
    assert r.status_code == 422
    assert "email" in _field_names(r.json())
    assert _lead_count(session) == before


def test_x7_unhandled_error_returns_the_generic_500(client, monkeypatch):
    """X7 — a blow-up inside the valuation router leaks nothing.

    Forced by making the model raise *in the router's namespace*, so this
    exercises the real route through the real global handler rather than the
    `/_debug/boom` shortcut — the point being that this router, specifically, is
    covered by the M1 contract.
    """
    import app.routers.valuation as valuation_router

    def _boom(**_kwargs):
        raise RuntimeError("SELECT * FROM valuationlead -- internal detail")

    monkeypatch.setattr(valuation_router, "estimate_valuation", _boom)

    r = client.post("/api/valuation", json=VALID_INPUT)
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Something went wrong on our end."
    assert "request_id" in body
    blob = r.text.lower()
    for leak in ("traceback", "sqlalchemy", "select *", 'file "', ".py"):
        assert leak not in blob


@pytest.mark.parametrize("path", BOTH_ROUTES)
def test_x8_4xx_bodies_carry_the_error_contract_shape(client, path):
    """X8 — the 422 keeps FastAPI's native field-level shape, and leaks nothing.

    `error_handling.md` §1 is explicit that 422 is the *one* class that does not
    use the `{detail, code}` envelope: it "keep[s] FastAPI's native field-level
    shape (the frontend maps loc → field)", which is what U4's inline field errors
    depend on. So this asserts `detail` is the list-of-`loc` form, not a string.

    Checked on a 422 because it is the only 4xx these public routes can produce
    without a limiter or an identity — and it is the shape most likely to echo an
    input back, so it is where a leak would surface first.
    """
    r = client.post(path, json=_body_for(path, type="not-a-real-type"))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert all("loc" in entry and "msg" in entry for entry in detail)
    blob = r.text.lower()
    for leak in ("traceback", "sqlalchemy", 'file "', ".py"):
        assert leak not in blob
