"""Calls: the live lines, detail, transcript with staff-only whisper rows, claim-file spans, timeline, starting a call,
the caller leg, and every line control (listen, whisper, take over, say, hand back, hang up, hand off)."""

import pytest

from claimvoice.calls import runtime
from tests.platform_api.fakes import FakeRuntime


@pytest.fixture
def rt():
    fake = FakeRuntime()
    runtime.use_runtime(fake)
    yield fake
    runtime.use_runtime(None, disabled=True)


async def _line(api, number):
    lines = await api.j("/api/v1/calls/live")
    return next(x for x in lines if x["lineLabel"] == f"Line {number}")


async def test_live_lines_show_the_morning_story(sup):
    lines = await sup.j("/api/v1/calls/live")
    by_label = {x["lineLabel"]: x for x in lines}
    assert by_label["Line 1"]["callerLabel"] == "Gord Lindqvist"
    assert by_label["Line 1"]["lossType"] == "wind" and by_label["Line 1"]["inSurge"] is True
    assert by_label["Line 2"]["callerLabel"] == "Kiara Booker" and by_label["Line 2"]["regionLabel"] == "Colorado"
    assert by_label["Line 3"]["language"] == "fr" and by_label["Line 3"]["stage"]["step"] == 5
    assert by_label["Line 4"]["state"] == "waiting_for_person"
    assert by_label["Line 4"]["handoff"]["priority"] == "urgent"
    only_ab = await sup.j("/api/v1/calls/live?region=CA-AB")
    assert {x["lineLabel"] for x in only_ab} == {"Line 1", "Line 4", "Line 5"}


async def test_call_detail_has_line_label_place_consent_and_stages(sup):
    line = await _line(sup, 1)
    detail = await sup.j(f"/api/v1/calls/{line['callId']}")
    assert detail["lineLabel"] == "Line 1"
    assert detail["place"] == "Saddle Ridge, Calgary"
    assert detail["consent"]["answer"] == "given" and detail["consent"]["rule"] == "all_party"
    assert "Alberta" in detail["consent"]["ruleLabel"]
    assert [s["step"] for s in detail["stages"]] == [1, 1, 2, 3, 4, 4, 5, 6, 7, 7]
    assert detail["stage"]["label"] and detail["stage"]["stepLabel"] == "What happened"
    assert detail["policyNumber"] == "LM-AB-204118"


async def test_claim_file_spans_point_into_the_transcript(sup):
    line = await _line(sup, 1)
    transcript = await sup.j(f"/api/v1/calls/{line['callId']}/transcript")
    turns = {t["id"]: t for t in transcript["turns"]}
    file = await sup.j(f"/api/v1/calls/{line['callId']}/claim-file")
    checked = 0
    for section in file["sections"]:
        for slot in section["slots"]:
            if slot["span"]:
                text = turns[slot["span"]["turnId"]]["text"]
                assert 0 <= slot["span"]["start"] < slot["span"]["end"] <= len(text)
                assert slot["sourceLabel"].startswith("▸ ")
                checked += 1
    assert checked >= 5
    assert 0 < file["progress"] <= 1


async def test_whisper_is_staff_only_audited_and_reaches_the_line(sup, rt):
    line = await _line(sup, 1)
    rt.live.add(line["callId"])
    res = await sup.post(
        f"/api/v1/calls/{line['callId']}/whisper", {"text": "Ask if the garage skylight is damaged too"}
    )
    assert res.status_code == 202
    assert rt.of("whisper")[0][1]["text"] == "Ask if the garage skylight is damaged too"
    transcript = await sup.j(f"/api/v1/calls/{line['callId']}/transcript")
    whispers = [t for t in transcript["turns"] if t["speaker"] == "whisper"]
    assert whispers and whispers[-1]["speakerLabel"].startswith("Whisper, ClaimVoice only")
    timeline = await sup.j(f"/api/v1/calls/{line['callId']}/timeline")
    assert any(e["kind"] == "whisper" for e in timeline)
    too_long = await sup.post(f"/api/v1/calls/{line['callId']}/whisper", {"text": "x" * 281})
    assert too_long.status_code == 422


