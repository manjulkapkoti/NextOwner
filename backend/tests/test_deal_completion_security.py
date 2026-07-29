"""M12 — deal completion: the forbidden paths (spec 012 § Security & abuse).

These are the crown jewels (`testing_guide.md` §1) and were written before the
happy paths in `test_deal_completion.py`. `docs/security.md` §7 M12 + §6.

Two of them (S12, S13) close a hole that exists on `main` today, before this
milestone adds a line: `update_listing` locks edits for `{closed, sold}` and
triggers re-review only from `("live", "paused")`, so `under_offer` is in
neither set — a seller can rewrite a listing's financials while a buyer's offer
stands accepted on the old terms. `relist` would then republish that
never-re-reviewed content. Spec D8.
"""

from decimal import Decimal

import pytest

ROUTES = ["mark-sold", "relist"]


def _seller_and_buyer(auth_headers):
    return (
        auth_headers(email="seller@example.com", role="seller"),
        auth_headers(email="buyer@example.com", role="buyer"),
    )


def assert_refused_by_the_gate(res):
    """A 404 that came from `get_owned_listing`, not from an unrouted path.

    Starlette answers an unknown URL with a bare `{"detail": "Not Found"}` and
    **no** `code` key, so a test that only checked `status_code == 404` would
    pass before either route exists — vacuously, and it would keep passing if
    the route were later added with no permission dependency at all. Asserting
    the machine code pins the refusal to this app's own `NotFound` (spec D3),
    which is the property being claimed. *(Written after the red-set check
    found exactly this: six ownership tests passed before a line of M12 was
    implemented — constitution Article 3 §2, "a test that passes before
    implementation is unverified".)*
    """
    assert res.status_code == 404, res.text
    assert res.json().get("code") == "not_found", (
        f"404 came from the router, not the gate: {res.text}"
    )


# ── Mass assignment (Article 2 #4) ───────────────────────────────────────────


def test_s1_mark_sold_ignores_every_client_supplied_field(
    client, auth_headers, under_offer_listing, user_id
):
    """S1 — the body cannot set the price, the timestamp, the status or the owner.

    The one test that makes the milestone's central claim believable: the sale
    price the platform records is derived from the accepted offer, full stop.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer, price="480000.00")
    seller_id = user_id(seller)

    res = client.post(
        f"/api/listings/{listing_id}/mark-sold",
        json={
            "final_price": "1.00",
            "sold_at": "1999-01-01T00:00:00Z",
            "status": "live",
            "owner_id": 999,
            "published_at": "1999-01-01T00:00:00Z",
        },
        headers=seller,
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert Decimal(body["final_price"]) == Decimal("480000.00")
    assert not body["sold_at"].startswith("1999")
    assert body["status"] == "sold"
    assert body["owner_id"] == seller_id
    assert not body["published_at"].startswith("1999")


# ── IDOR / ownership (spec D3 — 404, not 403) ────────────────────────────────


@pytest.mark.parametrize("route", ROUTES)
def test_s2_s3_another_seller_cannot_close_or_relist_your_deal(
    client, auth_headers, under_offer_listing, route
):
    """S2/S3 — a stranger gets 404, and the listing is untouched."""
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="seller")
    listing_id, _ = under_offer_listing(seller, buyer)

    res = client.post(f"/api/listings/{listing_id}/{route}", headers=stranger)

    assert_refused_by_the_gate(res)
    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "under_offer"


@pytest.mark.parametrize("route", ROUTES)
def test_s4_the_counterparty_buyer_cannot_close_or_unwind_the_deal(
    client, auth_headers, under_offer_listing, route
):
    """S4 — being party to the deal grants no rights over the seller's listing."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    res = client.post(f"/api/listings/{listing_id}/{route}", headers=buyer)

    assert_refused_by_the_gate(res)
    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "under_offer"


