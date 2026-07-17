"""M1 — Cleanup (spec 001 acceptance criterion I1).

The throwaway M0 sandbox — an unauthenticated write path — must be gone before
real data lands. Slice 11 deletes the endpoints, the model, and the two M0
sandbox tests in test_health.py (the DB-pipeline proof is now the auth tests).
"""


def test_i1_sandbox_write_endpoint_is_gone(client):
    assert client.post("/api/sandbox", json={"note": "x"}).status_code == 404


def test_i1_sandbox_read_endpoint_is_gone(client):
    assert client.get("/api/sandbox").status_code == 404
