"""Auth and session: cookie + CSRF, demo sign-in by role, login, lockout, sign-up, refresh, password."""

import pytest

ROLES = ["admin", "supervisor", "intake_agent", "adjuster", "siu_investigator", "compliance"]
PEOPLE = {
    "admin": "Nadia Kassem",
    "supervisor": "Renée Kowalchuk",
    "intake_agent": "Jamal Haddad",
    "adjuster": "Lena Ortiz",
    "siu_investigator": "Dev Malhotra",
    "compliance": "Priya Sandhu",
}


async def test_session_is_always_200_for_anonymous_visitors(anon):
    res = await anon.get("/api/v1/auth/session")
    assert res.status_code == 200
    body = res.json()
    assert body["me"] is None
    assert set(body["clock"]) == {"today", "now", "demo", "timezone"}


async def test_csrf_endpoint_sets_a_readable_cookie(anon):
    res = await anon.get("/api/v1/auth/csrf")
    assert res.status_code == 204
    assert anon.c.cookies.get("cv_csrf")


async def test_unsafe_method_without_csrf_header_is_refused(anon):
    res = await anon.c.post("/api/v1/auth/login", json={"email": "x@y.z", "password": "whatever-long"})
    assert res.status_code == 403
    assert res.json()["code"] == "csrf_failed"
    assert res.headers["content-type"].startswith("application/problem+json")


async def test_wrong_csrf_header_is_refused(anon):
    res = await anon.c.post("/api/v1/auth/demo", json={"role": "admin"}, headers={"X-CSRF-Token": "not-the-cookie"})
    assert res.status_code == 403


@pytest.mark.parametrize("role", ROLES)
async def test_demo_sign_in_for_every_role(api_factory, role):
    api = await api_factory(None)
    me = await api.demo(role)
    assert me["user"]["fullName"] == PEOPLE[role]
    assert me["membership"]["role"] == role
    assert me["membership"]["roleLabel"]
    assert me["activeOrg"]["name"] == "Larkspur Mutual"
    assert me["activeOrg"]["isSample"] is True
    assert api.c.cookies.get("cv_session")


async def test_unknown_demo_role_is_a_validation_error(anon):
    res = await anon.post("/api/v1/auth/demo", {"role": "ceo"})
    assert res.status_code in (400, 422)


async def test_login_with_the_demo_password(anon):
    res = await anon.post(
        "/api/v1/auth/login", {"email": "lena.ortiz@larkspur.example", "password": "larkspur-demo-2026"}
    )
    assert res.status_code == 200
    assert res.json()["membership"]["role"] == "adjuster"


async def test_login_failure_is_generic(anon):
    for email in ("lena.ortiz@larkspur.example", "nobody@larkspur.example"):
        res = await anon.post("/api/v1/auth/login", {"email": email, "password": "wrong-password-123"})
        assert res.status_code == 401
        assert res.json()["code"] == "invalid_credentials"


async def test_sign_in_pauses_after_five_failures(anon):
    email = "owen.fairweather@larkspur.example"
    for _ in range(5):
        await anon.post("/api/v1/auth/login", {"email": email, "password": "not-his-password-1"})
    res = await anon.post("/api/v1/auth/login", {"email": email, "password": "larkspur-demo-2026"})
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) > 0


async def test_me_logout_and_session_end(sup):
    assert (await sup.get("/api/v1/auth/me")).status_code == 200
    res = await sup.post("/api/v1/auth/logout")
    assert res.status_code == 204
    after = await sup.get("/api/v1/auth/me")
    assert after.status_code == 401
    assert after.json()["code"] in ("not_authenticated", "session_expired")
    state = await sup.get("/api/v1/auth/session")
    assert state.status_code == 200 and state.json()["me"] is None


async def test_refresh_extends_the_idle_expiry(sup):
    res = await sup.post("/api/v1/auth/refresh")
    assert res.status_code == 200
    body = res.json()
    assert body["expiresAt"] <= body["absoluteExpiresAt"]


async def test_session_state_includes_me_when_signed_in(sup):
    body = (await sup.get("/api/v1/auth/session")).json()
    assert body["me"]["user"]["fullName"] == "Renée Kowalchuk"
    assert "lines:manage" in body["me"]["membership"]["permissions"]


async def test_signup_rejects_weak_passwords(anon):
    res = await anon.post(
        "/api/v1/auth/signup",
        {"email": "ana@prairie.example", "password": "short", "fullName": "Ana", "orgName": "Prairie Mutual"},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "weak_password"
    res = await anon.post(
        "/api/v1/auth/signup",
        {
            "email": "anabella@prairie.example",
            "password": "anabella-is-great-99",
            "fullName": "Ana",
            "orgName": "Prairie Mutual",
        },
    )
    assert res.status_code == 422


async def test_signup_creates_an_org_with_shipped_settings(anon):
    res = await anon.post(
        "/api/v1/auth/signup",
        {
            "email": "kim@prairie.example",
            "password": "copper kettle on the porch",
            "fullName": "Kim Lee",
            "orgName": "Prairie Mutual",
        },
    )
    assert res.status_code == 201, res.text
    me = res.json()
    assert me["membership"]["role"] == "admin"
    assert me["activeOrg"]["isSample"] is False
    scripts = await anon.j("/api/v1/settings/scripts")
    assert {s["lossType"] for s in scripts} >= {"collision", "wind", "water"}
    rules = await anon.j("/api/v1/settings/consent-rules")
    assert any(r["region"] == "US-CA" and r["rule"] == "all_party" for r in rules)
    dup = await anon.post(
        "/api/v1/auth/signup",
        {
            "email": "kim@prairie.example",
            "password": "copper kettle on the porch",
            "fullName": "Kim Lee",
            "orgName": "Other",
        },
    )
    assert dup.status_code == 422


async def test_switch_to_an_org_you_do_not_belong_to_is_404(sup):
    res = await sup.post("/api/v1/auth/switch-org", {"orgId": "00000000-0000-0000-0000-000000000000"})
    assert res.status_code == 404


async def test_password_change_checks_the_current_password(api_factory):
    api = await api_factory("intake_agent")
    bad = await api.post(
        "/api/v1/auth/password", {"currentPassword": "nope-nope-nope", "newPassword": "a whole new phrase 42"}
    )
    assert bad.status_code == 422
    weak = await api.post("/api/v1/auth/password", {"currentPassword": "larkspur-demo-2026", "newPassword": "short"})
    assert weak.json()["code"] == "weak_password"


async def test_auth_events_are_audited(api_factory):
    admin = await api_factory("admin")
    entries = (await admin.j("/api/v1/audit?action=auth.&pageSize=100"))["items"]
    assert any(e["action"] == "auth.login" for e in entries)
    assert all(e["actionLabel"] for e in entries)
