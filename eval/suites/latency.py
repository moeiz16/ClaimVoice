"""Response-time suite: from the end of the caller's speech to the line's first audio (or first caption).

Two measurements, both offline with the deterministic fakes:
1. `voice` mode, every scripted caller turn through the call session: the Silero end-of-speech wait (0.2 s, fixed by
   the VAD's stop setting), speech-to-text, understanding, tools, planning and the first chunk of synthesised audio.
2. `browser_speech` mode over a real SmallWebRTC connection (an aiortc peer standing in for Chrome): the round trip
   from `caller.text` on the data channel to `line.say` coming back, which is when the browser starts speaking.

Gate: p95 under 800 ms for both. Cloud budgets per stage are documented in docs/ARCHITECTURE.md."""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path

from common import Gate, Report, table

from claimvoice.contracts import CallMode, MemoryCallSink
from claimvoice.dialogue.fakes import MemoryPolicyDirectory, YamlPlaybook
from claimvoice.dialogue.machine import CallEngine, EngineConfig
from claimvoice.dialogue.simulate import load_callers
from claimvoice.voice.adapters import FakeSpeechToText, FakeTextToSpeech
from claimvoice.voice.session import CallSession

SUITE = "latency"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "tests" / "voice"))
SEGMENT = b"\x00\x00" * 16000  # one second of caller audio handed to speech-to-text


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))] if xs else 0.0


async def voice_mode() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for caller in load_callers().values():
        stt = FakeSpeechToText()
        stt.queue([t.text for t in caller.turns], language=caller.language)
        engine = CallEngine(
            EngineConfig(
                f"lat-{caller.key}",
                "org",
                CallMode.VOICE,
                region=caller.region,
                caller_phone=caller.caller_phone,
                hold_line_turns=True,
            ),
            sink=MemoryCallSink(),
            policies=MemoryPolicyDirectory(),
            playbook=YamlPlaybook(),
        )
        session = CallSession(engine, CallMode.VOICE, stt=stt, tts=FakeTextToSpeech())
        await session.start()
        for _ in caller.turns:
            if session._tts_task is not None:
                await session._tts_task
            if engine.ended:
                break
            await session.caller_audio_segment(SEGMENT, 16000)
        if session._tts_task is not None:
            await session._tts_task
        rows += session.latencies
    return rows


async def webrtc_round_trips() -> list[float]:
    from helpers import BrowserPeer  # an aiortc peer standing in for the browser (backend/tests/voice)

    from claimvoice.voice.lines import LineManager

    lm = LineManager()
    caller = load_callers()["calgary-windstorm"]
    await lm.prepare(
        "latency-rtc",
        org_id="org",
        mode="browser_speech",
        language="auto",
        region=caller.region,
        scenario=None,
        caller_phone=caller.caller_phone,
        sink=MemoryCallSink(),
        policies=MemoryPolicyDirectory(),
        playbook=YamlPlaybook(),
        max_seconds=600,
    )
    peer = BrowserPeer()
    times: list[float] = []
    try:
        sdp, typ = await peer.offer()
        await peer.accept(await lm.answer_offer("latency-rtc", sdp, typ, None, False))
        peer.send(
            {
                "type": "client.hello",
                "mode": "browser_speech",
                "language": "auto",
                "recognition": "on_device",
                "voices": [],
            }
        )
        say = await peer.until("line.say")
        for turn in caller.turns:
            peer.send({"type": "line.spoken", "turnId": say["turnId"], "event": "end", "atMs": 0})
            t0 = time.perf_counter()
            peer.send({"type": "caller.text", "text": turn.text, "final": True, "language": "en"})
            say = await peer.until("line.say")
            times.append((time.perf_counter() - t0) * 1000)
            if not say.get("expectsAnswer", True):
                break
    finally:
        await peer.close()
        await lm.shutdown()
    return times


def run() -> Report:
    rows = asyncio.run(voice_mode())
    rtc = asyncio.run(webrtc_round_trips())
    totals = [r["totalMs"] for r in rows]
    stages = [
        ("Speech end confirmed + speech-to-text", "sttMs"),
        ("Understanding", "understandMs"),
        ("Tools", "toolsMs"),
        ("Planning the reply", "planMs"),
        ("First audio", "firstAudioMs"),
        ("Total", "totalMs"),
    ]
    stage_rows = [
        [
            label,
            f"{statistics.median([r[k] for r in rows]):.1f}",
            f"{pct([r[k] for r in rows], 0.95):.1f}",
            f"{max(r[k] for r in rows):.1f}",
        ]
        for label, k in stages
    ]
    gates = [
        Gate(SUITE, "voice_p95", "Voice mode: end of speech to first audio, p95 (ms)", pct(totals, 0.95), 800, "max"),
        Gate(
            SUITE,
            "webrtc_p95",
            "Browser speech over WebRTC: caller text to line caption, p95 (ms)",
            pct(rtc, 0.95),
            800,
            "max",
        ),
        Gate(SUITE, "turns_measured", "Caller turns measured", len(totals), 300, "min"),
    ]
    lines = [
        f"{len(totals)} caller turns in `voice` mode across {len(load_callers())} scripted calls (fake speech services; "
        "the 200 ms end-of-speech wait is the Silero VAD stop setting and is included).",
        "",
        *table(["Stage", "p50 (ms)", "p95 (ms)", "max (ms)"], stage_rows),
        "",
        f"Browser speech over a real SmallWebRTC data channel ({len(rtc)} turns): p50 {statistics.median(rtc):.1f} ms, "
        f"p95 {pct(rtc, 0.95):.1f} ms from `caller.text` to `line.say` (the browser then speaks locally).",
    ]
    return Report(
        gates,
        lines,
        {
            "voice": {"p50": statistics.median(totals), "p95": pct(totals, 0.95)},
            "webrtc": {"p50": statistics.median(rtc), "p95": pct(rtc, 0.95)},
            "stages": {k: pct([r[k] for r in rows], 0.95) for _, k in stages},
        },
    )