@pytest.mark.parametrize("route", ROUTES)
def test_s5_admin_does_not_widen_this_boundary(
    client, auth_headers, admin_headers, under_offer_listing, route
):
    """S5 — `is_admin` grants nothing here.

    Asserted explicitly because M10 established the *opposite* precedent on a
    different gate (`get_owned_or_admin_verification_document`, where admin
    widens by design). Curation is the admin's; closing a deal is the seller's,
    and an unstated rule is the one that drifts.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    res = client.post(f"/api/listings/{listing_id}/{route}", headers=admin_headers())

    assert_refused_by_the_gate(res)
    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "under_offer"


@pytest.mark.parametrize("route", ROUTES)
def test_s6_a_missing_listing_is_indistinguishable_from_someone_elses(
    client, auth_headers, under_offer_listing, route
):
    """S6 — no enumeration: the two refusals are byte-identical."""
    seller, buyer = _seller_and_buyer(auth_headers)
    stranger = auth_headers(email="stranger@example.com", role="seller")
    listing_id, _ = under_offer_listing(seller, buyer)

    someone_elses = client.post(f"/api/listings/{listing_id}/{route}", headers=stranger)
    nonexistent = client.post(f"/api/listings/999999/{route}", headers=stranger)

    assert someone_elses.status_code == nonexistent.status_code == 404
    assert someone_elses.json()["detail"] == nonexistent.json()["detail"]
    assert someone_elses.json()["code"] == nonexistent.json()["code"]


@pytest.mark.parametrize("route", ROUTES)
def test_s7_unauthenticated_and_tampered_tokens_are_401(
    client, auth_headers, under_offer_listing, route
):
    """S7 — no token and a tampered token both 401 (§6 token attacks)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    anonymous = client.post(f"/api/listings/{listing_id}/{route}")
    tampered = client.post(
        f"/api/listings/{listing_id}/{route}",
        headers={"Authorization": seller["Authorization"] + "x"},
    )

    assert anonymous.status_code == 401, anonymous.text
    assert tampered.status_code == 401, tampered.text


# ── The NDA gate is not weakened by a terminal state ─────────────────────────


def test_s8_the_nda_gate_still_guards_a_sold_listings_private_data(
    client, auth_headers, under_offer_listing, request_access, granted_access
):
    """S8 — approved 200, signed-but-unapproved 403, revoked 403 — on a `sold` row.

    The gate is the access request, not the listing's status (spec 005 D9;
    `testing_guide.md` §5 M12). This is the assertion `permissions.py`'s own
    docstring promised would still hold "when M12 marks a listing sold."
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    outsider = auth_headers(email="outsider@example.com", role="buyer")
    listing_id, _ = under_offer_listing(seller, buyer)
    request_access(listing_id, outsider)            # signs the NDA, never approved
    revoked_buyer = auth_headers(email="revoked@example.com", role="buyer")
    revoked_id = granted_access(listing_id, revoked_buyer, seller)
    client.post(f"/api/access-requests/{revoked_id}/revoke", headers=seller)

    assert client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller).status_code == 200

    assert client.get(f"/api/listings/{listing_id}/private", headers=buyer).status_code == 200
    assert client.get(f"/api/listings/{listing_id}/private", headers=outsider).status_code == 403
    assert client.get(
        f"/api/listings/{listing_id}/private", headers=revoked_buyer
    ).status_code == 403


def test_s9_document_downloads_are_unchanged_on_a_sold_listing(
    client, auth_headers, live_listing, under_offer_listing, request_access
):
    """S9 — approved buyer downloads (200); a stranger does not (403)."""
    from tests.conftest import VALID_PDF

    seller, buyer = _seller_and_buyer(auth_headers)
    outsider = auth_headers(email="outsider@example.com", role="buyer")
    listing_id = live_listing(seller)
    doc = client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": ("pl.pdf", VALID_PDF, "application/pdf")},
        headers=seller,
    )
    assert doc.status_code == 201, doc.text
    doc_id = doc.json()["id"]
    under_offer_listing(seller, buyer, listing_id=listing_id)
    request_access(listing_id, outsider)
    # The precondition is the whole test: without it this asserts M5's gate on
    # an `under_offer` listing, which was already true and passes with no M12
    # code at all (found in the red-set check).
    assert client.post(
        f"/api/listings/{listing_id}/mark-sold", headers=seller
    ).status_code == 200
    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "sold"

    assert client.get(
        f"/api/listings/{listing_id}/documents/{doc_id}", headers=buyer
    ).status_code == 200
    assert client.get(
        f"/api/listings/{listing_id}/documents/{doc_id}", headers=outsider
    ).status_code == 403


def test_s10_a_sold_listing_leaves_the_public_surface_entirely(
    client, auth_headers, under_offer_listing
):
    """S10 — absent from browse, 404 on detail: `sold` is not a new oracle (D10)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)
    # Same trap as S9: an `under_offer` listing is already off the public
    # surface, so without this precondition the test passes before M12 exists.
    assert client.post(
        f"/api/listings/{listing_id}/mark-sold", headers=seller
    ).status_code == 200

    page = client.get("/api/listings").json()

    assert listing_id not in [row["id"] for row in page["items"]]
    assert client.get(f"/api/listings/{listing_id}").status_code == 404