async def test_listen_adds_a_listener_and_nudges_a_scripted_line(sup, rt):
    line = await _line(sup, 2)
    rt.live.add(line["callId"])
    res = await sup.post(f"/api/v1/calls/{line['callId']}/listen")
    assert res.status_code == 200 and res.json()["mode"] == "transcript"
    detail = await sup.j(f"/api/v1/calls/{line['callId']}")
    assert any(x["name"] == "Renée Kowalchuk" and x["mode"] == "listening" for x in detail["listeners"])
    assert rt.of("nudge")
    assert (await sup.delete(f"/api/v1/calls/{line['callId']}/listen")).status_code == 204
    detail = await sup.j(f"/api/v1/calls/{line['callId']}")
    assert detail["listeners"] == []


async def test_take_over_say_and_hand_back(api_factory, rt):
    sup = await api_factory("supervisor")
    agent = await api_factory("intake_agent")
    line = await _line(sup, 3)
    rt.live.add(line["callId"])
    not_yet = await sup.post(f"/api/v1/calls/{line['callId']}/say", {"text": "Bonjour, ici Renée."})
    assert not_yet.status_code == 409 and not_yet.json()["code"] == "not_taken_over"
    took = await sup.post(f"/api/v1/calls/{line['callId']}/takeover")
    assert took.status_code == 200
    assert took.json()["call"]["state"] == "with_person"
    assert rt.of("take_over")
    clash = await agent.post(f"/api/v1/calls/{line['callId']}/takeover")
    assert clash.status_code == 409 and clash.json()["code"] == "already_taken"
    said = await sup.post(f"/api/v1/calls/{line['callId']}/say", {"text": "Bonjour, ici Renée de Larkspur."})
    assert said.status_code == 202 and said.json()["turnId"] == "turn-from-runtime"
    back = await sup.post(f"/api/v1/calls/{line['callId']}/return")
    assert back.status_code == 200 and back.json()["state"] == "with_line"
    assert rt.of("hand_back")
    audit = await api_factory("admin")
    actions = [e["action"] for e in (await audit.j("/api/v1/audit?action=call.&pageSize=100"))["items"]]
    assert {"call.takeover", "call.returned"} <= set(actions)


async def test_say_without_the_runtime_is_written_as_a_person_turn(sup):
    line = await _line(sup, 2)
    assert (await sup.post(f"/api/v1/calls/{line['callId']}/takeover")).status_code == 200
    res = await sup.post(f"/api/v1/calls/{line['callId']}/say", {"text": "Hi Kiara, this is Renée from Larkspur."})
    assert res.status_code == 202
    transcript = await sup.j(f"/api/v1/calls/{line['callId']}/transcript")
    assert transcript["turns"][-1]["speaker"] == "person"
    assert transcript["turns"][-1]["speakerLabel"] == "Renée Kowalchuk"
    await sup.post(f"/api/v1/calls/{line['callId']}/return")


async def test_accepting_a_hand_off_once(api_factory):
    jamal = await api_factory("intake_agent")
    sup = await api_factory("supervisor")
    board = await sup.j("/api/v1/switchboard")
    wendy = next(h for h in board["handoffTray"] if h["callerLabel"] == "Wendy Arsenault")
    res = await jamal.post(f"/api/v1/calls/{wendy['callId']}/handoff/accept")
    assert res.status_code == 200, res.text
    assert res.json()["handoff"]["acceptedBy"]["name"] == "Jamal Haddad"
    again = await sup.post(f"/api/v1/calls/{wendy['callId']}/handoff/accept")
    assert again.status_code == 409 and again.json()["code"] == "already_taken"
    board = await sup.j("/api/v1/switchboard")
    assert all(h["callId"] != wendy["callId"] for h in board["handoffTray"])
    assert "Jamal Haddad" not in [p["name"] for p in board["freePeople"]]


