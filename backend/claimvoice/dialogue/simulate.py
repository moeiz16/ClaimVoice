"""Scripted callers through the real engine.

`run_scenario` plays a caller from `eval/callers/<key>.yml` against a `CallEngine` and any `CallSink`. The dialogue
eval, the latency runner, the voice runtime's scripted demo lines and the platform seed all use it, so seeded
transcripts, values, spans and stages come from the same engine a live call uses.

Time is virtual by default: the call clock advances by how long each line takes to say, so turn timings look like a
real call without waiting for one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from claimvoice import clock
from claimvoice.contracts import CallMode, CallSink, MemoryCallSink, OrgPlaybook, PolicyDirectory
from claimvoice.dialogue.fakes import MemoryPolicyDirectory, YamlPlaybook
from claimvoice.dialogue.machine import CallEngine, EngineConfig, Out, SimClock
from claimvoice.nlu.base import LanguageUnderstanding
from claimvoice.tools.toolbox import Toolbox
from claimvoice.tools.weather import BundledWeather

REPO_ROOT = Path(__file__).resolve().parents[3]
CALLERS_DIR = REPO_ROOT / "eval" / "callers"
DEMO_ZONE = ZoneInfo("America/Edmonton")


def demo_moment() -> datetime:
    """Business "now" for scripted calls: the demo clock when it is installed, else the default demo moment
    (Thursday 8 January 2026, 7:42 a.m. Calgary time), so evaluations are reproducible on any date."""
    if clock.is_shifted():
        return clock.now()
    return datetime(2026, 1, 8, 7, 42, tzinfo=DEMO_ZONE)


@dataclass(frozen=True)
class CallerTurn:
    text: str
    barge_in_after_ms: int | None = None
    pause_ms: int = 400  # silence before the caller starts (after the line finished)


@dataclass(frozen=True)
class ScriptedCaller:
    key: str
    title: str
    language: str
    region: str
    caller_name: str | None
    caller_phone: str | None
    policy_number: str | None
    turns: tuple[CallerTurn, ...]
    expect: Mapping[str, Any]
    on_whisper: str | None = None  # what the caller says when the line asks a supervisor's whispered question
    mode: str = "typed"
    tags: tuple[str, ...] = ()
    surge_questions_on: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict)


def parse_caller(raw: Mapping[str, Any]) -> ScriptedCaller:
    turns = tuple(
        CallerTurn(t["text"], t.get("barge_in_after_ms"), int(t.get("pause_ms", 400))) for t in raw.get("turns", [])
    )
    return ScriptedCaller(
        key=raw["key"],
        title=raw.get("title", raw["key"]),
        language=raw.get("language", "en"),
        region=raw.get("region", "CA-AB"),
        caller_name=raw.get("caller_name"),
        caller_phone=raw.get("caller_phone"),
        policy_number=raw.get("policy_number"),
        turns=turns,
        expect=raw.get("expect", {}),
        on_whisper=raw.get("on_whisper"),
        mode=raw.get("mode", "browser_speech"),
        tags=tuple(raw.get("tags", ())),
        surge_questions_on=bool(raw.get("surge_questions_on", False)),
        raw=raw,
    )


@cache
def load_callers(directory: str | None = None) -> dict[str, ScriptedCaller]:
    root = Path(directory) if directory else CALLERS_DIR
    out: dict[str, ScriptedCaller] = {}
    for path in sorted(root.glob("*.yml")):
        c = parse_caller(yaml.safe_load(path.read_text(encoding="utf-8")))
        out[c.key] = c
    return out


@dataclass
class SimResult:
    engine: CallEngine
    caller: ScriptedCaller
    outs: list[Out]
    played: int  # caller turns played

    @property
    def values(self) -> dict[str, Any]:
        return self.engine.values()


async def run_scenario(
    scenario: str | ScriptedCaller,
    sink: CallSink | None = None,
    *,
    org_id: str = "org-demo",
    call_id: str = "call-demo",
    policies: PolicyDirectory | None = None,
    playbook: OrgPlaybook | None = None,
    nlu: LanguageUnderstanding | None = None,
    upto_caller_turn: int | None = None,
    answered_at: datetime | None = None,
    start_ms: int = 0,
    whisper_before_turn: Mapping[int, str] | None = None,
    hang_up_after: bool = True,
    toolbox: Toolbox | None = None,
) -> SimResult:
    """Play a scripted caller through the engine. `upto_caller_turn=N` stops after N caller turns and leaves the call
    open (a live demo line mid-call); otherwise the caller hangs up if the call hasn't ended by itself."""
    caller = scenario if isinstance(scenario, ScriptedCaller) else load_callers()[scenario]
    sink = sink if sink is not None else MemoryCallSink()
    policies = policies or MemoryPolicyDirectory()
    playbook = playbook or YamlPlaybook(surge_questions_on=caller.surge_questions_on)
    answered_at = answered_at or demo_moment()
    if toolbox is None:
        toolbox = Toolbox(
            policies or MemoryPolicyDirectory(),
            org_id,
            weather=BundledWeather(answered_at.astimezone(DEMO_ZONE).date()),
        )
    sim = SimClock(virtual=True)
    sim.advance(start_ms)
    mode = CallMode(caller.mode) if caller.mode in ("typed", "browser_speech", "voice") else CallMode.TYPED
    cfg = EngineConfig(
        call_id=call_id,
        org_id=org_id,
        mode=mode,
        language=caller.raw.get("call_language", "auto"),
        region=caller.region,
        caller_phone=caller.caller_phone,
        channel="test",
        scenario=caller.key,
        hold_line_turns=mode is not CallMode.TYPED,
    )
    engine = CallEngine(
        cfg,
        sink=sink,
        policies=policies,
        playbook=playbook,
        nlu=nlu,
        toolbox=toolbox,
        sim_clock=sim,
        answered_at=answered_at,
    )
    outs: list[Out] = list(await engine.start())
    played = 0
    whispers = dict(whisper_before_turn or {})
    for i, turn in enumerate(caller.turns, start=1):
        if engine.ended or (upto_caller_turn is not None and played >= upto_caller_turn):
            break
        if i in whispers:
            outs += await engine.whisper(whispers[i], from_name="Supervisor")
        text = turn.text
        if engine.substate == "whisper" and caller.on_whisper:
            text = caller.on_whisper
        if turn.barge_in_after_ms is not None and engine.pending_line is not None:
            # the caller starts talking part-way through the line's turn
            outs += await engine.barge_in()
        else:
            sim.advance(turn.pause_ms)
            if engine.pending_line is not None:
                outs += await engine.line_spoken(engine.pending_line.turn_id, "end")
        outs += await engine.caller_turn(text, confidence=0.95)
        played += 1
        if text != turn.text:  # the whispered question took this turn; the script line comes next
            outs += await engine.caller_turn(turn.text, confidence=0.95)
    if upto_caller_turn is None and hang_up_after and not engine.ended:
        outs += await engine.hang_up("caller_hung_up")
    return SimResult(engine, caller, outs, played)
