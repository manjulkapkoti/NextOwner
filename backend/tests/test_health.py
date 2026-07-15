"""Milestone 0 — prove the pipeline end to end.

``/api/health`` proves the endpoint→response path; the sandbox pair proves the
endpoint→session→DB→response path; the isolation test proves the fixtures give
each test a fresh database.
"""


def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_sandbox_write_then_read_proves_db_path(client):
    created = client.post("/api/sandbox", json={"note": "hello"})
    assert created.status_code == 201
    body = created.json()
    assert body["note"] == "hello"
    assert body["id"] is not None
    assert "created_at" in body

    listed = client.get("/api/sandbox")
    assert listed.status_code == 200
    assert "hello" in [row["note"] for row in listed.json()]


def test_fresh_db_per_test_has_no_leftover_rows(client):
    # If fixtures leaked state, the row from the test above would appear here.
    assert client.get("/api/sandbox").json() == []
