"""Cross-cutting API conventions: RFC 7807 errors, X-ClaimVoice-Now, request ids, paging, labels, rate limits."""

from datetime import datetime


async def test_every_kind_of_response_carries_the_demo_clock(anon, sup):
    for res in (
        await anon.get("/api/v1/auth/session"),
        await anon.get("/api/v1/claims"),
        await anon.get("/api/v1/no-such-thing"),
        await sup.get("/api/v1/switchboard"),
        await sup.get("/api/v1/switchboard/stream"),
    ):
        datetime.fromisoformat(res.headers["x-claimvoice-now"])
        assert res.headers["x-request-id"]


async def test_problem_details_shape(anon):
    res = await anon.get("/api/v1/claims")
    body = res.json()
    assert res.status_code == 401
    assert body["type"].endswith("/not_authenticated")
    assert {"type", "title", "status", "code", "requestId"} <= set(body)
    assert res.headers["cache-control"] == "no-store"


async def test_validation_errors_list_fields(sup):
    res = await sup.post("/api/v1/calls/does-not-matter/whisper", {"wrong": 1})
    assert res.status_code in (400, 422)
    assert res.headers["content-type"].startswith("application/problem+json")


async def test_paging_shape_and_page_size_cap(sup):
    body = await sup.j("/api/v1/policies?pageSize=500")
    assert body["pageSize"] == 100
    assert body["total"] >= 190
    assert body["totalPages"] == -(-body["total"] // 100)
    second = await sup.j("/api/v1/policies?page=2&pageSize=100")
    assert {p["id"] for p in body["items"]}.isdisjoint({p["id"] for p in second["items"]})


async def test_policies_are_ordered_by_number_and_filterable(sup):
    body = await sup.j("/api/v1/policies?pageSize=100&region=US-CO&line=auto")
    numbers = [p["policyNumber"] for p in body["items"]]
    assert numbers == sorted(numbers)
    assert all(p["region"] == "US-CO" and p["lineLabel"] == "Auto" for p in body["items"])
    found = await sup.j("/api/v1/policies?q=LM-CO-340021")
    assert found["items"][0]["holderName"] == "Tomás Reyes"


async def test_codes_travel_with_plain_word_labels(sup):
    calls = (await sup.j("/api/v1/calls?pageSize=20"))["items"]
    for c in calls:
        assert c["stateLabel"] and c["outcomeLabel"]
        for f in c["flags"]:
            assert f["label"]
    claims = (await sup.j("/api/v1/claims?pageSize=20"))["items"]
    for c in claims:
        assert c["statusLabel"] and c["lossTypeLabel"]
        if c["route"]:
            assert c["route"]["label"] in ("Fast-track", "Adjuster", "Closer look")


async def test_french_labels_follow_accept_language(sup):
    body = (await sup.get("/api/v1/meta", headers={"Accept-Language": "fr-CA"})).json()
    assert {lt["key"]: lt["label"] for lt in body["lossTypes"]}["wind"] == "Vent"
    claims = (await sup.get("/api/v1/claims?pageSize=5", headers={"Accept-Language": "fr"})).json()["items"]
    assert all(
        c["statusLabel"] in ("Nouvelle", "Assignée", "En examen", "En attente du client", "Fermée") for c in claims
    )


async def test_labels_never_show_technical_words(sup):
    import json

    text = json.dumps(await sup.j("/api/v1/switchboard")).lower()
    for word in ("llm", "shap", "confidence", "slot", "pipeline", "latency"):
        assert word not in text, word


async def test_meta_is_public(anon):
    body = await anon.j("/api/v1/meta")
    assert body["product"] == "ClaimVoice"
    assert {r["key"] for r in body["routes"]} == {"fast_track", "adjuster", "special_investigation"}
    assert any(r["code"] == "US-CA" and r["consentRule"] == "all_party" for r in body["regions"])


async def test_rate_limit_on_auth_routes(api_factory):
    api = await api_factory(None, rate_limits=True)
    codes = []
    for _ in range(12):
        res = await api.post("/api/v1/auth/login", {"email": "rate@limit.example", "password": "whatever-password"})
        codes.append(res.status_code)
    assert 429 in codes
    limited = await api.post("/api/v1/auth/login", {"email": "rate@limit.example", "password": "whatever-password"})
    assert limited.json()["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) >= 1


async def test_health_and_metrics(anon):
    assert (await anon.get("/health")).json()["status"] == "ok"
    body = (await anon.get("/metrics")).text
    for name in (
        "claimvoice_http_requests_total",
        "claimvoice_live_calls",
        "claimvoice_sse_subscribers",
        "claimvoice_turn_response_seconds",
        "claimvoice_tool_timeouts_total",
    ):
        assert name in body, name
