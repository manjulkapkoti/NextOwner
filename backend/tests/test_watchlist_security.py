"""M9 — the caller-scoping boundary (S), the 404-shaped core criteria (W), and
the failure contract (X), spec 009.

Written failing first. M9 is not on the security-critical list, but it adds a
new caller-owned table and three new routes, and the whole of `security.md` §7's
M9 line is *"every operation caller-scoped; a user only ever sees/edits their
own items."* That sentence has exactly two failure modes worth a test file:

1. **The read leaks sideways** — A's favorites show up in B's list (S1), or the
   response model carries a listing field the public boundary excludes (W11).
2. **The write reaches sideways** — B's `DELETE` deletes A's row (S2), or a
   `POST` body names a `user_id` the server honors (S4).

Everything else here is the existence-oracle discipline D2/D3 inherit verbatim
from `get_public_listing`: missing, never-published, and no-longer-`live` must
all answer identically (W5, W6, W9, W10, W13), so this router can never be used
to probe for a listing the caller could not have browsed to in the first place.

**Every 404 assertion also asserts the machine `code`.** An unmounted route
404s too — with Starlette's bare `{"detail": "Not Found"}` — so a status-only
assertion would pass vacuously right now and never have a red phase (the trap
named in `test_offers.py::test_a5` and `test_nda_gate.py::test_d8`).
"""

from __future__ import annotations

import pytest

# The full field set of `WatchlistEntryRead` (plan 009 § Response models). Kept
# as an allow-list rather than a deny-list: a deny-list only catches the leaks we
# thought of, while `set(row) <= ALLOWED` fails on any field a future edit adds.
ALLOWED_ENTRY_FIELDS = {
    "listing_id",
    "added_at",
    "type",
    "headline",
    "description",
    "asking_price",
    "ttm_revenue",
    "ttm_profit",
    "mrr",
    "churn_pct",
    "customers",
    "published_at",
}

# Absent by construction, the same list `ListingPublic` excludes (spec 009 W11).
FORBIDDEN_ENTRY_FIELDS = {
    "owner_id",
    "status",
    "company_name",
    "website_url",
    "detailed_financials",
}


def _seller_and_buyer(auth_headers):
    return (
        auth_headers(email="seller@example.com", role="seller"),
        auth_headers(email="buyer@example.com", role="buyer"),
    )


def _watchlisted_ids(client, headers) -> list[int]:
    """`GET /api/watchlist` as a plain list of listing ids.

    Asserts the 200 first so a test reads a failure as "the route isn't there /
    isn't caller-scoped" rather than a `TypeError` from indexing an error body.
    """
    res = client.get("/api/watchlist", headers=headers)
    assert res.status_code == 200, res.text
    rows = res.json()
    assert isinstance(rows, list), res.text
    return [row["listing_id"] for row in rows]


# ── S — security & abuse ─────────────────────────────────────────────────────


def test_s1_one_users_watchlist_never_appears_in_anothers(
    client, auth_headers, live_listing
):
    """S1 — the read is caller-scoped: A's favorite is invisible to B.

    The weakest plausible implementation of `GET /watchlist` is a join to
    `Listing` that forgets the `user_id == caller` predicate — it would still
    pass every single-user test in `test_watchlist.py`, because with one user
    "all rows" and "my rows" are the same set. Two users is the smallest world
    in which that bug is visible at all.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    user_a = auth_headers(email="a@example.com", role="buyer")
    user_b = auth_headers(email="b@example.com", role="buyer")
    listing_id = live_listing(seller)

    added = client.post(f"/api/watchlist/{listing_id}", headers=user_a)
    assert added.status_code == 201, added.text

    assert _watchlisted_ids(client, user_a) == [listing_id]
    assert _watchlisted_ids(client, user_b) == []


def test_s2_deleting_your_own_entry_does_not_delete_another_users(
    client, auth_headers, live_listing
):
    """S2 — the delete is keyed on `(caller, listing)`, not on `listing` alone.

    Both users hold an entry for the same listing, so a `DELETE` written as
    `where(WatchlistEntry.listing_id == listing_id)` — dropping the caller
    predicate — succeeds, returns the same 204, and silently clears a stranger's
    shortlist. Nothing in the response would distinguish it; only the other
    account's own read can. That is what this asserts.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    user_a = auth_headers(email="a@example.com", role="buyer")
    user_b = auth_headers(email="b@example.com", role="buyer")
    listing_id = live_listing(seller)
    assert client.post(f"/api/watchlist/{listing_id}", headers=user_a).status_code == 201
    assert client.post(f"/api/watchlist/{listing_id}", headers=user_b).status_code == 201

    removed = client.delete(f"/api/watchlist/{listing_id}", headers=user_b)

    assert removed.status_code == 204, removed.text
    assert _watchlisted_ids(client, user_a) == [listing_id]
    assert _watchlisted_ids(client, user_b) == []


