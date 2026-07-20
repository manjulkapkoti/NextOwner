"""M5 branch review — default-deny holds for *every* route, not just new ones.

Constitution Article 2 #1 and `security.md` §8 require that no non-public route
ships without an explicit permission check. Every milestone has honoured that,
and every milestone has verified it the same way: by a human remembering to look.

This asks the question mechanically instead. It enumerates the app's real route
table from the OpenAPI schema, calls each one **with no Authorization header**,
and asserts that nothing outside an explicit public allowlist answers 200.

Why this shape rather than introspecting dependencies: a route can be gated in
several structurally different ways (a `Depends` in the signature, a router-level
dependency, a check inside the body), and a structural audit that misses one
reports a false clean. Behaviour is the property that actually matters, and it
has exactly one answer per route.

Added during M5's branch review, after walking §8's matrix by hand found two
route families whose 401 behaviour was correct but unasserted (spec 005 C12/G4).
The gap was not that a rule was broken — it was that *nothing would have noticed*
if it were. This is the generalization of that fix: it covers routes nobody has
written yet, which is the only way a floor stays a floor.
"""

import re

# Routes that are public *by design*, each with the reason it is safe.
#   - health: no data (M0)
#   - browse + public detail: the anonymous half of the trust gate (M4, FR-6),
#     served through `ListingPublic`, which cannot carry identity fields
#   - register/login: the doors by which a caller *becomes* authenticated
PUBLIC_BY_DESIGN = {
    ("GET", "/api/health"),
    ("GET", "/api/listings"),
    ("GET", "/api/listings/{listing_id}"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
}

# Mounted only when ENABLE_DEBUG_ROUTES is set (conftest sets it so the 500
# contract can be tested). Never mounted in production — see app/main.py.
_DEBUG_PREFIX = "/api/_debug"


def _routes(client):
    spec = client.app.openapi()
    return [
        (method.upper(), path)
        for path, ops in spec["paths"].items()
        for method in ops
        if method.upper() not in {"HEAD", "OPTIONS"} and not path.startswith(_DEBUG_PREFIX)
    ]


def test_no_route_serves_data_without_a_token(client):
    """No route outside the allowlist answers 200 to an anonymous caller."""
    routes = _routes(client)

    # Guards against the check silently examining nothing — the failure mode
    # that makes a green result meaningless (and one this milestone hit for
    # real while writing an earlier version of this audit).
    assert len(routes) > 10, f"only found {len(routes)} routes — the enumeration is broken"

    leaks = []
    for method, path in routes:
        concrete = re.sub(r"\{[^}]+\}", "1", path)
        res = client.request(method, concrete)          # deliberately no auth header
        if res.status_code == 200 and (method, path) not in PUBLIC_BY_DESIGN:
            leaks.append(f"{method} {path} returned 200 without a token")

    assert not leaks, "routes reachable unauthenticated:\n" + "\n".join(leaks)


def test_the_public_allowlist_matches_reality(client):
    """Every allowlisted route still exists.

    Without this, a renamed or deleted public route would leave a stale entry in
    the allowlist — and a stale allowlist is how a route that *becomes* sensitive
    keeps a pass it no longer deserves.
    """
    live = {(m, p) for m, p in _routes(client)}
    stale = PUBLIC_BY_DESIGN - live
    assert not stale, f"allowlist names routes that no longer exist: {sorted(stale)}"