def test_s11_the_public_model_cannot_carry_the_sale(client, auth_headers, live_listing):
    """S11 — asserted against the schema's field set, not one response body.

    Spec 004 S3's pattern: `ListingPublic` is a standalone model precisely so a
    field added to `ListingRead` cannot join it, and this is the assertion that
    keeps the claim true as the owner's view grows.

    **This is the one M12 test that legitimately passes before implementation**
    (the red-set check found ten; the other nine were vacuous and were fixed).
    It is a regression pin, not a vacuous pass: `final_price`/`sold_at` do not
    exist yet, so it holds trivially today — and the moment slice 1 adds them to
    `ListingRead`, it becomes the assertion that stops them reaching the
    anonymous card. Sabotage-check it by adding `final_price` to
    `ListingPublic` and watching it go red (Article 3 §2 — a pin nobody has
    seen fail proves nothing).
    """
    from app.schemas import ListingPublic

    fields = set(ListingPublic.model_fields)
    for leaked in ("final_price", "sold_at", "status", "owner_id"):
        assert leaked not in fields, f"{leaked} must never reach the anonymous card"

    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    body = client.get(f"/api/listings/{listing_id}").json()
    assert "final_price" not in body and "sold_at" not in body


# ── The edit corridor (spec D8) ──────────────────────────────────────────────


def test_s12_editing_is_refused_while_under_offer(
    client, auth_headers, under_offer_listing
):
    """S12 ⚠ — the door. A listing under offer has a counterparty relying on its
    terms; the terms hold until the deal resolves."""
    from tests.conftest import VALID_LISTING

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    res = client.put(
        f"/api/listings/{listing_id}",
        json={**VALID_LISTING, "headline": "Rewritten mid-deal", "ttm_profit": "999999.00"},
        headers=seller,
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "listing_under_offer"
    after = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
    assert after["headline"] == VALID_LISTING["headline"]
    assert Decimal(after["ttm_profit"]) == Decimal(VALID_LISTING["ttm_profit"])


def test_s13_edit_then_relist_cannot_republish_unreviewed_content(
    client, auth_headers, under_offer_listing
):
    """S13 ⚠ — the corridor, end to end.

    A reachability test over the *sequence* `edit → relist → public read`,
    asserting the invariant rather than the endpoint (Article 3 §2, 2026-07-19):
    what an anonymous visitor sees after a re-list is what an admin approved.
    Each door here had a test; the corridor between them had none, because no
    single milestone owned it.
    """
    from tests.conftest import VALID_LISTING

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)
    approved_card = client.get(f"/api/listings/{listing_id}")
    assert approved_card.status_code == 404, "sanity: under_offer is off the public surface"

    client.put(
        f"/api/listings/{listing_id}",
        json={**VALID_LISTING, "headline": "Bait and switch", "ttm_profit": "999999.00"},
        headers=seller,
    )
    client.post(f"/api/listings/{listing_id}/relist", headers=seller)

    public = client.get(f"/api/listings/{listing_id}")
    assert public.status_code == 200, public.text
    assert public.json()["headline"] == VALID_LISTING["headline"]
    assert Decimal(public.json()["ttm_profit"]) == Decimal(VALID_LISTING["ttm_profit"])


