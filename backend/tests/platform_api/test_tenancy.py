"""Tenant isolation for every resource type: another organisation's ids are 404 (never 403), and lists never
include another organisation's rows."""

import pytest
from sqlalchemy import select


@pytest.fixture
async def other_org(api_factory):
    """Prairie Mutual: an admin (sign-up) and a compliance member (invitation), sharing nothing with Larkspur."""
    admin = await api_factory(None)
    res = await admin.post(
        "/api/v1/auth/signup",
        {
            "email": "ada@prairie-tenancy.example",
            "password": "an entirely separate phrase",
            "fullName": "Ada Prairie",
            "orgName": "Prairie Tenancy Mutual",
        },
    )
    if res.status_code == 422:  # already created by an earlier test in this module
        res = await admin.post(
            "/api/v1/auth/login", {"email": "ada@prairie-tenancy.example", "password": "an entirely separate phrase"}
        )
    assert res.status_code in (200, 201), res.text
    compliance = await api_factory(None)
    login = await compliance.post(
        "/api/v1/auth/login", {"email": "cy@prairie-tenancy.example", "password": "another separate phrase"}
    )
    if login.status_code != 200:
        inv = await admin.post("/api/v1/org/invitations", {"email": "cy@prairie-tenancy.example", "role": "compliance"})
        assert inv.status_code == 201, inv.text
        token = inv.json()["acceptUrl"].rsplit("/", 1)[-1]
        preview = await compliance.j(f"/api/v1/invitations/{token}")
        assert preview["orgName"] == "Prairie Tenancy Mutual"
        acc = await compliance.post(
            f"/api/v1/invitations/{token}/accept", {"fullName": "Cy Prairie", "password": "another separate phrase"}
        )
        assert acc.status_code == 200, acc.text
    return admin, compliance


async def _larkspur_ids(sup):
    from claimvoice.calls.models import Call, Surge
    from claimvoice.claims.models import ClaimPhoto
    from claimvoice.platform import db

    claims = (await sup.j("/api/v1/claims?pageSize=100"))["items"]
    claim = next(c for c in claims if c["claimNumber"].endswith("01842"))
    calls = (await sup.j("/api/v1/calls?pageSize=100"))["items"]
    live = next(c for c in calls if c["state"] != "ended")
    policies = (await sup.j("/api/v1/policies?pageSize=5"))["items"]
    holders = (await sup.j("/api/v1/policyholders?pageSize=5"))["items"]
    members = await sup.j("/api/v1/org/members")
    async with db.sessionmaker()() as s:
        surge = (await s.execute(select(Surge))).scalars().first()
        call_row = await s.get(Call, live["id"])
        photo = (await s.execute(select(ClaimPhoto))).scalars().first()
    return {
        "claim": claim["id"],
        "call": live["id"],
        "ended_call": claim["id"] and next(c["id"] for c in calls if c["state"] == "ended"),
        "policy": policies[0]["id"],
        "holder": holders[0]["id"],
        "member": members[0]["membershipId"],
        "surge": surge.id,
        "photo": photo.id if photo else None,
        "org_id": call_row.org_id,
    }


async def test_another_orgs_ids_are_404_for_every_resource(sup, other_org):
    admin, compliance = other_org
    ids = await _larkspur_ids(sup)
    paths = [
        f"/api/v1/claims/{ids['claim']}",
        f"/api/v1/claims/{ids['claim']}/transcript",
        f"/api/v1/claims/{ids['claim']}/routing",
        f"/api/v1/claims/{ids['claim']}/photos",
        f"/api/v1/calls/{ids['call']}",
        f"/api/v1/calls/{ids['call']}/transcript",
        f"/api/v1/calls/{ids['call']}/claim-file",
        f"/api/v1/calls/{ids['call']}/timeline",
        f"/api/v1/calls/{ids['call']}/messages",
        f"/api/v1/calls/{ids['call']}/stream",
        f"/api/v1/policies/{ids['policy']}",
        f"/api/v1/policyholders/{ids['holder']}",
        f"/api/v1/surges/{ids['surge']}",
        f"/api/v1/qa/calls/{ids['ended_call']}",
    ]
    for path in paths:
        res = await admin.get(path)
        assert res.status_code == 404, (path, res.status_code)
        assert res.json()["code"] == "not_found"
    for path in (
        f"/api/v1/claims/{ids['claim']}/siu",
        f"/api/v1/claims/{ids['claim']}/recording",
        f"/api/v1/calls/{ids['ended_call']}/recording",
        f"/api/v1/claims/{ids['claim']}/recording/audio",
    ):
        res = await compliance.get(path)
        assert res.status_code == 404, (path, res.status_code)
    if ids["photo"]:
        assert (await admin.get(f"/api/v1/photos/{ids['photo']}")).status_code == 404


async def test_another_orgs_ids_cannot_be_changed(sup, other_org):
    admin, compliance = other_org
    ids = await _larkspur_ids(sup)
    assert (await admin.patch(f"/api/v1/org/members/{ids['member']}", {"title": "Mine now"})).status_code == 404
    assert (await admin.delete(f"/api/v1/org/members/{ids['member']}")).status_code == 404
    assert (await admin.post(f"/api/v1/claims/{ids['claim']}/assign", {"userId": None})).status_code == 404
    review = await compliance.post(f"/api/v1/qa/calls/{ids['ended_call']}/review", {"items": []})
    assert review.status_code == 404


async def test_lists_only_show_your_own_organisation(other_org):
    admin, compliance = other_org
    assert (await admin.j("/api/v1/claims"))["total"] == 0
    assert (await admin.j("/api/v1/calls"))["total"] == 0
    assert (await admin.j("/api/v1/policies"))["total"] == 0
    assert await admin.j("/api/v1/calls/live") == []
    board = await admin.j("/api/v1/switchboard")
    assert board["lines"] == [] and board["handoffTray"] == [] and board["surge"] is None
    assert {m["fullName"] for m in await admin.j("/api/v1/org/members")} == {"Ada Prairie", "Cy Prairie"}
    entries = (await admin.j("/api/v1/audit?pageSize=100"))["items"]
    assert entries and all("Larkspur" not in e["summary"] for e in entries)
    assert (await compliance.j("/api/v1/siu/referrals"))["total"] == 0
    assert (await admin.j("/api/v1/routing-checks"))["checks"] == []


async def test_invitation_flow_and_last_admin_rule(other_org):
    admin, _ = other_org
    members = await admin.j("/api/v1/org/members")
    me = next(m for m in members if m["isYou"])
    res = await admin.patch(f"/api/v1/org/members/{me['membershipId']}", {"role": "compliance"})
    assert res.status_code == 409 and res.json()["code"] == "last_admin"
    inv = await admin.post("/api/v1/org/invitations", {"email": "not-an-email", "role": "admin"})
    assert inv.status_code == 422
    inv = await admin.post("/api/v1/org/invitations", {"email": "dee@prairie-tenancy.example", "role": "adjuster"})
    assert inv.status_code == 201
    listed = await admin.j("/api/v1/org/invitations")
    assert any(i["email"] == "dee@prairie-tenancy.example" and i["status"] == "pending" for i in listed)
    assert (await admin.delete(f"/api/v1/org/invitations/{inv.json()['id']}")).status_code == 204
    token = inv.json()["acceptUrl"].rsplit("/", 1)[-1]
    assert (await admin.get(f"/api/v1/invitations/{token}")).status_code == 404
