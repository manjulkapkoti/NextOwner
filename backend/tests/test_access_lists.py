"""M5 — The buyer's and seller's access-request lists, and the schema/leak
guards around them (spec 005 acceptance criteria F1-F3, G1-G3, S3, S4, X3).

F is the buyer's own view (`GET /api/my/access-requests`) — caller-scoped, no
listing_id filter needed since it is always "mine".

G is the seller's queue (`GET /api/my/listings/{id}/access-requests`, spec D7)
— guarded by the *existing* `get_owned_listing`, so a non-owner gets 404, not
403 (spec 002's existence rule, inherited rather than re-decided). It carries
the buyer's profile and deliberately nothing else: no email (G3, PII
minimization) and no verification flag (D5 — that field is M10's to add).

S3/S4 assert the schema boundary directly, the way test_browse.py's S3 does —
a field added to a model in a later milestone is caught here even if no route
test happens to exercise it.

X3 proves a crash inside the gate still returns the generic error contract
(error_handling.md §7) — mirrors test_browse.py's browse-path E2 and
test_error_contract.py's 500-contract assertions, applied to the gate itself.
"""

from decimal import Decimal


def _flatten_keys(obj: object) -> set[str]:
    """All dict keys anywhere in a (possibly nested) JSON-decoded response —
    proves a forbidden field is absent everywhere, not just at the top level
    (G1, G3)."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _flatten_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item)
    return keys


def _collect_field_names(model, _seen: set | None = None) -> set[str]:
    """Recursively collect field names from a Pydantic/SQLModel model,
    including nested models reachable through Optional[...]/list[...]
    wrappers — so a nested "buyer profile" submodel is checked too, not just
    the top-level response model (S3)."""
    from typing import get_args, get_origin

    from pydantic import BaseModel

    seen = _seen if _seen is not None else set()
    if model in seen:
        return set()
    seen.add(model)

    names: set[str] = set()
    for field_name, field in model.model_fields.items():
        names.add(field_name)
        stack = [field.annotation]
        while stack:
            ann = stack.pop()
            origin = get_origin(ann)
            if origin is not None:
                stack.extend(get_args(ann))
            elif isinstance(ann, type) and issubclass(ann, BaseModel) and ann is not model:
                names |= _collect_field_names(ann, seen)
    return names


# ── F — the buyer's own requests ─────────────────────────────────────────────

def test_f1_returns_the_buyers_own_requests_across_listings(
    client, auth_headers, live_listing, request_access
):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_a = live_listing(seller, headline="Listing A")
    listing_b = live_listing(seller, headline="Listing B")
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    request_access(listing_a, buyer)
    request_access(listing_b, buyer, sign=False)   # already signed above

    r = client.get("/api/my/access-requests", headers=buyer)
    assert r.status_code == 200
    got = {row["listing_id"]: row["status"] for row in r.json()}
    assert got == {listing_a: "requested", listing_b: "requested"}


def test_f2_never_shows_another_buyers_requests(
    client, auth_headers, live_listing, request_access
):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    other_listing = live_listing(seller, headline="Other listing")
    buyer_a = auth_headers(email="buyer-a@example.com", role="buyer")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")

    request_access(listing_id, buyer_a)
    request_access(other_listing, buyer_b)

    seen_by_a = {
        row["listing_id"] for row in client.get("/api/my/access-requests", headers=buyer_a).json()
    }
    assert other_listing not in seen_by_a


def test_f3_unauthenticated_is_401(client):
    assert client.get("/api/my/access-requests").status_code == 401


# ── G — the seller's queue ───────────────────────────────────────────────────

def test_g1_queue_returns_requests_with_buyer_profile_and_no_verification_field(
    client, auth_headers, live_listing, request_access
):
    """Spec D5: FR-14's profile half only — no verification placeholder until
    M10 owns it."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    buyer_a = auth_headers(email="buyer-a@example.com", role="buyer")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")
    profile = client.put(
        "/api/profile",
        json={
            "display_name": "Buyer A",
            "budget": "250000",
            "target_industries": "SaaS",
            "experience": "1 prior acquisition",
        },
        headers=buyer_a,
    )
    assert profile.status_code == 200
    request_access(listing_id, buyer_a)
    request_access(listing_id, buyer_b)

    r = client.get(f"/api/my/listings/{listing_id}/access-requests", headers=seller)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2

    row_a = next(row for row in rows if row["buyer"]["display_name"] == "Buyer A")
    assert Decimal(str(row_a["buyer"]["budget"])) == Decimal("250000")
    assert row_a["buyer"]["target_industries"] == "SaaS"
    assert row_a["buyer"]["experience"] == "1 prior acquisition"

    keys = _flatten_keys(rows)
    assert not any("verif" in k.lower() for k in keys), "no verification field until M10 (D5)"


