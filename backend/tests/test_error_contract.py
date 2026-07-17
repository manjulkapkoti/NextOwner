"""M1 — The error contract (spec 001 acceptance criteria G1–G3).

The foundation error_handling.md §7 mandates lands at M1: a 500 never leaks, 4xx
carry a machine `code`, and a request id ties a response to its log line.
"""


def test_g1_unhandled_error_returns_generic_500_with_no_internals(client):
    """A route that blows up returns the generic contract — no stack, SQL, or paths."""
    r = client.get("/api/_debug/boom")           # test-only route that raises (removed if absent → 404 also fails this)
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Something went wrong on our end."
    assert "request_id" in body
    blob = r.text.lower()
    for leak in ("traceback", "sqlalchemy", 'file "', "line ", ".py"):
        assert leak not in blob


def test_g2_business_errors_carry_a_machine_code(client):
    client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "correct horse battery staple", "role": "buyer"},
    )
    dup = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "correct horse battery staple", "role": "buyer"},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "email_taken"     # stable slug alongside `detail`


def test_g3_request_id_is_echoed_and_correlatable(client):
    r = client.get("/api/_debug/boom", headers={"X-Request-ID": "req_test_123"})
    assert r.status_code == 500
    assert r.json()["request_id"] == "req_test_123"   # the caller's id is propagated
