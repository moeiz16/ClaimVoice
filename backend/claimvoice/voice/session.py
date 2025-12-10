"""One call on the line, independent of the transport.

`CallSession` sits between a transport (SmallWebRTC data channel and audio track, the WebSocket fallback, or no
transport at all for scripted demo lines) and the dialogue engine:

* client messages in (docs/API_CONTRACT.md §4.3): `client.hello`, `caller.text` (interim -> caption only, final ->
  the engine), `caller.barge_in`, `line.spoken`, `caller.hangup`;
* caller audio in (`voice` mode): segments cut by the VAD go to speech-to-text, then the engine;
* everything the engine says out: `line.say` (and synthesised audio in `voice` mode), `transcript.turn`,
  `claim_file.slot`, `call.stage`, `call.flag` (caller-safe kinds only), `call.notice`, `call.handoff`, `call.ended`,
  `line.stop`, `turn.metrics`;
* timing per caller turn, reported to the platform as `TurnLatency`.

Card numbers are removed from interim captions too, before they reach anyone.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from claimvoice import clock
from claimvoice.contracts import CallMode, Speaker
from claimvoice.dialogue.machine import (
    CallEngine,
    CallerTurnOut,
    EndedOut,
    FlagOut,
    HandoffOut,
    HushOut,
    MetricsOut,
    Notice,
    Out,
    Say,
    SlotOut,
    StageOut,
    StopOut,
)
from claimvoice.dialogue.slots import SLOT_CATALOG
from claimvoice.nlu.redaction import redact_card_numbers
from claimvoice.voice.adapters import SpeechToText, TextToSpeech
from claimvoice.voice.recorder import Recorder

log = structlog.get_logger("claimvoice.voice")

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendAudio = Callable[[bytes], Awaitable[None]]
CALLER_FLAGS = {"urgent_safety", "card_number_removed", "language_switched"}
VAD_STOP_MS = 200  # Silero stop_secs: the end of the caller's speech is confirmed this long after it happens
SPEAKER_LABELS = {"line": "ClaimVoice", "caller": "You", "person": "Larkspur", "system": "ClaimVoice"}
SOURCE_LABELS = {"policy_record": "from the policy", "tool": "looked up", "person": "added by a person"}


def _confidence_label(c: float | None) -> str | None:
    if c is None:
        return None
    return "sure" if c >= 0.85 else ("likely" if c >= 0.6 else "check")


def _mmss(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


@dataclass
class TurnClock:
    """Timing of the caller turn being answered (for TurnLatency)."""

    turn_id: str | None = None
    stt_ms: float = 0.0
    understand_ms: float = 0.0
    tools_ms: float = 0.0
    plan_ms: float = 0.0
    started: float = 0.0


@dataclass
class CallSession:
    engine: CallEngine
    mode: CallMode
    stt: SpeechToText | None = None
    tts: TextToSpeech | None = None
    recorder: Recorder | None = None
    send_json: SendJson | None = None
    send_audio: SendAudio | None = None
    on_ended: Callable[[], Awaitable[None]] | None = None
    language_hint: str | None = None
    hello: dict[str, Any] | None = None
    ready_sent: bool = False
    speaking_turn: str | None = None  # line turn currently being spoken (voice mode: TTS running)
    pending: TurnClock = field(default_factory=TurnClock)
    _tts_task: asyncio.Task[None] | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    latencies: list[dict[str, float]] = field(default_factory=list)
    last_activity: float = field(default_factory=time.monotonic)

    @property
    def call_id(self) -> str:
        return self.engine.call_id

    # ------------------------------------------------------------------ outbound

    async def _send(self, msg: dict[str, Any]) -> None:
        if self.send_json is not None:
            try:
                await self.send_json(msg)
            except Exception:  # the caller's connection dropping must never break the call
                log.warning("send_failed", call_id=self.call_id, type=msg.get("type"))

    def turn_wire(self, out: CallerTurnOut | Say, *, text: str | None = None) -> dict[str, Any]:
        if isinstance(out, CallerTurnOut):
            t = out.turn
            return {
                "id": t.turn_id,
                "seq": t.seq,
                "speaker": t.speaker.value,
                "speakerLabel": SPEAKER_LABELS["caller"],
                "text": t.text,
                "textEn": None,
                "language": t.language,
                "atMs": t.at_ms,
                "endMs": t.end_ms,
                "stage": t.stage,
                "confidence": t.confidence,
                "interrupted": False,
                "redactions": t.redactions,
                "flags": ["card_number_removed"] if t.redactions else [],
            }
        turn = next((x for x in self.engine.turns if x.turn_id == out.turn_id), None)
        return {
            "id": out.turn_id,
            "seq": turn.seq if turn else 0,
            "speaker": out.speaker,
            "speakerLabel": out.speaker_name or SPEAKER_LABELS.get(out.speaker, "ClaimVoice"),
            "text": text if text is not None else out.text,
            "textEn": out.text_en,
            "language": out.language,
            "atMs": out.at_ms,
            "endMs": turn.end_ms if turn else out.at_ms,
            "stage": turn.stage if turn else self.engine.stage.value,
            "confidence": None,
            "interrupted": False,
            "redactions": 0,
            "flags": [],
        }

    def slot_wire(self, out: SlotOut) -> dict[str, Any]:
        s = out.slot
        lang = self.engine.language
        spec = SLOT_CATALOG.get(s.key)
        heard = s.at_ms / 1000 if s.source == "heard" and s.turn_id else None
        return {
            "key": s.key,
            "label": spec.label(lang) if spec else s.key,
            "value": s.value,
            "display": s.display,
            "confidence": s.confidence,
            "confidenceLabel": _confidence_label(s.confidence),
            "source": s.source,
            "sourceLabel": f"▸ {_mmss(s.at_ms)}" if heard is not None else SOURCE_LABELS.get(s.source, "heard"),
            "span": {"turnId": s.turn_id, "start": s.span[0], "end": s.span[1]} if s.span and s.turn_id else None,
            "heardAtSeconds": heard,
            "changedAtSeconds": s.changed_at_ms / 1000 if s.changed_at_ms is not None else None,
            "confirmed": s.confirmed,
            "required": s.required,
            "history": [],
        }

    async def emit(self, outs: list[Out]) -> None:
        """Forward the engine's output to the caller (and the line's voice in `voice` mode)."""
        ended: EndedOut | None = None
        for o in outs:
            if isinstance(o, Say):
                await self._send(
                    {
                        "type": "line.say",
                        "turnId": o.turn_id,
                        "text": o.text,
                        "language": o.language,
                        "voiceLang": "fr-CA" if o.language == "fr" else "en-CA",
                        "interruptible": o.interruptible,
                        "expectsAnswer": o.expects_answer,
                    }
                )
                await self._send({"type": "transcript.turn", "turn": self.turn_wire(o)})
                if self.mode is CallMode.VOICE and self.tts is not None:
                    self._speak(o)
            elif isinstance(o, CallerTurnOut):
                await self._send({"type": "transcript.turn", "turn": self.turn_wire(o)})
            elif isinstance(o, SlotOut):
                await self._send({"type": "claim_file.slot", "slot": self.slot_wire(o), "progress": o.progress})
            elif isinstance(o, StageOut):
                await self._send({"type": "call.stage", "stage": o.info})
            elif isinstance(o, FlagOut):
                if o.kind in CALLER_FLAGS:
                    await self._send(
                        {
                            "type": "call.flag",
                            "flag": {
                                "kind": o.kind,
                                "label": o.label,
                                "detail": "" if o.kind == "urgent_safety" else o.detail,
                                "severity": o.severity,
                                "at": clock.now().isoformat(),
                                "turnId": o.turn_id,
                            },
                        }
                    )
            elif isinstance(o, Notice):
                await self._send({"type": "call.notice", "kind": o.kind, "text": o.text})
            elif isinstance(o, HandoffOut):
                await self._send({"type": "call.handoff", "handoff": self.handoff_wire(o)})
            elif isinstance(o, StopOut):
                self._stop_speaking()
                await self._send({"type": "line.stop", "turnId": o.turn_id, "reason": o.reason})
            elif isinstance(o, HushOut):
                if self.recorder is not None:
                    self.recorder.hush(o.start_ms, o.end_ms)
            elif isinstance(o, MetricsOut):
                self.pending.turn_id = o.turn_id
                self.pending.understand_ms = o.understand_ms
                self.pending.tools_ms = o.tools_ms
                self.pending.plan_ms = o.plan_ms
                if self.mode is not CallMode.VOICE:
                    await self._finish_latency(first_audio_ms=0.0)
            elif isinstance(o, EndedOut):
                ended = o
        if self.recorder is not None:
            self.recorder.recording = self.engine.recording
            if self.engine.consent_answer == "refused" and not self.recorder.refused:
                self.recorder.refuse()
        if ended is not None:
            await self._send(
                {
                    "type": "call.ended",
                    "reason": ended.reason,
                    "claimNumber": ended.claim_number,
                    "summary": ended.summary,
                    "nextSteps": list(ended.next_steps),
                    "route": self.route_preview(),
                }
            )
            if self.on_ended is not None:
                await self.on_ended()

    def handoff_wire(self, o: HandoffOut) -> dict[str, Any]:
        now = clock.now().isoformat()
        p = self.engine.policy
        labels = {
            "caller_asked": "Asked for a person",
            "urgent_safety": "Urgent safety",
            "distress": "Caller distressed",
            "low_confidence": "Hard to understand",
            "identity_unverified": "Identity not confirmed",
            "tool_failed": "Records unavailable",
            "consent_refused": "Declined recording",
            "supervisor": "A person took the call",
        }
        return {
            "id": o.handoff_id,
            "callId": self.call_id,
            "reason": o.reason,
            "reasonLabel": labels.get(o.reason, "A person is joining"),
            "detail": o.detail,
            "priority": o.priority,
            "state": "waiting",
            "requestedAt": now,
            "waitingSeconds": 0,
            "acceptedBy": None,
            "acceptedAt": None,
            "callerLabel": p.holder_name if p else "Unverified caller",
            "lineLabel": "ClaimVoice",
            "place": None,
            "lossTypeLabel": None,
            "language": self.engine.language,
            "summary": o.summary,
            "actionsTaken": list(o.actions_taken),
            "to": None,
            "team": "intake",
            "position": o.position,
            "expectedWaitSeconds": o.expected_wait_seconds,
        }

    def route_preview(self) -> dict[str, Any] | None:
        """The route reveal for the caller's end screen (who looks at the claim first; never a decision)."""
        if self.engine.loss_type is None or self.engine.policy is None:
            return None
        try:
            from claimvoice.voice.preview import preview_route

            return preview_route(self.engine)
        except Exception:
            log.warning("route_preview_failed", call_id=self.call_id)
            return None

    # ------------------------------------------------------------------ speaking (voice mode)

    def _speak(self, say: Say) -> None:
        self._stop_speaking()
        self.speaking_turn = say.turn_id
        self._tts_task = asyncio.create_task(self._tts(say))

    async def _tts(self, say: Say) -> None:
        assert self.tts is not None
        first = True
        started = time.perf_counter()
        try:
            async for chunk in self.tts.synthesize(say.text, language=say.language):
                if first:
                    first = False
                    await self._finish_latency(first_audio_ms=(time.perf_counter() - started) * 1000)
                if self.recorder is not None:
                    self.recorder.line_audio(chunk, self.tts.sample_rate)
                if self.send_audio is not None:
                    await self.send_audio(chunk)
        except asyncio.CancelledError:
            raise
        finally:
            if self.speaking_turn == say.turn_id:
                self.speaking_turn = None
                await self.engine.line_spoken(say.turn_id, "end")

    def _stop_speaking(self) -> None:
        if self._tts_task is not None and not self._tts_task.done():
            self._tts_task.cancel()
        self._tts_task = None
        self.speaking_turn = None

    async def _finish_latency(self, *, first_audio_ms: float) -> None:
        p = self.pending
        if p.turn_id is None:
            return
        stt = p.stt_ms + (VAD_STOP_MS if self.mode is CallMode.VOICE else 0.0)
        sample = await self.engine.report_latency(
            p.turn_id,
            stt_ms=round(stt, 2),
            understand_ms=p.understand_ms,
            tools_ms=p.tools_ms,
            plan_ms=p.plan_ms,
            first_audio_ms=round(first_audio_ms, 2),
        )
        row = {
            "sttMs": sample.stt_ms,
            "understandMs": sample.understand_ms,
            "toolsMs": sample.tools_ms,
            "planMs": sample.plan_ms,
            "firstAudioMs": sample.tts_first_audio_ms,
            "totalMs": round(sample.total_ms, 2),
        }
        self.latencies.append(row)
        await self._send({"type": "turn.metrics", "turnId": p.turn_id, **row})
        self.pending = TurnClock()

    # ------------------------------------------------------------------ inbound

    async def start(self) -> None:
        async with self._lock:
            await self.emit(await self.engine.start())

    async def send_ready(self) -> None:
        if self.ready_sent:
            return
        self.ready_sent = True
        await self._send(
            {
                "type": "call.ready",
                "callId": self.call_id,
                "mode": self.mode.value,
                "language": self.engine.language,
                "stage": self.engine.stage_info(),
            }
        )
        # replay what was said before the channel opened (the greeting) so the caller sees and hears it
        for t in self.engine.turns:
            if t.speaker is Speaker.LINE:
                say = Say(t.turn_id, t.text, t.text_en, t.language, at_ms=t.at_ms)
                await self.emit([say])

    async def on_client_message(self, msg: dict[str, Any]) -> None:
        self.last_activity = time.monotonic()
        kind = msg.get("type")
        if kind == "client.hello":
            first = self.hello is None
            self.hello = msg
            if msg.get("mode") in ("voice", "browser_speech", "typed"):
                self.mode = CallMode(msg["mode"])
            if first:
                await self.send_ready()
            return
        if kind == "caller.text":
            text = str(msg.get("text") or "")
            if not msg.get("final"):
                clean = redact_card_numbers(text).text
                await self._send({"type": "transcript.partial", "speaker": "caller", "text": clean})
                await self.engine.sink.partial(self.call_id, Speaker.CALLER, clean)
                return
            await self.caller_final(text, confidence=msg.get("confidence"), language=msg.get("language"))
            return
        if kind == "caller.barge_in":
            async with self._lock:
                await self.emit(await self.engine.barge_in(msg.get("atMs")))
            return
        if kind == "line.spoken":
            async with self._lock:
                await self.emit(
                    await self.engine.line_spoken(str(msg.get("turnId")), str(msg.get("event")), msg.get("atMs"))
                )
            return
        if kind == "caller.hangup":
            await self.hang_up("caller_hung_up")

    async def caller_final(
        self, text: str, *, confidence: float | None = None, language: str | None = None, stt_ms: float = 0.0
    ) -> None:
        if not text.strip():
            return
        async with self._lock:
            if self.speaking_turn is not None:  # the caller answered over the line: that is a barge-in
                await self.emit(await self.engine.barge_in())
            self.pending = TurnClock(stt_ms=stt_ms, started=time.perf_counter())
            outs = await self.engine.caller_turn(text, confidence=confidence, language=language, stt_ms=stt_ms)
            await self.emit(outs)

    async def caller_audio_segment(self, pcm: bytes, sample_rate: int) -> None:
        """`voice` mode: one VAD-bounded caller segment -> speech-to-text -> the engine."""
        if self.stt is None:
            return
        t0 = time.perf_counter()
        transcript = await self.stt.transcribe(pcm, sample_rate=sample_rate, language=self.engine.language)
        stt_ms = (time.perf_counter() - t0) * 1000
        await self.caller_final(
            transcript.text, confidence=transcript.confidence, language=transcript.language, stt_ms=stt_ms
        )

    async def caller_started_speaking(self) -> None:
        """Server VAD heard the caller start: barge in if the line is speaking (voice mode)."""
        self.last_activity = time.monotonic()
        if self.speaking_turn is not None and self.mode is CallMode.VOICE:
            async with self._lock:
                await self.emit(await self.engine.barge_in())

    async def hang_up(self, reason: str, *, by_person: bool = False) -> None:
        async with self._lock:
            self._stop_speaking()
            if not self.engine.ended:
                await self.emit(await self.engine.hang_up(reason, by_person=by_person))

    async def run_locked(self, fn: Callable[[], Awaitable[list[Out]]]) -> None:
        async with self._lock:
            await self.emit(await fn())
