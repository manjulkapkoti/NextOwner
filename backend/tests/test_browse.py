"""M4 — the public marketplace browse (spec 004: A, B, C, S, E-n).

The first endpoints in the project that an anonymous stranger may call, and the
first response model whose job is to *withhold*. Two controls do all the work
and both are asserted here:

  1. a `WHERE status = 'live'` clause  — nothing unapproved is public (A1, C2)
  2. the `ListingPublic` schema        — identity fields cannot leak (A4, C4, S3)

S3 asserts the control itself rather than one of its outputs, so a field added
to the model in a later milestone is caught even if no route test covers it.
"""

import itertools

import pytest


@pytest.fixture
def make_live(client, auth_headers, admin_headers, make_listing):
    """Create a listing and walk it to `live` through the real endpoints.

    `live` is only reachable via admin approval (M3, spec 003 B1-B5), so this
    submits and approves rather than force-setting the status — the fixture
    exercises the same path a real listing takes. Each call registers its own
    seller so the tests never depend on one account owning everything.
    """
    admin = admin_headers()
    counter = itertools.count(1)

    def _make(**overrides):
        n = next(counter)
        seller = auth_headers(email=f"seller{n}@example.com", role="seller")
        listing_id = make_listing(seller, **overrides).json()["id"]
        client.post(f"/api/listings/{listing_id}/submit", headers=seller)
        client.post(f"/api/listings/{listing_id}/approve", headers=admin)
        return listing_id

    return _make


def _ids(response):
    return [item["id"] for item in response.json()["items"]]


# ── A — the public browse collection ─────────────────────────────────────────

def test_a1_only_live_listings_are_returned(client, auth_headers, make_listing, make_live, force_status):
    live_id = make_live()
    seller = auth_headers(email="hidden@example.com", role="seller")
    for status in ("draft", "pending_review", "rejected", "paused", "closed"):
        hidden = make_listing(seller).json()["id"]
        force_status(hidden, status)

    assert _ids(client.get("/api/listings")) == [live_id]


def test_a2_a_sellers_own_draft_is_absent_even_with_their_token(client, auth_headers, make_listing):
    seller = auth_headers(email="drafter@example.com", role="seller")
    make_listing(seller)
    # The public route is public for everyone — the dashboard is /api/my/listings.
    assert client.get("/api/listings", headers=seller).json()["items"] == []


def test_a3_browse_needs_no_authentication(client, make_live):
    make_live()
    assert client.get("/api/listings").status_code == 200


def test_a4_no_item_carries_an_identity_field(client, make_live):
    listing_id = make_live(company_name="SecretCo", website_url="https://secret.example.com")
    res = client.get("/api/listings")

    # Prove the response is the real thing before asserting what is missing from
    # it — an absence assertion passes vacuously against a 404, which would be a
    # leak test that can never fail.
    assert res.status_code == 200 and _ids(res) == [listing_id]

    for leak in ("SecretCo", "secret.example.com", "company_name", "website_url",
                 "detailed_financials", "owner_id"):
        assert leak not in res.text, f"{leak!r} must not cross the public boundary"


def test_a5_pagination_returns_the_requested_window(client, make_live):
    ids = [make_live(headline=f"Business {i}") for i in range(5)]
    ordered = list(reversed(ids))              # newest-published first (A9)
    assert _ids(client.get("/api/listings?limit=2&offset=2")) == ordered[2:4]


def test_a6_a_default_page_size_is_applied_when_limit_is_absent(client, make_live):
    for i in range(25):
        make_live(headline=f"Business {i}")
    body = client.get("/api/listings").json()
    assert len(body["items"]) == 20 and body["limit"] == 20


def test_a7_a_limit_above_the_cap_is_refused(client):
    # An explicit 422, not a silent clamp — a silent clamp hides the caller's
    # mistake and makes the DoS ceiling invisible (spec S7).
    assert client.get("/api/listings?limit=5000").status_code == 422


def test_a8_money_is_serialized_as_an_exact_string(client, make_live):
    make_live(asking_price="500000.00")
    assert client.get("/api/listings").json()["items"][0]["asking_price"] == "500000.00"


def test_a9_results_are_ordered_newest_published_first(client, make_live):
    ids = [make_live(headline=f"Business {i}") for i in range(3)]
    assert _ids(client.get("/api/listings")) == list(reversed(ids))


def test_a10_the_envelope_reports_the_total_beyond_the_page(client, make_live):
    for i in range(5):
        make_live(headline=f"Business {i}")
    body = client.get("/api/listings?limit=2").json()
    assert len(body["items"]) == 2 and body["total"] == 5


