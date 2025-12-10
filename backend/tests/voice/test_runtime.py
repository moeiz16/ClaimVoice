"""The voice runtime end to end: a real SmallWebRTC call through Pipecat, the WebSocket fallback, `voice` mode with
the speech fakes and barge-in, scripted demo lines, and the supervisor's controls."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import msgspec
import pytest

from claimvoice.contracts import CallMode, LineRuntime, MemoryCallSink, Speaker
from claimvoice.dialogue.fakes import MemoryPolicyDirectory, YamlPlaybook
from claimvoice.dialogue.machine import CallEngine, EngineConfig
from claimvoice.schemas import voice as wire
from claimvoice.voice.adapters import FakeSpeechToText, FakeTextToSpeech
from claimvoice.voice.lines import LineManager
from claimvoice.voice.session import CallSession

from .helpers import BrowserPeer

HELLO = {"type": "client.hello", "mode": "browser_speech", "language": "auto", "recognition": "on_device", "voices": []}


async def _prepare(lm: LineManager, call_id: str, sink: MemoryCallSink, **kw: Any) -> None:
    await lm.prepare(
        call_id,
        org_id="org",
        mode=kw.get("mode", "browser_speech"),
        language="auto",
        region=kw.get("region", "CA-AB"),
        scenario=kw.get("scenario"),
        caller_phone="+14035550142",
        sink=sink,
        policies=MemoryPolicyDirectory(),
        playbook=YamlPlaybook(),
        max_seconds=360,
    )


def test_line_manager_is_a_line_runtime():
    assert isinstance(LineManager(), LineRuntime)


@pytest.mark.slow
async def test_browser_call_over_smallwebrtc_data_channel():
    lm, sink = LineManager(), MemoryCallSink()
    await _prepare(lm, "rtc-1", sink)
    peer = BrowserPeer()
    try:
        sdp, typ = await peer.offer()
        answer = await lm.answer_offer("rtc-1", sdp, typ, None, False)
        assert answer["type"] == "answer" and answer["pcId"]
        await peer.accept(answer)
        peer.send(HELLO)
        ready = await peer.until("call.ready")
        wire.server_decoder.decode(json.dumps(ready))
        greet = await peer.until("line.say")
        assert "recorded" in greet["text"] and greet["voiceLang"] == "en-CA"
        peer.send({"type": "line.spoken", "turnId": greet["turnId"], "event": "end", "atMs": 5000})
        for text in ["Hi, the wind last night tore up my house.", "Yes, that's fine."]:
            peer.send({"type": "caller.text", "text": text, "final": True, "language": "en"})
            say = await peer.until("line.say")
            peer.send({"type": "line.spoken", "turnId": say["turnId"], "event": "end", "atMs": 1})
        metrics = await peer.until("turn.metrics")
        assert metrics["totalMs"] < 800
        await asyncio.sleep(1.5)  # let some microphone audio reach the recording
        peer.send({"type": "caller.hangup"})
        ended = await peer.until("call.ended")
        wire.server_decoder.decode(json.dumps(ended))
        assert ended["reason"] == "caller_hung_up"
    finally:
        await peer.close()
        await lm.shutdown()
    closing = sink.of("closed")[0]
    assert closing.recording_path == "rtc-1.wav" and closing.recording_seconds and closing.recording_seconds > 0.5


async def test_every_server_message_matches_the_wire_schema():
    sent: list[dict[str, Any]] = []
    lm, sink = LineManager(), MemoryCallSink()
    await _prepare(lm, "wire-1", sink, mode="typed")
    line = lm.lines["wire-1"]

    async def capture(msg: dict[str, Any]) -> None:
        sent.append(msg)

    line.session.send_json = capture
    await line.session.on_client_message({**HELLO, "mode": "typed"})
    for text in [
        "Hi, the wind just smashed our skylight.",
        "Yes.",
        "LM-AB-187342",
        "September twelfth, 1984.",
        "My card is 4111 1111 1111 1111",
        "Can I talk to a person?",
    ]:
        await line.session.on_client_message({"type": "caller.text", "text": text, "final": True, "language": "en"})
    await line.session.on_client_message(
        {"type": "caller.text", "text": "my card four one one one", "final": False, "language": "en"}
    )
    await lm.hang_up("wire-1", reason="completed", by_user_id=None)
    kinds = {m["type"] for m in sent}
    assert {
        "call.ready",
        "line.say",
        "transcript.turn",
        "call.stage",
        "claim_file.slot",
        "call.flag",
        "call.notice",
        "call.handoff",
        "call.ended",
        "transcript.partial",
    } <= kinds
    for m in sent:
        wire.server_decoder.decode(json.dumps(m))
    blob = json.dumps(sent)
    assert "4111" not in blob and "four one one one" not in blob
    flags = [m["flag"]["kind"] for m in sent if m["type"] == "call.flag"]
    assert set(flags) <= {"urgent_safety", "card_number_removed", "language_switched"}
    await lm.shutdown()


class FakeSocket:
    def __init__(self, frames: list[dict[str, Any]]) -> None:
        self.frames = list(frames)
        self.text: list[dict[str, Any]] = []
        self.binary: list[bytes] = []

    async def receive(self) -> dict[str, Any]:
        await asyncio.sleep(0)
        if self.frames:
            return self.frames.pop(0)
        return {"type": "websocket.disconnect"}

    async def send_text(self, data: str) -> None:
        self.text.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.binary.append(data)


async def test_websocket_fallback_carries_the_same_messages():
    lm, sink = LineManager(), MemoryCallSink()
    await _prepare(lm, "ws-1", sink)
    frames = [
        {"type": "websocket.receive", "text": json.dumps(HELLO)},
        {"type": "websocket.receive", "bytes": b"\x00\x00" * 320},  # 20 ms of silence
        {
            "type": "websocket.receive",
            "text": json.dumps({"type": "caller.text", "text": "Yes, that's fine.", "final": True, "language": "en"}),
        },
    ]
    sock = FakeSocket(frames)
    await lm.run_websocket("ws-1", sock)
    kinds = [m["type"] for m in sock.text]
    assert kinds[0] == "call.ready" and "line.say" in kinds
    assert sink.of("consent")[0].answer == "given"
    await lm.shutdown()


async def test_voice_mode_speaks_with_tts_and_stops_on_barge_in():
    sink = MemoryCallSink()
    engine = CallEngine(
        EngineConfig("voice-1", "org", CallMode.VOICE, region="CA-AB", hold_line_turns=True),
        sink=sink,
        policies=MemoryPolicyDirectory(),
        playbook=YamlPlaybook(),
    )
    stt = FakeSpeechToText()
    stt.queue(["Hi, the wind last night tore up my house.", "Yes, that's fine."])
    audio: list[bytes] = []
    sent: list[dict[str, Any]] = []

    async def send_audio(pcm: bytes) -> None:
        audio.append(pcm)
        await asyncio.sleep(0.001)

    async def send_json(msg: dict[str, Any]) -> None:
        sent.append(msg)

    session = CallSession(
        engine, CallMode.VOICE, stt=stt, tts=FakeTextToSpeech(), send_json=send_json, send_audio=send_audio
    )
    await session.start()
    await asyncio.sleep(0.05)
    assert audio, "the greeting is spoken"
    assert session.speaking_turn is not None
    await session.caller_started_speaking()  # the caller talks over the greeting
    assert any(m["type"] == "line.stop" and m["reason"] == "barge_in" for m in sent)
    assert session.speaking_turn is None
    await session.caller_audio_segment(b"\x00\x00" * 1600, 16000)
    await asyncio.sleep(0.05)
    metrics = [m for m in sent if m["type"] == "turn.metrics"]
    assert metrics and metrics[0]["sttMs"] >= 200 and metrics[0]["firstAudioMs"] < 50
    assert not [t for t in sink.of("turn") if t.speaker is Speaker.LINE]  # all-party region: held until consent
    await session.caller_audio_segment(b"\x00\x00" * 1600, 16000)
    await asyncio.sleep(0.05)
    assert next(t for t in sink.of("turn") if t.speaker is Speaker.LINE).interrupted
    session._stop_speaking()


async def test_adopted_demo_line_carries_on_and_answers_a_whisper():
    lm, sink = LineManager(), MemoryCallSink()
    await lm.adopt_sample_line(
        "line-1",
        org_id="org",
        scenario="calgary-windstorm",
        resume_after_turn=7,
        sink=sink,
        policies=MemoryPolicyDirectory(),
        playbook=YamlPlaybook(),
    )
    line = lm.lines["line-1"]
    assert lm.is_live("line-1") and line.engine.stage.value == "loss_details"
    assert sink.events == []  # the replay never reaches the platform
    import claimvoice.voice.lines as lines_mod

    lines_mod.SCRIPT_PACE_SECONDS = 0.01
    await lm.whisper("line-1", "Ask if the garage skylight is damaged too", from_name="Renée Kowalchuk")
    for _ in range(100):
        await asyncio.sleep(0.02)
        if line.engine.values().get("extra_notes"):
            break
    asked = [t.text for t in sink.of("turn") if t.speaker is Speaker.LINE]
    assert any("Is the garage skylight damaged too?" in t for t in asked)
    assert "garage" in line.engine.values()["extra_notes"]
    await lm.shutdown()


async def test_take_over_say_and_hand_back_through_line_control():
    lm, sink = LineManager(), MemoryCallSink()
    await _prepare(lm, "sup-1", sink, mode="typed")
    s = lm.lines["sup-1"].session
    for text in ["Hi, my fence blew down.", "Yes."]:
        await s.caller_final(text)
    await lm.take_over("sup-1", user_id="u1", name="Renée Kowalchuk")
    turn_id = await lm.say_as_person("sup-1", "Hi, it's Renée from Larkspur.", user_id="u1", name="Renée Kowalchuk")
    assert any(t.turn_id == turn_id and t.speaker is Speaker.PERSON for t in sink.of("turn"))
    await lm.hand_back("sup-1", user_id="u1")
    assert lm.lines["sup-1"].engine.stage.value == "identity"
    await lm.hang_up("sup-1", reason="completed", by_user_id="u1")
    assert not lm.is_live("sup-1")
    await lm.shutdown()


def test_wire_schema_decodes_route_on_call_ended():
    msg = {
        "type": "call.ended",
        "reason": "completed",
        "claimNumber": "CV-26-01842",
        "summary": "s",
        "nextSteps": [],
        "route": {
            "route": "fast_track",
            "label": "Fast-track",
            "reasons": [{"text": "Nothing is open to the weather", "atSeconds": 41.0}],
        },
    }
    out = wire.server_decoder.decode(msgspec.json.encode(msg))
    assert out.route is not None and out.route.reasons[0].at_seconds == 41.0