def test_g2_a_non_owner_gets_404_not_403(client, auth_headers, live_listing):
    """Spec D7: guarded by the existing get_owned_listing, so "not yours" and
    "doesn't exist" stay indistinguishable.

    Confirms the route serves its real owner first — a route that doesn't
    exist yet also 404s on the attacker's request, which would pass this test
    for the wrong reason (mirrors test_my_listing_detail.py's D2)."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    attacker = auth_headers(email="attacker@example.com", role="buyer")

    assert client.get(f"/api/my/listings/{listing_id}/access-requests", headers=seller).status_code == 200

    res = client.get(f"/api/my/listings/{listing_id}/access-requests", headers=attacker)
    assert res.status_code == 404, "403 would confirm the listing exists"


def test_g3_queue_never_carries_the_buyers_email(
    client, auth_headers, live_listing, request_access
):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    buyer = auth_headers(email="secretbuyer@example.com", role="buyer")
    request_access(listing_id, buyer)

    r = client.get(f"/api/my/listings/{listing_id}/access-requests", headers=seller)
    assert r.status_code == 200
    assert "secretbuyer@example.com" not in r.text
    assert "email" not in _flatten_keys(r.json())


# ── Security & abuse — schema leaks ──────────────────────────────────────────

def test_s3_access_request_schemas_exclude_email_and_password_hash_by_construction(client):
    """Assert the control, not one of its outputs — a field added to either
    model in a later milestone is caught here even if no route test covers it
    (mirrors test_browse.py's S3)."""
    from app.schemas import AccessRequestRead, AccessRequestWithBuyer

    for model in (AccessRequestRead, AccessRequestWithBuyer):
        fields = _collect_field_names(model)
        assert "email" not in fields, f"{model.__name__} declares an email field"
        assert "password_hash" not in fields, f"{model.__name__} declares password_hash"


def test_s4_public_listing_schema_still_excludes_private_and_identity_fields(
    client, auth_headers, live_listing
):
    """M5 must not widen M4's public boundary. Checked against the model
    classes directly, then against a real response carrying values that would
    leak if the boundary had moved."""
    from app.schemas import ListingPrivateRead, ListingPublic

    forbidden = set(ListingPrivateRead.model_fields) | {"owner_id", "status"}
    assert forbidden.isdisjoint(set(ListingPublic.model_fields))

    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(
        seller, company_name="SecretCo", website_url="https://secret.example.com"
    )
    res = client.get(f"/api/listings/{listing_id}")
    assert res.status_code == 200
    for leak in (
        "SecretCo", "secret.example.com", "company_name", "website_url",
        "detailed_financials", "owner_id",
    ):
        assert leak not in res.text


# ── Errors & failure modes ───────────────────────────────────────────────────

def test_x3_a_failure_inside_the_gate_returns_the_generic_contract(
    client, auth_headers, live_listing, granted_access, monkeypatch, session
):
    """A crash while resolving require_private_access must not leak the query,
    the schema, or a stack trace (spec X3; error_handling.md §7)."""
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller, company_name="SecretCo")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    granted_access(listing_id, buyer, seller)

    def boom(*args, **kwargs):
        raise RuntimeError("SELECT * FROM accessrequest WHERE listing_id = ...")

    monkeypatch.setattr(session, "exec", boom)
    res = client.get(f"/api/listings/{listing_id}/private", headers=buyer)
    assert res.status_code == 500
    assert res.json()["detail"] == "Something went wrong on our end."
    assert "request_id" in res.json()
    blob = res.text.lower()
    for leak in ("secretco", "select", "accessrequest", "traceback", "sqlalchemy", ".py"):
        assert leak not in blob
