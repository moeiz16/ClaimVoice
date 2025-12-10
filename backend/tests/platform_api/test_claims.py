"""Claims: the ledger, claim file corrections, "Where it goes", closer-look referrals, recordings and photo links."""

import io
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import select, update

from claimvoice import clock
from claimvoice.calls.models import Call, PhotoLink
from claimvoice.platform import db
from claimvoice.platform.security import token_digest


async def _claim(api, suffix):
    claims = (await api.j("/api/v1/claims?pageSize=100"))["items"]
    return next(c for c in claims if c["claimNumber"].endswith(suffix))


async def test_ledger_is_newest_first_and_filters_by_route(sup):
    body = await sup.j("/api/v1/claims?pageSize=100")
    reported = [c["reportedAt"] for c in body["items"]]
    assert reported == sorted(reported, reverse=True)
    fast = await sup.j("/api/v1/claims?route=fast_track&pageSize=100")
    assert fast["items"] and all(c["route"]["route"] == "fast_track" for c in fast["items"])
    wind = await sup.j("/api/v1/claims?lossType=wind&pageSize=100")
    assert all(c["lossType"] == "wind" for c in wind["items"])
    co = await sup.j("/api/v1/claims?region=US-CO&pageSize=100")
    assert co["items"] and all(c["regionLabel"] == "Colorado" for c in co["items"])
    q = await sup.j("/api/v1/claims?q=Whitcombe")
    assert [c["claimNumber"] for c in q["items"]] == ["CV-26-01842"]
    surge = (await sup.j("/api/v1/switchboard"))["surge"]
    in_surge = await sup.j(f"/api/v1/claims?surge={surge['id']}&pageSize=100")
    assert in_surge["total"] == surge["claimsSoFar"]


async def test_closer_look_filter_only_for_siu_readers(api_factory):
    dev = await api_factory("siu_investigator")
    lena = await api_factory("adjuster")
    flagged = await dev.j("/api/v1/claims?flag=siu&pageSize=100")
    assert any(c["claimNumber"] == "CV-26-01856" and c["siuOpen"] for c in flagged["items"])
    everyone = await lena.j("/api/v1/claims?flag=siu&pageSize=100")
    assert all(c["siuOpen"] is False for c in everyone["items"])


async def test_claim_detail_in_short_links_point_into_the_transcript(sup):
    claim = await _claim(sup, "01842")
    detail = await sup.j(f"/api/v1/claims/{claim['id']}")
    transcript = await sup.j(f"/api/v1/claims/{claim['id']}/transcript")
    turns = {t["id"]: t for t in transcript["turns"]}
    for link in detail["inShort"]["links"]:
        assert link["turnId"] in turns
        assert 0 <= link["start"] < link["end"] <= len(detail["inShort"]["text"])
    assert detail["file"]["sections"] and detail["nextSteps"]
    assert detail["holderName"] == "Dana Whitcombe" and detail["policyNumber"] == "LM-AB-187342"


async def test_where_it_goes_for_tomas(api_factory):
    lena = await api_factory("adjuster")
    dev = await api_factory("siu_investigator")
    claim = await _claim(lena, "01856")
    route = await lena.j(f"/api/v1/claims/{claim['id']}/routing")
    assert route["route"] == "adjuster" and route["override"]["reason"] == "Police report confirms the SUV."
    assert route["override"]["by"]["name"] == "Lena Ortiz"
    assert route["fraud"] is None and route["signs"] is None
    assert route["signsChecked"] == 14
    assert "deny" in route["statement"]
    dev_view = await dev.j(f"/api/v1/claims/{claim['id']}/routing")
    assert dev_view["modelRoute"] == "special_investigation"
    assert [s["label"] for s in dev_view["signs"]] == [
        "Policy started 19 days before the loss",
        "Coverage was raised 9 days before the loss",
        "Someone other than the policyholder pushed for a fast payment",
    ]
    referral = await dev.j(f"/api/v1/claims/{claim['id']}/siu")
    assert referral["status"] == "open" and "not a finding of fraud" in referral["statement"]


