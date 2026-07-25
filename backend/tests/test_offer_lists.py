"""M7 — offers / LOI (spec 007): the two read queues F1-F3, G1-G4, plus the
schema/leak/token guards around them: S2, S4, S7.

F is the buyer's own view (`GET /api/my/offers`) — caller-scoped, mirrors
spec 005's F. G is the seller's per-listing queue (`GET /api/my/listings/{id}
/offers`) — guarded by the *existing* `get_owned_listing`, so a non-owner gets
404, not 403 (spec 002's existence rule, inherited rather than re-decided). It
carries the buyer's profile and deliberately nothing else: no email (G3) and no
verification flag (D5 deferral to M10, same as spec 005's G1).

S2/S4 assert the schema/auth boundary directly, the way `test_access_lists.py`'s
S3/S4 do — a field or a route added later is caught here even if no other test
happens to exercise it. S7 mirrors spec 005's S8 (no-leak-on-denial), applied
to the offer gate.

Scope: creation (A), withdraw (D), X1 live in `test_offers.py`. The decision
machine (B), counter mechanics (C), the sibling sweep (E), and S1/S3/S5/S6/S8/X2
live in `test_offer_decisions.py`.
"""

import datetime
from decimal import Decimal

import jwt

from tests.conftest import TEST_JWT_ALG, TEST_JWT_SECRET, VALID_OFFER


def _seller_and_buyer(auth_headers, seller_email="seller@example.com", buyer_email="buyer@example.com"):
    seller = auth_headers(email=seller_email, role="seller")
    buyer = auth_headers(email=buyer_email, role="buyer")
    return seller, buyer