async def test_hand_off_from_the_dock_to_a_team(sup):
    line = await _line(sup, 2)
    res = await sup.post(
        f"/api/v1/calls/{line['callId']}/handoff", {"reason": "Wants to talk about the rental car", "team": "intake"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "waiting" and body["team"] == "intake" and body["reasonLabel"]
    board = await sup.j("/api/v1/switchboard")
    assert any(h["callId"] == line["callId"] for h in board["handoffTray"])
    bad = await sup.post(f"/api/v1/calls/{line['callId']}/handoff", {"reason": "x", "toUserId": "someone-else"})
    assert bad.status_code == 422


async def test_hang_up_closes_the_line_and_opens_the_claim(sup, rt):
    line = await _line(sup, 1)
    rt.live.add(line["callId"])
    res = await sup.post(f"/api/v1/calls/{line['callId']}/hangup", {"reason": "completed", "note": "Caller had to go"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["state"] == "ended"
    assert body["outcome"] == "claim_created" and body["claimNumber"].startswith("CV-26-")
    routing = await sup.j(f"/api/v1/claims/{body['claimId']}/routing")
    assert routing["route"] in ("fast_track", "adjuster", "special_investigation")
    assert routing["statement"].startswith("For a person to review")
    late = await sup.post(f"/api/v1/calls/{line['callId']}/whisper", {"text": "Too late"})
    assert late.status_code == 409 and late.json()["code"] == "call_not_live"
    qa = await sup.j(f"/api/v1/qa/calls/{line['callId']}")
    assert qa["claimId"] == body["claimId"] and len(qa["beads"]) == 6


async def test_start_a_call_and_use_the_caller_leg(sup, anon, rt):
    res = await sup.post("/api/v1/calls", {"mode": "typed", "language": "en", "region": "US-CA"})
    assert res.status_code == 201, res.text
    body = res.json()
    connect = body["connect"]
    assert connect["dataChannelLabel"] == "claimvoice" and connect["maxSeconds"] == 1800
    assert body["call"]["consent"]["rule"] == "all_party"
    assert rt.of("prepare")[-1][1]["region"] == "US-CA"
    bearer = {"Authorization": f"Bearer {connect['callerToken']}"}
    answer = await anon.c.post(connect["offerUrl"], json={"sdp": "v=0 offer", "type": "offer"}, headers=bearer)
    assert answer.status_code == 200 and answer.json()["type"] == "answer"
    ice = await anon.c.patch(
        connect["iceUrl"],
        json={"pcId": "pc-1", "candidates": [{"candidate": "c", "sdpMid": "0", "sdpMLineIndex": 0}]},
        headers=bearer,
    )
    assert ice.status_code == 204
    wrong = await anon.c.post(
        connect["offerUrl"], json={"sdp": "v=0", "type": "offer"}, headers={"Authorization": "Bearer nope"}
    )
    assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_call_token"
    hung = await anon.c.post(
        f"/api/v1/calls/{connect['callId']}/hangup", json={"reason": "caller_request"}, headers=bearer
    )
    assert hung.status_code == 200 and hung.json()["state"] == "ended"


async def test_public_demo_line(anon, rt):
    res = await anon.post("/api/v1/demo/calls", {"mode": "browser_speech", "scenario": "calgary-windstorm"})
    assert res.status_code == 201, res.text
    assert res.json()["connect"]["maxSeconds"] == 360
    bad = await anon.post("/api/v1/demo/calls", {"scenario": "not-a-caller"})
    assert bad.status_code == 422


async def test_messages_show_the_photo_link_for_the_sample_org(sup):
    calls = (await sup.j("/api/v1/calls?pageSize=100&status=ended"))["items"]
    dana = next(c for c in calls if c["claimNumber"] and c["claimNumber"].endswith("01842"))
    messages = await sup.j(f"/api/v1/calls/{dana['id']}/messages")
    assert messages and "/p/" in messages[0]["body"] and messages[0]["toMasked"].startswith("•••")


async def test_call_list_filters(sup):
    live = await sup.j("/api/v1/calls?status=live")
    assert all(c["state"] != "ended" for c in live["items"])
    fr = await sup.j("/api/v1/calls?language=fr&pageSize=100")
    assert fr["items"] and all(c["language"] == "fr" for c in fr["items"])
    q = await sup.j("/api/v1/calls?q=CV-26-01856")
    assert q["total"] == 1 and q["items"][0]["callerLabel"]
    bad = await sup.get("/api/v1/calls?from=yesterday")
    assert bad.status_code == 400