def test_s3_all_three_watchlist_routes_require_authentication(
    client, auth_headers, live_listing
):
    """S3 — default-deny on every route in the router, not just the writes.

    Uses a genuinely `live` listing so a 401 cannot be an accident of the
    listing being absent: the auth dependency has to be what refuses, before any
    lookup runs. The `GET` is included deliberately — a read-only route is the
    one most likely to be mounted without a `get_current_user` dependency, and
    it is the route that returns another person's shortlist.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = live_listing(seller)

    responses = {
        "POST": client.post(f"/api/watchlist/{listing_id}"),
        "GET": client.get("/api/watchlist"),
        "DELETE": client.delete(f"/api/watchlist/{listing_id}"),
    }

    assert {name: r.status_code for name, r in responses.items()} == {
        "POST": 401,
        "GET": 401,
        "DELETE": 401,
    }


def test_s4_the_stored_user_id_comes_from_the_jwt_not_the_request(
    client, session, auth_headers, live_listing, user_id
):
    """S4 — `user_id` mass-assignment has no field to be assigned from.

    Spec S4 claims the strongest form of the `security.md` §2 control: the route
    takes **no** request body, so the ownership field isn't merely stripped, it
    is unreachable. Asserting "the row is mine" alone would not prove that — it
    is also true of a route that reads a body and happens to overwrite the field
    afterwards. So this sends a body that names a *victim's* id and asserts
    three things: the call still succeeds (the body is ignored, not 422'd on an
    unknown field), the stored `user_id` is the caller's, and the victim's own
    watchlist stays empty.

    The stored row is read straight from the table because the response model
    has no `user_id` field to inspect (plan 009 § Response models) — a leak the
    schema hides is exactly what a raw read is for.
    """
    from sqlalchemy import text

    seller = auth_headers(email="seller@example.com", role="seller")
    attacker = auth_headers(email="attacker@example.com", role="buyer")
    victim = auth_headers(email="victim@example.com", role="buyer")
    listing_id = live_listing(seller)
    attacker_id, victim_id = user_id(attacker), user_id(victim)

    added = client.post(
        f"/api/watchlist/{listing_id}",
        json={"user_id": victim_id, "listing_id": 999999},
        headers=attacker,
    )

    assert added.status_code == 201, added.text
    owners = [
        r[0]
        for r in session.execute(
            text("SELECT user_id FROM watchlistentry WHERE listing_id = :i"),
            {"i": listing_id},
        ).fetchall()
    ]
    assert owners == [attacker_id]
    assert _watchlisted_ids(client, victim) == []


# ── W — the caller-scoping / existence-oracle half of the core criteria ──────


def test_w5_adding_a_listing_that_does_not_exist_is_404(client, auth_headers):
    """W5 — D2: you cannot favorite what does not exist."""
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    res = client.post("/api/watchlist/987654", headers=buyer)

    assert res.status_code == 404
    assert res.json().get("code") == "not_found"


@pytest.mark.parametrize(
    "status", ["draft", "pending_review", "paused", "closed", "rejected", "under_offer"]
)
def test_w6_adding_a_non_live_listing_is_404(
    client, auth_headers, live_listing, force_status, status
):
    """W6 — D2: every non-`live` status answers exactly like a missing listing.

    Mirrors `test_offers.py::test_a3`'s setup: publish for real first (so
    `published_at` is set the way the product sets it), then force each of the
    six non-`live` values, isolating the status guard from whichever real
    transition would normally produce that status. The point is not that any one
    of these is unreachable — it is that a buyer who can only see `live`
    listings must not be able to use this route to learn that a `draft`,
    `rejected`, or `under_offer` listing exists behind a given id.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    force_status(listing_id, status)

    res = client.post(f"/api/watchlist/{listing_id}", headers=buyer)

    assert res.status_code == 404
    assert res.json().get("code") == "not_found"


def test_w9_deleting_an_entry_you_never_added_is_404(
    client, auth_headers, live_listing
):
    """W9 — the listing is real and `live`, but the *entry* is not the caller's.

    This is the `get_owned_watchlist_entry` boundary (plan 009 D5): the row is
    looked up by the pair `(caller, listing)`, so "never added it" and "someone
    else added it" are the same miss.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)

    res = client.delete(f"/api/watchlist/{listing_id}", headers=buyer)

    assert res.status_code == 404
    assert res.json().get("code") == "not_found"


def test_w10_delete_is_not_an_existence_oracle(client, auth_headers, live_listing):
    """W10 — "never watchlisted" and "no such listing" must be indistinguishable.

    Asserts the two responses are byte-identical rather than merely both-404:
    the 4xx contract is `{"detail", "code"}` with no request id (`main.py`'s
    `app_error_handler`), so a differing `detail` string — the natural result of
    someone "helpfully" raising `NotFound("Listing not found")` on one path and
    `NotFound("Watchlist entry not found")` on the other — is a working oracle
    for whether a listing id is in use, and this comparison catches it.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    live_id = live_listing(seller)

    never_added = client.delete(f"/api/watchlist/{live_id}", headers=buyer)
    does_not_exist = client.delete("/api/watchlist/987654", headers=buyer)

    assert never_added.status_code == 404
    assert never_added.json().get("code") == "not_found"
    assert (never_added.status_code, never_added.json()) == (
        does_not_exist.status_code,
        does_not_exist.json(),
    )


