"""The permission matrix (docs/API_CONTRACT.md §1.3), enforced by the API whatever the web app shows.

Allowed roles reach the handler (which then answers 200, 404 for a made-up id, or 422 for a bad body); denied roles get
403 `forbidden` before anything is looked up."""

import pytest

from claimvoice.platform.permissions import ROLE_PERMISSIONS, Role

FAKE = "00000000-0000-0000-0000-000000000000"
ALL = [r.value for r in Role]

CASES = [
    ("GET", "/api/v1/switchboard", None, "lines:read"),
    ("GET", "/api/v1/calls/live", None, "lines:read"),
    ("GET", "/api/v1/calls", None, "calls:read"),
    ("GET", "/api/v1/claims", None, "claims:read"),
    ("GET", "/api/v1/policies", None, "policies:read"),
    ("GET", "/api/v1/settings", None, "settings:read"),
    ("GET", "/api/v1/org/members", None, "members:read"),
    ("GET", "/api/v1/org/invitations", None, "members:manage"),
    ("GET", "/api/v1/qa/queue", None, "qa:read"),
    ("GET", "/api/v1/routing-checks", None, "models:read"),
    ("GET", "/api/v1/audit", None, "audit:read"),
    ("GET", "/api/v1/siu/referrals", None, "siu:read"),
    ("GET", f"/api/v1/claims/{FAKE}/siu", None, "siu:read"),
    ("GET", f"/api/v1/claims/{FAKE}/recording", None, "recordings:read"),
    ("POST", "/api/v1/calls", {"mode": "typed", "region": "CA-AB"}, "calls:start"),
    ("POST", f"/api/v1/calls/{FAKE}/listen", None, "calls:listen"),
    ("POST", f"/api/v1/calls/{FAKE}/whisper", {"text": "Ask about the garage"}, "calls:whisper"),
    ("POST", f"/api/v1/calls/{FAKE}/takeover", None, "calls:takeover"),
    ("POST", f"/api/v1/calls/{FAKE}/say", {"text": "Hello"}, "calls:takeover"),
    ("POST", f"/api/v1/calls/{FAKE}/handoff", {"reason": "Needs a person"}, "calls:handoff"),
    ("POST", f"/api/v1/calls/{FAKE}/handoff/accept", None, "calls:handoff"),
    ("POST", f"/api/v1/calls/{FAKE}/hangup", {"reason": "completed"}, "calls:hangup"),
    ("PATCH", f"/api/v1/claims/{FAKE}", {"status": "in_review"}, "claims:edit"),
    (
        "PATCH",
        f"/api/v1/claims/{FAKE}/file",
        {"slots": [{"key": "loss_place", "value": "x", "note": "y"}]},
        "claims:edit",
    ),
    ("POST", f"/api/v1/claims/{FAKE}/assign", {"userId": None}, "claims:assign"),
    ("POST", f"/api/v1/claims/{FAKE}/routing/accept", None, "claims:route"),
    ("POST", f"/api/v1/claims/{FAKE}/routing/override", {"route": "adjuster", "reason": "x"}, "claims:route"),
    ("POST", f"/api/v1/claims/{FAKE}/siu/decision", {"decision": "investigate", "note": "x"}, "siu:decide"),
    ("POST", f"/api/v1/qa/calls/{FAKE}/review", {"items": []}, "qa:review"),
    ("POST", "/api/v1/routing-checks/size/versions/99/sign-off", {"version": 99, "note": "ok"}, "models:signoff"),
    ("POST", f"/api/v1/surges/{FAKE}/standby", {}, "lines:manage"),
    ("POST", f"/api/v1/surges/{FAKE}/questions", {"on": True}, "lines:manage"),
    (
        "PUT",
        "/api/v1/settings/handoff-rules",
        {
            "urgentKeywords": ["gas"],
            "askedTimes": 1,
            "lowConfidenceTurns": 2,
            "distressThreshold": 0.7,
            "identityAttempts": 3,
            "offerPersonOnConsentRefusal": True,
            "maxWaitSeconds": 90,
            "urgentSafetyAlways": True,
        },
        "settings:manage",
    ),
    ("PATCH", f"/api/v1/org/members/{FAKE}", {"title": "x"}, "members:manage"),
    ("PATCH", "/api/v1/org", {"name": "Larkspur Mutual"}, "org:manage"),
    ("GET", "/api/v1/audit/export.csv", None, "audit:read"),
]


def _matrix() -> list[tuple[str, str, object, str, str]]:
    out = []
    for method, path, body, perm in CASES:
        for role in ALL:
            out.append((method, path, body, perm, role))
    return out


@pytest.mark.parametrize(("method", "path", "body", "perm", "role"), _matrix())
async def test_permission_matrix_is_enforced(api_factory, method, path, body, perm, role):
    api = await api_factory(role)
    if method == "GET":
        res = await api.get(path)
    else:
        res = await getattr(api, method.lower())(path, body)
    allowed = perm in ROLE_PERMISSIONS[Role(role)]
    if allowed:
        assert res.status_code != 403, (role, path, res.text[:200])
    else:
        assert res.status_code == 403, (role, path, res.status_code, res.text[:200])
        assert res.json()["code"] == "forbidden"


async def test_siu_fields_are_stripped_without_siu_read(api_factory):
    adjuster = await api_factory("adjuster")
    compliance = await api_factory("compliance")
    a_claims = (await adjuster.j("/api/v1/claims?pageSize=100"))["items"]
    assert all(c["siuOpen"] is False for c in a_claims)
    claim_id = a_claims[0]["id"]
    a_route = await adjuster.j(f"/api/v1/claims/{claim_id}/routing")
    c_route = await compliance.j(f"/api/v1/claims/{claim_id}/routing")
    assert a_route["fraud"] is None and a_route["signs"] is None
    assert c_route["fraud"] is not None and c_route["signs"] is not None
    for c in (await adjuster.j("/api/v1/calls?pageSize=100"))["items"]:
        assert all(f["kind"] != "siu_signal" for f in c["flags"])


async def test_nobody_can_approve_or_deny_a_claim(sup):
    from claimvoice.platform.permissions import PERMISSIONS

    assert not any(p.endswith(("approve", "deny")) for p in PERMISSIONS)
    claim = (await sup.j("/api/v1/claims?pageSize=1"))["items"][0]
    res = await sup.patch(f"/api/v1/claims/{claim['id']}", {"status": "denied"})
    assert res.status_code in (400, 422)
