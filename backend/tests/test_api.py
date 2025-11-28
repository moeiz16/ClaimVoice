from datetime import datetime


async def test_health_reports_database_and_clock(client):
    res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "x-claimvoice-now" in res.headers
    datetime.fromisoformat(res.headers["x-claimvoice-now"])


async def test_every_response_has_request_id_and_security_headers(client):
    res = await client.get("/health", headers={"X-Request-ID": "test-request-0001"})
    assert res.headers["x-request-id"] == "test-request-0001"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


async def test_unknown_route_is_problem_json(client):
    res = await client.get("/api/v1/nothing-here")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["code"] == "not_found"
    assert res.headers["cache-control"] == "no-store"