def test_a11_an_empty_marketplace_is_not_an_error(client):
    res = client.get("/api/listings")
    assert res.status_code == 200 and res.json()["items"] == [] and res.json()["total"] == 0


# ── B — filters and keyword search ───────────────────────────────────────────

def test_b1_type_filter(client, make_live):
    saas = make_live(type="saas")
    make_live(type="ecommerce")
    assert _ids(client.get("/api/listings?type=saas")) == [saas]


def test_b2_price_range_is_inclusive(client, make_live):
    cheap = make_live(asking_price="100000.00")
    mid = make_live(asking_price="200000.00")
    make_live(asking_price="900000.00")
    got = _ids(client.get("/api/listings?min_price=100000&max_price=200000"))
    assert sorted(got) == sorted([cheap, mid])


def test_b3_min_profit_filter(client, make_live):
    rich = make_live(ttm_profit="300000.00")
    make_live(ttm_profit="10000.00")
    assert _ids(client.get("/api/listings?min_profit=100000")) == [rich]


@pytest.mark.parametrize(
    "query,expect_match",
    [
        ("type=saas&min_price=100000&max_price=600000&min_profit=100000", True),
        ("type=ecommerce&min_price=100000&max_price=600000&min_profit=100000", False),
        ("type=saas&min_price=600000&max_price=900000&min_profit=100000", False),
        ("type=saas&min_price=100000&max_price=600000&min_profit=400000", False),
    ],
)
def test_b4_filter_combinations_apply_every_clause(client, make_live, query, expect_match):
    target = make_live(type="saas", asking_price="500000.00", ttm_profit="120000.00")
    got = _ids(client.get(f"/api/listings?{query}"))
    assert (target in got) is expect_match


def test_b5_keyword_matches_the_headline(client, make_live):
    found = make_live(headline="Profitable scheduling SaaS", description="Nothing here.")
    make_live(headline="Pet supply store", description="Nothing here.")
    assert _ids(client.get("/api/listings?q=scheduling")) == [found]


def test_b6_keyword_matches_the_description(client, make_live):
    found = make_live(headline="A business", description="Serves dental clinics nationwide.")
    make_live(headline="Another business", description="Sells coffee.")
    assert _ids(client.get("/api/listings?q=dental")) == [found]


def test_b7_keyword_search_is_case_insensitive(client, make_live):
    found = make_live(headline="Profitable scheduling SaaS")
    assert _ids(client.get("/api/listings?q=SCHEDULING")) == [found]


def test_b8_keyword_search_never_reaches_private_data(client, make_live):
    """The identity oracle (spec D4/B8).

    A search box that confirms "SecretCo" exists defeats FR-6 without ever
    rendering the field — so `q` must cover public text only.
    """
    make_live(
        headline="Profitable scheduling SaaS",
        description="A tool for clinics.",
        company_name="SecretCo",
        website_url="https://secretco.example.com",
    )
    assert client.get("/api/listings?q=SecretCo").json()["items"] == []


def test_b9_sql_metacharacters_in_q_are_parameterized(client, make_live):
    make_live()
    res = client.get("/api/listings?q=' OR 1=1 --")
    assert res.status_code == 200 and res.json()["items"] == []


def test_b10_like_wildcards_in_q_are_escaped(client, make_live):
    make_live(headline="Profitable scheduling SaaS")
    # An unescaped '%' would match every row — it must match literally.
    assert client.get("/api/listings?q=%").json()["items"] == []


def test_b11_a_non_numeric_price_is_422_with_a_field_level_detail(client):
    res = client.get("/api/listings?min_price=cheap")
    assert res.status_code == 422
    assert "min_price" in res.text


def test_b12_min_price_above_max_price_is_an_empty_result(client, make_live):
    make_live(asking_price="500000.00")
    res = client.get("/api/listings?min_price=900000&max_price=100000")
    assert res.status_code == 200 and res.json()["items"] == []


def test_b13_a_filter_matching_nothing_returns_an_empty_page(client, make_live):
    make_live(type="saas")
    body = client.get("/api/listings?type=laundromat").json()
    assert body["items"] == [] and body["total"] == 0


# ── C — the public listing detail ────────────────────────────────────────────

def test_c1_a_live_listing_is_publicly_readable(client, make_live):
    listing_id = make_live()
    res = client.get(f"/api/listings/{listing_id}")
    assert res.status_code == 200 and res.json()["id"] == listing_id