def test_w11_the_watchlist_schema_leaks_no_private_or_identity_fields(
    client, auth_headers, live_listing
):
    """W11 — schema-leak, in `ListingPublic`'s absent-field-set tradition.

    `WatchlistEntryRead` is a *standalone* model by design (plan 009 § Response
    models) — the whole point of not inheriting from `ListingRead` is that a
    private field added there can never ride along into here. An allow-list
    assertion is what makes that design decision enforceable rather than
    aspirational, so this checks the key set is a subset of the declared model
    **and** that the seller's actual private values appear nowhere in the raw
    response text (a field renamed on the way out would still be a leak).
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    buyer = auth_headers(email="buyer@example.com", role="buyer")
    listing_id = live_listing(seller)
    assert client.post(f"/api/watchlist/{listing_id}", headers=buyer).status_code == 201

    res = client.get("/api/watchlist", headers=buyer)

    assert res.status_code == 200, res.text
    rows = res.json()
    assert isinstance(rows, list) and rows, res.text
    for row in rows:
        leaked = set(row) & FORBIDDEN_ENTRY_FIELDS
        assert not leaked, f"private/identity field(s) exposed: {leaked}"
        assert set(row) <= ALLOWED_ENTRY_FIELDS, (
            f"undeclared field(s): {set(row) - ALLOWED_ENTRY_FIELDS}"
        )
    assert "Acme Internal Tools LLC" not in res.text
    assert "acme.example.com" not in res.text
    assert "see attached" not in res.text


def test_w13_a_seller_cannot_watchlist_their_own_pending_listing(
    client, auth_headers, make_listing
):
    """W13 — D2 applies to the owner too ("not even the person who wrote it").

    The owner *can* see this listing elsewhere (`GET /api/my/listings/{id}`), so
    the tempting shortcut is to special-case them here. That would make this
    route the one place where a response varies by who is asking about a
    not-yet-public listing — reintroducing the oracle W5/W6/W10 close, from the
    inside.
    """
    seller = auth_headers(email="seller@example.com", role="seller")
    listing_id = make_listing(seller).json()["id"]
    assert client.post(f"/api/listings/{listing_id}/submit", headers=seller).status_code == 200

    res = client.post(f"/api/watchlist/{listing_id}", headers=seller)

    assert res.status_code == 404
    assert res.json().get("code") == "not_found"


# ── X — errors & failure modes ───────────────────────────────────────────────


def test_x1_a_non_numeric_listing_id_is_422(client, auth_headers):
    """X1 — the path parameter is the router's entire input surface.

    With no request body anywhere in this router (plan 009 § Endpoints), the
    typed path parameter is the only thing left to validate — so it has to
    actually validate, on both routes that take one, rather than falling through
    to a lookup that stringly-compares and 404s.
    """
    buyer = auth_headers(email="buyer@example.com", role="buyer")

    added = client.post("/api/watchlist/not-a-number", headers=buyer)
    removed = client.delete("/api/watchlist/not-a-number", headers=buyer)

    assert added.status_code == 422, added.text
    assert removed.status_code == 422, removed.text


def test_x2_an_internal_error_returns_the_generic_contract(
    client, auth_headers, session
):
    """X2 — a 500 on a watchlist route leaks no stack, SQL, or file path.

    Same injection point as `test_alerts_security.py::test_x2`: the fault is
    raised at the session boundary, so the catch-all handler is reached through
    a real route rather than the `/_debug/boom` stub. `GET /api/watchlist` is
    the route chosen because its query is a join across two tables — the one
    place in this router where a leaked exception string would carry a `SELECT`
    naming another user's column.
    """
    from app.db import get_session
    from app.main import app

    buyer = auth_headers(email="buyer@example.com", role="buyer")

    class BrokenSession:
        def __getattr__(self, name):
            if name == "exec":
                raise RuntimeError("injected failure")
            return getattr(session, name)

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    try:
        res = client.get("/api/watchlist", headers=buyer)
    finally:
        app.dependency_overrides[get_session] = lambda: session

    assert res.status_code == 500
    body = res.json()
    assert "request_id" in body
    assert "Traceback" not in str(body)
    assert "SELECT" not in str(body).upper()
    assert "watchlistentry" not in str(body).lower()
