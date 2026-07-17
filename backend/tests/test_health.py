"""Health probe — the one M0 test that survives M1.

The M0 sandbox tests (write→read DB proof, fresh-DB isolation) were deleted with
the sandbox at M1 slice 11 — the DB path and fixture isolation are now proven by
the auth tests. `test_sandbox_removed.py` asserts the endpoints are gone.
"""


def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