def _flatten_keys(obj: object) -> set[str]:
    """All dict keys anywhere in a (possibly nested) JSON-decoded response —
    proves a forbidden field is absent everywhere, not just at the top level
    (mirrors `test_access_lists.py`)."""
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
    including nested models (so `OfferWithBuyer`'s nested `BuyerProfile` is
    checked too) — mirrors `test_access_lists.py`."""
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


# ── F — the buyer's own offers ───────────────────────────────────────────────

def test_f1_returns_every_row_across_both_listings(
    client, auth_headers, live_listing, submitted_offer
):
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_a = live_listing(seller, headline="Listing A")
    listing_b = live_listing(seller, headline="Listing B")
    offer_a = submitted_offer(listing_a, buyer, seller)
    offer_b = submitted_offer(listing_b, buyer, seller)

    rows = client.get("/api/my/offers", headers=buyer).json()
    ids = {r["id"] for r in rows}
    assert {offer_a, offer_b} <= ids


def test_f2_never_shows_another_buyers_offers(
    client, auth_headers, live_listing, submitted_offer
):
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer_a = auth_headers(email="buyer-a@example.com", role="buyer")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")
    listing_id = live_listing(seller)
    other_listing = live_listing(seller, headline="Other listing")
    offer_a = submitted_offer(listing_id, buyer_a, seller)
    offer_b = submitted_offer(other_listing, buyer_b, seller)

    rows = client.get("/api/my/offers", headers=buyer_a).json()
    ids = {r["id"] for r in rows}
    assert offer_a in ids
    assert offer_b not in ids


def test_f3_unauthenticated_is_401(client):
    assert client.get("/api/my/offers").status_code == 401


# ── G — the seller's queue ───────────────────────────────────────────────────

def test_g1_queue_returns_both_buyers_threads_with_profile(
    client, auth_headers, live_listing, submitted_offer
):
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer_a = auth_headers(email="buyer-a@example.com", role="buyer")
    buyer_b = auth_headers(email="buyer-b@example.com", role="buyer")
    listing_id = live_listing(seller)
    profile = client.put(
        "/api/profile",
        json={
            "display_name": "Buyer A",
            "budget": "300000",
            "target_industries": "SaaS",
            "experience": "First deal",
        },
        headers=buyer_a,
    )
    assert profile.status_code == 200
    offer_a = submitted_offer(listing_id, buyer_a, seller)
    offer_b = submitted_offer(listing_id, buyer_b, seller)

    r = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller)
    assert r.status_code == 200
    rows = r.json()
    ids = {row["id"] for row in rows}
    assert offer_a in ids and offer_b in ids

    row_a = next(row for row in rows if row["id"] == offer_a)
    assert row_a["buyer"]["display_name"] == "Buyer A"
    assert Decimal(str(row_a["buyer"]["budget"])) == Decimal("300000")
    assert row_a["buyer"]["target_industries"] == "SaaS"

    keys = _flatten_keys(rows)
    assert not any("verif" in k.lower() for k in keys), "no verification field until M10 (D5 deferral)"


def test_g2_a_non_owner_gets_404_not_403(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    attacker = auth_headers(email="attacker@example.com", role="buyer")

    assert client.get(f"/api/my/listings/{listing_id}/offers", headers=seller).status_code == 200
    res = client.get(f"/api/my/listings/{listing_id}/offers", headers=attacker)
    assert res.status_code == 404, "403 would confirm the listing exists"


def test_g3_queue_never_carries_the_buyers_email(
    client, auth_headers, live_listing, submitted_offer
):
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="secretbuyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    submitted_offer(listing_id, buyer, seller)

    r = client.get(f"/api/my/listings/{listing_id}/offers", headers=seller)
    assert r.status_code == 200
    assert "secretbuyer@example.com" not in r.text
    assert "email" not in _flatten_keys(r.json())


def test_g4_unauthenticated_is_401(client, auth_headers, live_listing):
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)
    assert client.get(f"/api/my/listings/{listing_id}/offers").status_code == 401


# ── Security & abuse (this file's slice: S2, S4, S7) ─────────────────────────

def test_s2_offer_schemas_exclude_email_and_password_hash_by_construction(client):
    """Assert the control, not one of its outputs (mirrors spec 005 S3) — a
    field added to either model in a later milestone is caught here even if no
    route test happens to exercise it."""
    from app.schemas import OfferRead, OfferWithBuyer

    for model in (OfferRead, OfferWithBuyer):
        fields = _collect_field_names(model)
        assert "email" not in fields, f"{model.__name__} declares an email field"
        assert "password_hash" not in fields, f"{model.__name__} declares password_hash"


def test_s4_token_attacks_reach_every_offer_route(
    client, auth_headers, live_listing, submitted_offer
):
    """Identity resolves before authorization on every offer surface — a
    broken token must never fall through to a 403/404 (mirrors spec 005 S6)."""
    seller, buyer = _seller_and_buyer(auth_headers)
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    expired = jwt.encode({"sub": "1", "exp": past}, TEST_JWT_SECRET, algorithm=TEST_JWT_ALG)
    tampered = jwt.encode({"sub": "1"}, "attacker-key", algorithm="HS256")

    for token in (expired, tampered):
        bad = {"Authorization": f"Bearer {token}"}
        assert (
            client.post(f"/api/listings/{listing_id}/offers", json=VALID_OFFER, headers=bad).status_code
            == 401
        )
        assert client.post(f"/api/offers/{offer_id}/accept", headers=bad).status_code == 401
        assert client.get("/api/my/offers", headers=bad).status_code == 401
        assert client.get(f"/api/my/listings/{listing_id}/offers", headers=bad).status_code == 401


def test_s7_a_403_from_an_offer_gate_leaks_nothing(
    client, auth_headers, live_listing, submitted_offer
):
    seller_email = "seller@example.com"
    buyer_email = "buyer@example.com"
    seller, buyer = _seller_and_buyer(auth_headers, seller_email=seller_email, buyer_email=buyer_email)
    stranger = auth_headers(email="stranger@example.com", role="buyer")
    listing_id = live_listing(seller)
    offer_id = submitted_offer(listing_id, buyer, seller)

    res = client.post(f"/api/offers/{offer_id}/accept", headers=stranger)
    assert res.status_code == 403

    body = res.json()
    assert "code" in body and "detail" in body       # the generic contract (error_handling.md §1)
    blob = res.text.lower()
    for leak in (seller_email, buyer_email, "select", "traceback", "sqlalchemy", ".py"):
        assert leak not in blob, f"{leak!r} leaked through a 403"
