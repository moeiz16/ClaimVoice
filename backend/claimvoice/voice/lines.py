"""`LineManager`: the voice runtime's side of the platform interface (`LineRuntime`, docs/API_CONTRACT.md Part 3).

One `Line` per live call, held in memory inside the API process: the dialogue engine, the call session, the caller's
transport (a SmallWebRTC leg or the WebSocket fallback, or none for a scripted demo line), the recorder and the call's
timers:

* the call ends itself after `max_seconds`, after two unanswered re-prompts, or 30 s after the caller's connection
  is lost (the browser's `ping-<ms>` keep-alive stops);
* a hand-off nobody accepts within the hand-off rules' wait offers a call-back (never for urgent safety);
* scripted demo lines (a `scenario`) play their caller's lines at a natural pace, and carry on when a supervisor
  listens (`nudge`), whispers or takes over.

Supervisor actions arrive through `LineControl` after the platform has checked permissions and written the audit
entry; the runtime never touches the database.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import structlog

from claimvoice import clock
from claimvoice.contracts import CallMode, CallSink, MemoryCallSink, OrgPlaybook, PolicyDirectory
from claimvoice.dialogue.machine import CallEngine, EngineConfig, SimClock
from claimvoice.dialogue.simulate import ScriptedCaller, load_callers
from claimvoice.dialogue.stages import Stage
from claimvoice.nlu.llm import get_understanding
from claimvoice.tools.sms import get_sms_sender
from claimvoice.tools.toolbox import Toolbox
from claimvoice.tools.weather import BundledWeather
from claimvoice.voice.adapters import get_speech_adapters
from claimvoice.voice.recorder import Recorder
from claimvoice.voice.session import CallSession

log = structlog.get_logger("claimvoice.voice")
SILENCE_SECONDS = 12.0
LOST_SECONDS = 30.0
SCRIPT_PACE_SECONDS = 6.0


@dataclass
class Line:
    call_id: str
    org_id: str
    session: CallSession
    max_seconds: int
    scenario: ScriptedCaller | None = None
    script_index: int = 0
    leg: Any = None  # WebRtcLeg
    websocket: bool = False
    tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    script_task: asyncio.Task[Any] | None = None
    started: float = field(default_factory=time.monotonic)
    adopted: bool = False

    @property
    def engine(self) -> CallEngine:
        return self.session.engine

    def connected(self) -> bool:
        if self.websocket:
            return True
        return bool(self.leg is not None and self.leg.connected())


class LineManager:
    def __init__(self) -> None:
        self.lines: dict[str, Line] = {}

    # ------------------------------------------------------------------ lifecycle

    def _toolbox(self, policies: PolicyDirectory, org_id: str) -> Toolbox:
        from claimvoice.config import get_settings

        return Toolbox(
            policies,
            org_id,
            sms=get_sms_sender(),
            weather=BundledWeather(clock.today()),
            web_origin=get_settings().web_origin,
        )

    def _recorder(self, call_id: str) -> Recorder:
        from claimvoice.config import get_settings

        return Recorder(call_id, get_settings().recordings_dir)

    async def prepare(
        self,
        call_id: str,
        *,
        org_id: str,
        mode: str,
        language: str,
        region: str | None,
        scenario: str | None,
        caller_phone: str | None,
        sink: CallSink,
        policies: PolicyDirectory,
        playbook: OrgPlaybook,
        max_seconds: int,
    ) -> None:
        caller = load_callers().get(scenario) if scenario else None
        cfg = EngineConfig(
            call_id=call_id,
            org_id=org_id,
            mode=CallMode(mode),
            language=language if language in ("en", "fr", "auto") else "auto",
            region=region or (caller.region if caller else None),
            caller_phone=caller_phone or (caller.caller_phone if caller else None),
            channel="browser",
            scenario=scenario,
            hold_line_turns=CallMode(mode) is not CallMode.TYPED,
        )
        engine = CallEngine(
            cfg,
            sink=sink,
            policies=policies,
            playbook=playbook,
            nlu=get_understanding(),
            toolbox=self._toolbox(policies, org_id),
        )
        stt, tts = get_speech_adapters()
        recorder = self._recorder(call_id)
        engine.recording_provider = recorder.finish
        session = CallSession(engine, CallMode(mode), stt=stt, tts=tts, recorder=recorder)
        line = Line(call_id, org_id, session, max_seconds, scenario=caller)
        session.on_ended = lambda: self._ended(call_id)
        self.lines[call_id] = line
        await session.start()
        line.tasks.append(asyncio.create_task(self._watch(line)))
        if caller is not None:
            line.script_task = asyncio.create_task(self._play_script(line))

    async def answer_offer(
        self, call_id: str, sdp: str, type: str, pc_id: str | None, restart_pc: bool
    ) -> Mapping[str, Any]:
        from claimvoice.config import get_settings
        from claimvoice.voice.pipeline import WebRtcLeg

        line = self._line(call_id)
        if line.leg is not None and pc_id and line.leg.pc_id == pc_id:
            return await line.leg.renegotiate(sdp, type, restart_pc)
        if line.leg is not None:
            await line.leg.close()
        ice = [s.strip() for s in get_settings().voice_ice_servers.split(",") if s.strip()]
        line.leg = WebRtcLeg(line.session, ice)
        return await line.leg.answer(sdp, type)

    async def add_ice(self, call_id: str, pc_id: str, candidates: Sequence[Mapping[str, Any]]) -> None:
        line = self._line(call_id)
        if line.leg is not None and line.leg.pc_id == pc_id:
            await line.leg.add_ice([dict(c) for c in candidates])

    async def run_websocket(self, call_id: str, socket: Any) -> None:
        from claimvoice.voice.websocket import run_websocket

        line = self._line(call_id)
        line.websocket = True
        try:
            await run_websocket(line.session, socket)
        finally:
            line.websocket = False

    async def adopt_sample_line(
        self,
        call_id: str,
        *,
        org_id: str,
        scenario: str,
        resume_after_turn: int,
        sink: CallSink,
        policies: PolicyDirectory,
        playbook: OrgPlaybook,
        answered_at: datetime | None = None,
    ) -> None:
        """Rebuild a seeded live line's state by replaying its first caller turns silently, then carry on live."""
        caller = load_callers()[scenario]
        sim = SimClock(virtual=True)
        replay_sink = MemoryCallSink()
        cfg = EngineConfig(
            call_id=call_id,
            org_id=org_id,
            mode=CallMode.BROWSER_SPEECH,
            language="auto",
            region=caller.region,
            caller_phone=caller.caller_phone,
            channel="demo_line",
            scenario=scenario,
            hold_line_turns=False,
        )
        engine = CallEngine(
            cfg,
            sink=replay_sink,
            policies=policies,
            playbook=playbook,
            toolbox=self._toolbox(policies, org_id),
            sim_clock=sim,
        )
        await engine.start()
        played = 0
        for turn in caller.turns[:resume_after_turn]:
            sim.advance(turn.pause_ms)
            await engine.caller_turn(turn.text, confidence=0.95)
            played += 1
        # from here on the line is live: real time, the platform's sink, the same engine state
        if answered_at is not None:
            # Keep the stored call's start, so new turns and whispers share one timeline with the seeded turns.
            answered = answered_at if answered_at.tzinfo else answered_at.replace(tzinfo=UTC)
            sim.advance(max(0, int((clock.now() - answered).total_seconds() * 1000) - sim.now_ms()))
            engine.answered_at = answered
        else:
            engine.answered_at = clock.now() - timedelta(milliseconds=sim.now_ms())
        sim.go_live()
        engine.sink = sink
        session = CallSession(engine, CallMode.BROWSER_SPEECH)
        line = Line(call_id, org_id, session, max_seconds=60 * 60, scenario=caller, script_index=played, adopted=True)
        session.on_ended = lambda: self._ended(call_id)
        self.lines[call_id] = line

    async def nudge(self, call_id: str) -> None:
        line = self.lines.get(call_id)
        if line is None or line.scenario is None or line.engine.ended:
            return
        if line.script_task is None or line.script_task.done():
            line.script_task = asyncio.create_task(self._play_script(line))

    async def shutdown(self) -> None:
        for line in list(self.lines.values()):
            await self._close_line(line)
        self.lines.clear()

    # ------------------------------------------------------------------ LineControl

    def is_live(self, call_id: str) -> bool:
        line = self.lines.get(call_id)
        return line is not None and not line.engine.ended

    async def whisper(self, call_id: str, text: str, *, from_name: str) -> None:
        line = self._line(call_id)
        await line.session.run_locked(lambda: line.engine.whisper(text, from_name=from_name))
        await self.nudge(call_id)  # a scripted line answers at its next turn

    async def take_over(self, call_id: str, *, user_id: str, name: str) -> None:
        line = self._line(call_id)
        if line.script_task is not None:
            line.script_task.cancel()
        await line.session.run_locked(lambda: line.engine.take_over(user_id=user_id, name=name))

    async def say_as_person(self, call_id: str, text: str, *, user_id: str, name: str) -> str:
        line = self._line(call_id)
        turn_id = ""

        async def go() -> list[Any]:
            nonlocal turn_id
            turn_id, outs = await line.engine.say_as_person(text, user_id=user_id, name=name)
            return outs

        await line.session.run_locked(go)
        return turn_id or str(uuid.uuid4())

    async def hand_back(self, call_id: str, *, user_id: str) -> None:
        line = self._line(call_id)
        await line.session.run_locked(lambda: line.engine.hand_back(user_id=user_id))
        await self.nudge(call_id)

    async def hang_up(self, call_id: str, *, reason: str, by_user_id: str | None) -> None:
        line = self.lines.get(call_id)
        if line is None:
            return
        await line.session.hang_up(reason, by_person=by_user_id is not None)

    # ------------------------------------------------------------------ internals

    def _line(self, call_id: str) -> Line:
        line = self.lines.get(call_id)
        if line is None:
            raise LookupError(call_id)
        return line

    async def _ended(self, call_id: str) -> None:
        line = self.lines.get(call_id)
        if line is not None:
            asyncio.get_running_loop().call_later(2.0, lambda: asyncio.ensure_future(self._close_line(line)))

    async def _close_line(self, line: Line) -> None:
        for t in [*line.tasks, line.script_task]:
            if t is not None and not t.done() and t is not asyncio.current_task():
                t.cancel()
        if line.leg is not None:
            with contextlib.suppress(Exception):
                await line.leg.close()
        self.lines.pop(line.call_id, None)

    async def _watch(self, line: Line) -> None:
        """Timers: the call's maximum length, silence after a question, a lost connection, a hand-off wait."""
        lost_since: float | None = None
        handoff_since: float | None = None
        offered = False
        try:
            while not line.engine.ended:
                await asyncio.sleep(1.0)
                now = time.monotonic()
                s, e = line.session, line.engine
                if now - line.started > line.max_seconds:
                    await s.hang_up("max_time")
                    break
                if line.leg is not None or line.websocket:
                    if line.connected():
                        lost_since = None
                    else:
                        lost_since = lost_since or now
                        if now - lost_since > LOST_SECONDS:
                            await s.hang_up("connection_lost")
                            break
                if e.stage is Stage.HANDOFF and e.taken_over_by is None:
                    handoff_since = handoff_since or now
                    if not offered and now - handoff_since > e.rules.max_wait_seconds:
                        offered = True
                        await s.run_locked(e.handoff_timeout)
                else:
                    handoff_since, offered = None, False
                waiting = (
                    line.scenario is None
                    and s.hello is not None
                    and e.stage not in (Stage.HANDOFF, Stage.ENDED)
                    and e.pending_line is None
                    and s.speaking_turn is None
                )
                if waiting and now - s.last_activity > SILENCE_SECONDS:
                    s.last_activity = now
                    await s.run_locked(e.silence)
        except asyncio.CancelledError:
            pass

    async def _play_script(self, line: Line) -> None:
        """A scripted caller (demo line or `scenario`) says its next lines at a natural pace."""
        caller = line.scenario
        if caller is None:
            return
        s, e = line.session, line.engine
        try:
            while not e.ended and line.script_index < len(caller.turns):
                await asyncio.sleep(SCRIPT_PACE_SECONDS if line.adopted else 2.5)
                if e.taken_over_by is not None:
                    return
                if e.pending_line is not None:
                    await s.run_locked(lambda: e.line_spoken(e.pending_line.turn_id, "end"))  # type: ignore[union-attr]
                if e.substate == "whisper" and caller.on_whisper:
                    await s.caller_final(caller.on_whisper, confidence=0.95)
                    continue
                turn = caller.turns[line.script_index]
                line.script_index += 1
                await s.caller_final(turn.text, confidence=0.95)
        except asyncio.CancelledError:
            pass


@cache
def get_line_manager() -> LineManager:
    """The process-wide line manager (one per API process)."""
    return LineManager()
