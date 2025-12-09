"""Server-Sent Events: framing (integer retry and ids), replay with Last-Event-ID, resync, pings, permission
filtering, and the two HTTP streams."""

import json

from claimvoice.platform import events
from claimvoice.platform.events import EventBus, Event, frame, parse_last_event_id, retry_frame, visible


def test_retry_field_is_an_integer():
    assert retry_frame() == b"retry: 3000\n\n"
    assert retry_frame(2500.7) == b"retry: 2500\n\n"  # type: ignore[arg-type]


def test_frame_layout():
    raw = frame("line.updated", {"type": "line.updated", "data": {"a": 1}}, 7).decode()
    lines = raw.split("\n")
    assert lines[0] == "id: 7" and lines[1] == "event: line.updated"
    assert json.loads(lines[2][len("data: ") :])["data"] == {"a": 1}
    assert raw.endswith("\n\n")
    assert "id:" not in frame("ping", {}).decode()


def test_last_event_id_parsing():
    assert parse_last_event_id("12") == 12
    assert parse_last_event_id(" 3 ") == 3
    assert parse_last_event_id("abc") is None and parse_last_event_id("-1") is None and parse_last_event_id(None) is None


def test_ids_increase_per_stream_and_replay_after_a_reconnect():
    bus = EventBus()
    for i in range(5):
        bus.publish("org:a", "stats.updated", {"n": i}, org_id="a")
    bus.publish("org:b", "stats.updated", {"n": 0}, org_id="b")
    assert bus.last_id("org:a") == 5 and bus.last_id("org:b") == 1
    _, replay, resync = bus.subscribe("org:a", 2)
    assert not resync and [e.id for e in replay] == [3, 4, 5]
    _, replay, resync = bus.subscribe("org:a", 5)
    assert replay == [] and not resync


def test_unknown_future_id_asks_for_a_resync():
    bus = EventBus()
    bus.publish("org:a", "x", {}, org_id="a")
    _, replay, resync = bus.subscribe("org:a", 40)
    assert resync and replay == []


def test_gap_older_than_the_replay_window_asks_for_a_resync(monkeypatch):
    bus = EventBus()
    for _ in range(3):
        bus.publish("org:a", "x", {}, org_id="a")
    stream = bus._streams["org:a"]
    stream.recent.popleft()  # event 1 aged out
    stream.recent.popleft()  # event 2 aged out
    _, replay, resync = bus.subscribe("org:a", 0)
    assert resync


def test_transient_events_have_no_id_and_are_not_kept():
    bus = EventBus()
    q, _, _ = bus.subscribe("call:c", None)
    assert bus.publish("call:c", "turn.partial", {"text": "hi"}, org_id="a", transient=True) is None
    assert q.get_nowait().id is None
    assert bus.last_id("call:c") == 0


def test_closer_look_fields_are_removed_without_siu_read():
    env = {"type": "line.updated", "data": {"flags": [{"kind": "siu_signal"}, {"kind": "surge"}], "siuOpen": True,
                                            "nested": {"fraud": {"band": "high"}, "signs": [1]}}}  # fmt: skip
    ev = Event(1, "line.updated", env)
    stripped = visible(ev, {"lines:read"})
    assert stripped["data"]["flags"] == [{"kind": "surge"}]
    assert stripped["data"]["siuOpen"] is False
    assert stripped["data"]["nested"] == {"fraud": None, "signs": None}
    assert visible(ev, {"siu:read"}) is env
    assert visible(Event(2, "flag.raised", {"data": {"kind": "siu_signal"}}), set()) is None


async def test_stream_yields_retry_replay_then_ping():
    bus = EventBus()
    events.bus, old = bus, events.bus
    try:
        bus.publish("org:z", "stats.updated", {"n": 1}, org_id="z")
        bus.publish("org:z", "stats.updated", {"n": 2}, org_id="z")
        chunks = []
        agen = events.sse("org:z", org_id="z", permissions=set(), last_event_id=1, ping_seconds=0.01)
        async for chunk in agen:
            chunks.append(chunk.decode())
            if len(chunks) == 3:
                break
        await agen.aclose()
    finally:
        events.bus = old
    assert chunks[0] == "retry: 3000\n\n"
    assert chunks[1].startswith("id: 2\nevent: stats.updated\n")
    assert chunks[2].startswith("event: ping")


async def test_switchboard_stream_over_http(sup):
    res = await sup.get("/api/v1/switchboard/stream", headers={"Last-Event-ID": "0"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["cache-control"] == "no-cache, no-transform"
    assert res.headers["x-accel-buffering"] == "no"
    assert res.headers["x-claimvoice-now"]
    assert res.text.startswith("retry: 3000\n\n")


async def test_call_stream_carries_a_whisper(sup):
    lines = await sup.j("/api/v1/calls/live")
    line = next(x for x in lines if x["lineLabel"] == "Line 2")
    before = events.bus.last_id(events.call_key(line["callId"]))
    await sup.post(f"/api/v1/calls/{line['callId']}/whisper", {"text": "Ask about the rental car"})
    res = await sup.get(f"/api/v1/calls/{line['callId']}/stream", headers={"Last-Event-ID": str(before)})
    assert "event: whisper.sent" in res.text
    payload = next(ln for ln in res.text.split("\n") if ln.startswith("data:") and "whisper.sent" in ln)
    assert json.loads(payload[5:])["data"]["text"] == "Ask about the rental car"