def test_c2_a_non_live_listing_is_404_even_to_its_owner(client, auth_headers, make_listing, force_status):
    seller = auth_headers(email="owner@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]
    for status in ("draft", "pending_review", "rejected", "paused", "closed"):
        force_status(listing_id, status)
        res = client.get(f"/api/listings/{listing_id}", headers=seller)
        assert res.status_code == 404, f"the public route must not serve {status!r}"


def test_c3_a_missing_listing_is_indistinguishable_from_a_non_live_one(
    client, auth_headers, make_listing, force_status
):
    seller = auth_headers(email="owner@example.com", role="seller")
    hidden = make_listing(seller).json()["id"]
    force_status(hidden, "draft")

    missing = client.get("/api/listings/999999")
    non_live = client.get(f"/api/listings/{hidden}")
    assert missing.status_code == non_live.status_code == 404
    assert missing.json()["detail"] == non_live.json()["detail"]   # no existence oracle


def test_c4_the_detail_body_carries_no_identity_field(client, make_live):
    listing_id = make_live(company_name="SecretCo", website_url="https://secret.example.com")
    res = client.get(f"/api/listings/{listing_id}")

    # As in A4: confirm the body is a real listing before asserting absences.
    assert res.status_code == 200 and res.json()["id"] == listing_id

    for leak in ("SecretCo", "secret.example.com", "company_name", "website_url",
                 "detailed_financials", "owner_id"):
        assert leak not in res.text


# ── Security & abuse ─────────────────────────────────────────────────────────

def test_s3_the_public_model_excludes_identity_fields_by_construction(client):
    """Assert the control, not one of its outputs.

    A field added to `ListingPublic` in a later milestone is caught here even
    if no route test happens to cover it.
    """
    from app.schemas import ListingPublic

    forbidden = {"owner_id", "status", "company_name", "website_url", "detailed_financials"}
    assert forbidden.isdisjoint(set(ListingPublic.model_fields))


def test_s8_an_authed_caller_gets_no_wider_response_than_an_anonymous_one(
    client, make_live, admin_headers
):
    listing_id = make_live(company_name="SecretCo")
    anonymous = client.get("/api/listings")
    as_admin = client.get("/api/listings", headers=admin_headers(email="admin2@example.com"))

    # Two 404s are also "identical" — pin that both calls really returned the
    # listing before comparing them.
    assert anonymous.status_code == 200 and _ids(anonymous) == [listing_id]
    assert as_admin.status_code == 200
    assert anonymous.json() == as_admin.json()   # a public route never widens for a token


def test_s9_no_sequence_of_seller_actions_reaches_the_public_browse(
    client, auth_headers, make_listing
):
    """Reachability, extending spec 003's E6 to the newly public surface.

    M3 proved a seller cannot reach `live`. M4 must prove the converse for the
    surface that matters: appearing in browse *requires* an admin approval. The
    per-door tests each name one door; this walks the corridor.
    """
    from itertools import product

    # One seller, a fresh listing per sequence: registering per sequence would
    # mean 125 bcrypt hashes and turn a fast invariant check into a slow one.
    seller = auth_headers(email="walker@example.com", role="seller")
    actions = ["submit", "pause", "resume", "close", "edit"]
    for sequence in product(actions, repeat=3):
        listing_id = make_listing(seller).json()["id"]
        for action in sequence:
            if action == "edit":
                client.put(
                    f"/api/listings/{listing_id}",
                    json={"headline": "Edited without review"},
                    headers=seller,
                )
            else:
                client.post(f"/api/listings/{listing_id}/{action}", headers=seller)
        visible = _ids(client.get("/api/listings"))
        assert listing_id not in visible, (
            f"seller-only sequence {sequence} published to the public marketplace"
        )


# ── Errors & failure modes ───────────────────────────────────────────────────

def test_e2_a_failure_in_the_browse_path_returns_the_generic_contract(client, session, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("SELECT company_name FROM listingprivate")

    monkeypatch.setattr(session, "exec", boom)
    res = client.get("/api/listings")
    assert res.status_code == 500
    assert res.json()["detail"] == "Something went wrong on our end."
    assert "request_id" in res.json()
    blob = res.text.lower()
    for leak in ("select", "listingprivate", "traceback", "sqlalchemy", ".py"):
        assert leak not in blob


def test_e3_a_public_404_carries_the_machine_code_and_no_detail(client):
    res = client.get("/api/listings/999999")
    assert res.status_code == 404 and res.json()["code"] == "not_found"
    assert "exist" not in res.json()["detail"].lower()   # says nothing about the row