async def test_accept_then_change_a_route(api_factory):
    sup = await api_factory("supervisor")
    claims = (await sup.j("/api/v1/claims?route=fast_track&pageSize=100"))["items"]
    target = next(c for c in claims if c["route"]["decidedBy"] == "model" and c["status"] == "new")
    route = await sup.j(f"/api/v1/claims/{target['id']}/routing")
    if route["acceptedBy"] is None:
        ok = await sup.post(f"/api/v1/claims/{target['id']}/routing/accept")
        assert ok.status_code == 200 and ok.json()["acceptedBy"]["name"] == "Renée Kowalchuk"
    again = await sup.post(f"/api/v1/claims/{target['id']}/routing/accept")
    assert again.status_code == 409 and again.json()["code"] == "already_decided"
    no_reason = await sup.post(f"/api/v1/claims/{target['id']}/routing/override", {"route": "adjuster", "reason": "  "})
    assert no_reason.status_code == 422 and no_reason.json()["errors"][0]["field"] == "reason"
    changed = await sup.post(
        f"/api/v1/claims/{target['id']}/routing/override",
        {"route": "adjuster", "reason": "Second vehicle mentioned at the end"},
    )
    assert changed.status_code == 200
    assert changed.json()["route"] == "adjuster" and changed.json()["modelRoute"] == "fast_track"
    admin = await api_factory("admin")
    audit = (await admin.j(f"/api/v1/audit?target=claim:{target['id']}"))["items"]
    assert {"claim.route_accepted", "claim.route_override"} <= {e["action"] for e in audit}


async def test_siu_decision_by_the_investigator(api_factory):
    dev = await api_factory("siu_investigator")
    claim = await _claim(dev, "01856")
    no_note = await dev.post(f"/api/v1/claims/{claim['id']}/siu/decision", {"decision": "investigate", "note": ""})
    assert no_note.status_code == 422
    res = await dev.post(
        f"/api/v1/claims/{claim['id']}/siu/decision",
        {"decision": "investigate", "note": "Requesting the dash-cam video."},
    )
    assert res.status_code == 200 and res.json()["status"] == "investigating"
    referrals = await dev.j("/api/v1/siu/referrals")
    assert referrals["items"][0]["status"] in ("open", "investigating")
    closed = await dev.post(
        f"/api/v1/claims/{claim['id']}/siu/decision",
        {"decision": "close_no_concern", "note": "Video matches the police report."},
    )
    assert closed.status_code == 200
    late = await dev.post(f"/api/v1/claims/{claim['id']}/siu/decision", {"decision": "investigate", "note": "x"})
    assert late.status_code == 409


async def test_correcting_the_claim_file_keeps_what_was_heard(api_factory):
    lena = await api_factory("adjuster")
    claim = await _claim(lena, "01853")
    before = await lena.j(f"/api/v1/claims/{claim['id']}")
    res = await lena.patch(
        f"/api/v1/claims/{claim['id']}/file",
        {"slots": [{"key": "loss_place", "value": "14 Sheep River Dr, Okotoks", "note": "Confirmed by phone"}]},
    )
    assert res.status_code == 200, res.text
    slot = next(s for sec in res.json()["sections"] for s in sec["slots"] if s["key"] == "loss_place")
    assert slot["source"] == "person" and slot["sourceLabel"] == "edited by Lena Ortiz"
    assert slot["display"] == "14 Sheep River Dr, Okotoks"
    had = any(s["key"] == "loss_place" for sec in before["file"]["sections"] for s in sec["slots"])
    assert len(slot["history"]) == (1 if had else 0)
    bad = await lena.patch(
        f"/api/v1/claims/{claim['id']}/file", {"slots": [{"key": "nonsense", "value": 1, "note": "x"}]}
    )
    assert bad.status_code == 422
    no_note = await lena.patch(
        f"/api/v1/claims/{claim['id']}/file", {"slots": [{"key": "loss_place", "value": "x", "note": ""}]}
    )
    assert no_note.status_code == 422


async def test_status_and_assignment(api_factory):
    sup = await api_factory("supervisor")
    lena_id = next(m["userId"] for m in await sup.j("/api/v1/org/members") if m["fullName"] == "Lena Ortiz")
    claim = await _claim(sup, "01845")
    res = await sup.post(f"/api/v1/claims/{claim['id']}/assign", {"userId": lena_id})
    assert res.status_code == 200 and res.json()["assignedTo"]["name"] == "Lena Ortiz"
    assert res.json()["status"] in ("assigned", "in_review", "waiting_on_customer", "closed")
    stranger = await sup.post(f"/api/v1/claims/{claim['id']}/assign", {"userId": "not-a-member"})
    assert stranger.status_code == 422
    status = await sup.patch(f"/api/v1/claims/{claim['id']}", {"status": "in_review"})
    assert status.status_code == 200 and status.json()["statusLabel"] == "In review"
    mine = await (await api_factory("adjuster")).j("/api/v1/claims?assigned=me&pageSize=100")
    assert any(c["id"] == claim["id"] for c in mine["items"])