@pytest.mark.parametrize(
    "method,path",
    [
        ("put", ""),
        ("post", "/submit"),
        ("post", "/pause"),
        ("post", "/resume"),
        ("post", "/close"),
        # Added 2026-07-29 after the independent appsec pass: this route had no
        # status check, so "a sold listing is frozen" was false of the data room
        # — the one part of a listing a buyer actually relies on. A parametrize
        # that stops at the routes you happened to think of is how a claim like
        # this ends up narrower than its own title.
        ("post", "/documents"),
    ],
)
def test_s14_a_sold_listing_is_frozen(
    client, auth_headers, under_offer_listing, method, path
):
    """S14 — `_EDIT_LOCKED`'s `sold` entry, written at M2, finally reachable."""
    from tests.conftest import VALID_LISTING, VALID_PDF

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)
    client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    if method == "put":
        kwargs = {"json": VALID_LISTING}
    elif path == "/documents":
        kwargs = {"files": {"file": ("late.pdf", VALID_PDF, "application/pdf")}}
    else:
        kwargs = {}
    res = getattr(client, method)(f"/api/listings/{listing_id}{path}", headers=seller, **kwargs)

    assert res.status_code == 409, f"{method.upper()} {path or '/'}: {res.text}"
    assert client.get(f"/api/my/listings/{listing_id}", headers=seller).json()[
        "status"
    ] == "sold"


def test_s16_uploads_stay_open_while_a_deal_is_under_offer(
    client, auth_headers, live_listing, under_offer_listing
):
    """S16 — the deliberate narrowing of S14's guard, asserted (appsec, 2026-07-29).

    `update_listing` refuses `under_offer`; this route does not, because due
    diligence is exactly when a buyer asks for more documents. That asymmetry
    looks like an inconsistency to anyone reading the two guards side by side,
    and the obvious "tidy-up" is to add `under_offer` here — which would break
    the workflow the data room exists for, mid-deal, with nothing objecting.
    The decision lived only in a comment until this test; a decision no test
    defends is a decision the next reader gets to overturn by accident.
    """
    from tests.conftest import VALID_PDF

    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    under_offer_listing(seller, buyer, listing_id=listing_id)

    res = client.post(
        f"/api/listings/{listing_id}/documents",
        files={"file": ("diligence-request.pdf", VALID_PDF, "application/pdf")},
        headers=seller,
    )

    assert res.status_code == 201, res.text


def test_s15_an_internal_failure_returns_the_generic_contract(
    client, auth_headers, under_offer_listing, monkeypatch, session
):
    """S15 — no stack, no SQL, no column names; the sale does not half-happen.

    The failure is injected *after* both compare-and-swaps and *before* the
    commit — the worst moment, and the only one where a partial close could
    escape. Production's `get_session()` yields inside `with Session(engine)`,
    so an exception unwinding through it closes the session and discards the
    uncommitted work; the shared test session has no such context manager, so
    the rollback below stands in for it explicitly. What is being asserted is
    that nothing was **committed**, which is the property that matters.
    """
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id, _ = under_offer_listing(seller, buyer)

    from app.routers import listings as listings_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure in listing.final_price write")

    monkeypatch.setattr(listings_module, "notify_deal", _boom)

    res = client.post(f"/api/listings/{listing_id}/mark-sold", headers=seller)

    assert res.status_code == 500, res.text
    assert res.json()["detail"] == "Something went wrong on our end."
    blob = res.text.lower()
    for leak in ("traceback", "sqlalchemy", "final_price", "listing", 'file "', ".py"):
        assert leak not in blob

    session.rollback()
    body = client.get(f"/api/my/listings/{listing_id}", headers=seller).json()
    assert body["status"] == "under_offer"
    assert body["final_price"] is None and body["sold_at"] is None