async def test_recording_band_and_audio_with_range(api_factory):
    lena = await api_factory("adjuster")
    claim = await _claim(lena, "01842")
    rec = await lena.j(f"/api/v1/claims/{claim['id']}/recording")
    assert rec["available"] and rec["durationSeconds"] > 10
    assert len(rec["peaks"]) == 800 and all(0 <= p <= 1 for p in rec["peaks"])
    assert rec["segments"] and {m["kind"] for m in rec["moments"]} & {"consent", "policy", "safety"}
    starts = [s["startSeconds"] for s in rec["segments"]]
    assert starts == sorted(starts)
    part = await lena.get(rec["audioUrl"], headers={"Range": "bytes=0-1023"})
    assert part.status_code == 206 and part.headers["content-range"].startswith("bytes 0-1023/")
    assert len(part.content) == 1024
    admin = await api_factory("admin")
    played = (await admin.j("/api/v1/audit?action=recording.played"))["items"]
    assert any(e["targetLabel"] == "CV-26-01842" and e["actorLabel"] == "Lena Ortiz" for e in played)


def _png_with_gps() -> bytes:
    img = Image.new("RGB", (64, 48), (120, 160, 200))
    exif = Image.Exif()
    exif[0x8825] = {2: (51.0, 3.0, 0.0), 4: (114.0, 4.0, 0.0)}  # GPS IFD
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


@pytest.fixture
async def photo_token(sup):
    """A fresh photo link on Line 3 (the line has texted one; this test makes its own token)."""
    lines = await sup.j("/api/v1/calls/live")
    call_id = next(x["callId"] for x in lines if x["lineLabel"] == "Line 3")
    token = "test-photo-token-123456"
    async with db.sessionmaker()() as s:
        call = await s.get(Call, call_id)
        existing = (
            await s.execute(select(PhotoLink).where(PhotoLink.token_hash == token_digest(token)))
        ).scalar_one_or_none()
        if existing is None:
            s.add(
                PhotoLink(
                    org_id=call.org_id,
                    call_id=call_id,
                    token_hash=token_digest(token),
                    expires_at=clock.real_now() + timedelta(hours=72),
                    max_photos=3,
                )
            )
            await s.commit()
    await db.dispose()
    return token


async def test_photo_link_upload_strips_location(anon, photo_token):
    info = await anon.j(f"/api/v1/photo-links/{photo_token}")
    assert info["orgName"] == "Larkspur Mutual" and info["language"] == "fr" and info["maxPhotos"] == 3
    res = await anon.c.post(
        f"/api/v1/photo-links/{photo_token}/photos",
        files={"file": ("sous-sol.jpg", _png_with_gps(), "image/jpeg")},
        data={"caption": "Le sous-sol"},
    )
    assert res.status_code == 201, res.text
    photo = res.json()
    assert photo["caption"] == "Le sous-sol" and photo["width"] == 64 and photo["source"] == "text_link"
    from claimvoice.claims.models import ClaimPhoto
    from claimvoice.config import get_settings

    async with db.sessionmaker()() as s:
        row = await s.get(ClaimPhoto, photo["id"])
    stored = Image.open(get_settings().uploads_dir / row.path)
    assert not stored.getexif().get_ifd(0x8825)
    await db.dispose()


async def test_photo_link_rejects_other_files_and_expired_links(anon, photo_token):
    text = await anon.c.post(
        f"/api/v1/photo-links/{photo_token}/photos", files={"file": ("a.txt", b"hello", "text/plain")}
    )
    assert text.status_code == 415 and text.json()["code"] == "unsupported_media_type"
    heic = await anon.c.post(
        f"/api/v1/photo-links/{photo_token}/photos", files={"file": ("a.heic", b"x", "image/heic")}
    )
    assert heic.status_code == 415
    assert (await anon.get("/api/v1/photo-links/not-a-real-token")).status_code == 404
    async with db.sessionmaker()() as s:
        await s.execute(
            update(PhotoLink)
            .where(PhotoLink.token_hash == token_digest(photo_token))
            .values(expires_at=clock.real_now() - timedelta(minutes=1))
        )
        await s.commit()
    await db.dispose()
    gone = await anon.get(f"/api/v1/photo-links/{photo_token}")
    assert gone.status_code == 410 and gone.json()["code"] == "expired"
