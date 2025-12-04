"""Per-call dialogue engine (docs/API_CONTRACT.md Part 5, docs/adr/0003).

One `CallEngine` per live call. It holds the call's state in memory (stage, values heard, attempts, language, consent,
recording, the stage a hand-off interrupted) and turns each final caller turn into facts and a reply:

1. remove card numbers first (`nlu.redaction`), so nothing downstream ever sees them;
2. ask language understanding for an intent and the values the current stage expects, each with its span;
3. check the global events in order of importance: urgent safety, a request for a person, distress;
4. apply values and corrections, decide the stage event from the script's completion rules and call
   `stages.next_stage` (the only place the next stage is decided);
5. run mid-call tools through the budgeted `Toolbox`;
6. pick the next line from the script or a fixed template (`dialogue.lines`), never improvised;
7. report every fact to the platform through `CallSink`, in order, and return what to send to the caller.

The engine never touches the database and never sends anything itself: the voice runtime (or a test, the eval
harness, the seed's scripted calls) feeds it caller turns and forwards its `Out` items.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from claimvoice import clock
from claimvoice.contracts import (
    CallClosing,
    CallFlag,
    CallMode,
    CallOpened,
    CallSink,
    ConsentRecord,
    FlagKind,
    HandoffReason,
    HandoffRules,
    OrgPlaybook,
    PolicyDirectory,
    PolicyMatch,
    Script,
    ScriptQuestion,
    SlotRecord,
    Speaker,
    StageChange,
    ToolCallRecord,
    TurnLatency,
    TurnRecord,
)
from claimvoice.dialogue.lines import EMPATHY_MARKERS, line
from claimvoice.dialogue.scripts import condition_holds
from claimvoice.dialogue.slots import KEY_FACTS, SLOT_CATALOG, display, required_keys
from claimvoice.dialogue.stages import DISPLAY_STEPS, SCRIPT_ORDER, STAGE_LABELS, STAGE_STEP, Event, Stage, next_stage
from claimvoice.dialogue.summary import read_back, summary
from claimvoice.nlu.base import Intent, LanguageUnderstanding, NluRequest, NluResult, SlotSpec, SlotValue
from claimvoice.nlu.fake import SAFETY_REASONS, FakeUnderstanding, detect_language
from claimvoice.nlu.redaction import redact_card_numbers
from claimvoice.tools.sms import mask_phone
from claimvoice.tools.toolbox import Toolbox

NLU_TIMEOUT_MS = 600
# Facts that describe the situation now; a later mention updates them without counting as a story change.
STATE_KEYS = frozenset(
    {"open_to_weather", "water_still_entering", "home_livable", "power_out", "danger_now", "mitigation_taken"}
)
SAFETY_KEYS = ("injury_reported", "injury_detail", "danger_now", "emergency_services_called", "power_out")
NOTE_KEYS = ("damage_areas", "caller_damage_estimate_band", "caller_relationship")
TOPIC_LINES = {
    "robot": "faq_robot",
    "premium": "faq_premium",
    "covered": "faq_covered",
    "deductible": "faq_deductible",
    "rental": "faq_rental",
    "contractor": "faq_contractor",
    "timeline": "faq_timeline",
    "next": "faq_next",
    "other": "faq_other",
}
FLAG_LABELS: dict[str, dict[str, str]] = {
    "urgent_safety": {"en": "Urgent safety", "fr": "Sécurité urgente"},
    "distress": {"en": "Caller distressed", "fr": "Appelant en détresse"},
    "card_number_removed": {"en": "Card number removed", "fr": "Numéro de carte retiré"},
    "low_confidence": {"en": "Hard to understand", "fr": "Difficile à comprendre"},
    "siu_signal": {"en": "Sign worth a closer look", "fr": "Signe à examiner"},
    "consent_refused": {"en": "Recording refused", "fr": "Enregistrement refusé"},
    "surge": {"en": "Storm surge", "fr": "Pointe liée à la tempête"},
    "language_switched": {"en": "Language switched", "fr": "Changement de langue"},
}
FLAG_SEVERITY = {
    "urgent_safety": "critical",
    "distress": "warning",
    "card_number_removed": "warning",
    "low_confidence": "warning",
    "siu_signal": "warning",
    "consent_refused": "info",
    "surge": "info",
    "language_switched": "info",
}
NOTICES: dict[str, dict[str, str]] = {
    "recording_on": {"en": "Recording is on.", "fr": "L'enregistrement est en cours."},
    "recording_off": {
        "en": "Recording stopped. Notes only from here.",
        "fr": "Enregistrement arrêté. Notes seulement.",
    },
    "recording_paused": {
        "en": "Recording paused while we skip that number.",
        "fr": "Enregistrement en pause pendant que nous sautons ce numéro.",
    },
    "recording_resumed": {"en": "Recording resumed.", "fr": "Enregistrement repris."},
    "card_number_removed": {"en": "Card number removed.", "fr": "Numéro de carte retiré."},
    "photo_link_sent": {"en": "Photo link sent by text.", "fr": "Lien pour les photos envoyé par texto."},
    "waiting_for_person": {"en": "Connecting you with a person…", "fr": "Mise en contact avec une personne…"},
    "person_joined": {"en": "A person from Larkspur joined the call.", "fr": "Une personne de Larkspur s'est jointe."},
    "back_with_line": {"en": "You're back with ClaimVoice.", "fr": "Vous êtes de retour avec ClaimVoice."},
    "language_switched": {"en": "Continuing in English.", "fr": "On continue en français."},
}


# ------------------------------------------------------------------ what the engine asks the runtime to send


@dataclass(frozen=True, slots=True)
class Say:
    turn_id: str
    text: str
    text_en: str | None
    language: str
    speaker: str = "line"  # "line" | "person"
    speaker_name: str | None = None
    expects_answer: bool = True
    interruptible: bool = True
    at_ms: int = 0


@dataclass(frozen=True, slots=True)
class CallerTurnOut:
    turn: TurnRecord


@dataclass(frozen=True, slots=True)
class Notice:
    kind: str
    text: str


@dataclass(frozen=True, slots=True)
class StageOut:
    stage: str
    info: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SlotOut:
    slot: SlotState
    progress: float


@dataclass(frozen=True, slots=True)
class FlagOut:
    kind: str
    label: str
    detail: str
    severity: str
    turn_id: str | None
    at_ms: int


@dataclass(frozen=True, slots=True)
class HandoffOut:
    handoff_id: str
    reason: str
    priority: str
    detail: str
    position: int
    expected_wait_seconds: int | None
    summary: str
    actions_taken: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StopOut:
    turn_id: str
    reason: str  # "barge_in" | "takeover" | "hangup"


@dataclass(frozen=True, slots=True)
class HushOut:
    """Recording paused for this span of the caller's audio (card number)."""

    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class EndedOut:
    reason: str
    claim_number: str | None
    summary: str | None
    next_steps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricsOut:
    turn_id: str
    understand_ms: float
    tools_ms: float
    plan_ms: float


Out = (
    Say | CallerTurnOut | Notice | StageOut | SlotOut | FlagOut | HandoffOut | StopOut | HushOut | EndedOut | MetricsOut
)


@dataclass
class SlotState:
    key: str
    value: Any
    display: str
    display_en: str
    confidence: float
    source: str  # heard | policy_record | tool | person
    turn_id: str | None
    span: tuple[int, int] | None
    at_ms: int
    confirmed: bool = False
    changed_at_ms: int | None = None
    required: bool = False
    history: list[tuple[Any, str, str | None, tuple[int, int] | None]] = field(default_factory=list)

    def label(self, language: str) -> str:
        spec = SLOT_CATALOG.get(self.key)
        return spec.label(language) if spec else self.key


@dataclass(frozen=True, slots=True)
class EngineConfig:
    call_id: str
    org_id: str
    mode: CallMode = CallMode.BROWSER_SPEECH
    language: str = "auto"  # "en" | "fr" | "auto"
    region: str | None = None
    caller_phone: str | None = None
    channel: str = "browser"
    scenario: str | None = None
    org_name: str = "Larkspur Mutual"
    started_by_user_id: str | None = None
    web_origin: str = "http://localhost:3040"
    hold_line_turns: bool = False  # report a line turn when it finishes (barge-in marks it interrupted)


class SimClock:
    """A call-relative millisecond clock. Live calls use `perf_counter`; simulations advance it by speech length."""

    def __init__(self, *, virtual: bool = False) -> None:
        self.virtual = virtual
        self._t0 = time.perf_counter()
        self._ms = 0

    def now_ms(self) -> int:
        if self.virtual:
            return self._ms
        return int((time.perf_counter() - self._t0) * 1000)

    def advance(self, ms: int) -> None:
        if self.virtual:
            self._ms += max(0, int(ms))


def speech_ms(text: str) -> int:
    """Roughly how long a line takes to say (about 14 characters a second)."""
    return max(700, int(len(text) * 70))


@dataclass
class _Held:
    """Sink calls held back until the caller agrees to recording (all-party regions keep nothing before the yes)."""

    turns: list[TurnRecord] = field(default_factory=list)
    slots: list[SlotRecord] = field(default_factory=list)


class CallEngine:
    def __init__(
        self,
        cfg: EngineConfig,
        *,
        sink: CallSink,
        policies: PolicyDirectory,
        playbook: OrgPlaybook,
        nlu: LanguageUnderstanding | None = None,
        toolbox: Toolbox | None = None,
        sim_clock: SimClock | None = None,
        answered_at: datetime | None = None,
    ) -> None:
        self.cfg = cfg
        self.sink = sink
        self.policies = policies
        self.playbook = playbook
        self.nlu = nlu or FakeUnderstanding()
        self._fallback_nlu = FakeUnderstanding()
        self.tools = toolbox or Toolbox(policies, cfg.org_id, web_origin=cfg.web_origin)
        self.clock = sim_clock or SimClock()
        self.answered_at = answered_at or clock.now()
        self.call_id = cfg.call_id
        # state
        self.stage = Stage.GREETING
        self.language = cfg.language if cfg.language in ("en", "fr") else "en"
        self.language_decided = cfg.language in ("en", "fr")
        self.region = cfg.region or "CA-AB"
        self.rules = HandoffRules()
        self.consent_rule = "all_party"
        self.consent_answer = "pending"
        self.recording = False
        self.holding = True
        self.held = _Held()
        self.slots: dict[str, SlotState] = {}
        self.policy: PolicyMatch | None = None
        self.loss_type: str | None = None
        self.script: Script | None = None
        self.surge: Mapping[str, Any] | None = None
        self.surge_questions = False
        self.weather_confirms: bool | None = None
        self.resume_stage: Stage | None = None
        self.handoff_reason: str | None = None
        self.taken_over_by: str | None = None
        self.waiting_prompts = 0
        self.substate: str | None = None
        self.asked: str | None = None  # slot key the last question asked for
        self.asked_counts: dict[str, int] = {}
        self.last_prompt: tuple[str, str] | None = None  # (text, text_en)
        self.misses = 0
        self.identity_attempts = 0
        self.tool_failures = 0
        self.handoff_asks = 0
        self.silences = 0
        self.corrections_key_facts = 0
        self.redactions = 0
        self.seq = 0
        self.turns: list[TurnRecord] = []
        self.events: list[dict[str, Any]] = []  # timeline for QA ({kind, atMs, data})
        self.whispers: list[str] = []
        self.pending_whisper: str | None = None
        self.claim_number: str | None = None
        self.ended = False
        self.end_reason: str | None = None
        self.next_steps: list[str] = []
        self.pending_line: TurnRecord | None = None
        self.pending_interrupted = False
        self.latencies: list[float] = []
        self.first_name = ""
        self.said_sorry = False
        self._outs: list[Out] = []
        self._turn_tools_ms = 0.0

    # ------------------------------------------------------------------ helpers

    def now_ms(self) -> int:
        return self.clock.now_ms()

    def business_now(self) -> datetime:
        return self.answered_at + timedelta(milliseconds=self.now_ms())

    def values(self) -> dict[str, Any]:
        return {k: s.value for k, s in self.slots.items()}

    def _event(self, kind: str, data: Mapping[str, Any]) -> None:
        self.events.append({"kind": kind, "atMs": self.now_ms(), "data": dict(data)})

    def stage_info(self, stage: Stage | None = None, language: str | None = None) -> dict[str, Any]:
        st = stage or self.stage
        lang = language or self.language
        shown = st if st in STAGE_STEP else (self.resume_stage or Stage.READ_BACK)
        step = STAGE_STEP.get(shown, 7)
        nxt = DISPLAY_STEPS[step]["fr" if lang == "fr" else "en"] if step < len(DISPLAY_STEPS) else None
        next_label = (f"{nxt} ensuite" if lang == "fr" else f"{nxt} next") if nxt else None
        return {
            "key": st.value,
            "label": STAGE_LABELS[st]["fr" if lang == "fr" else "en"],
            "step": step,
            "stepLabel": DISPLAY_STEPS[step - 1]["fr" if lang == "fr" else "en"],
            "steps": len(DISPLAY_STEPS),
            "nextLabel": next_label,
        }

    def required(self) -> list[str]:
        keys = [q.slot_key for q in (self.script.questions if self.script else ()) if q.required]
        return required_keys(keys)

    def progress(self) -> float:
        req = self.required()
        if not req:
            return 0.0
        return round(sum(1 for k in req if k in self.slots) / len(req), 3)

    def missing(self) -> list[str]:
        return [SLOT_CATALOG[k].label(self.language) for k in self.required() if k not in self.slots]

    async def _sink_turn(self, turn: TurnRecord) -> None:
        if self.holding:
            self.held.turns.append(turn)
        else:
            await self.sink.turn(self.call_id, turn)

    async def _sink_slot(self, rec: SlotRecord) -> None:
        if self.holding:
            self.held.slots.append(rec)
        else:
            await self.sink.slot(self.call_id, rec)

    async def _release_held(self, *, retained: bool) -> None:
        self.holding = False
        held, self.held = self.held, _Held()
        unretained = {t.turn_id for t in held.turns} if not retained else set()
        for t in held.turns:
            await self.sink.turn(self.call_id, t if retained else replace(t, retained=False))
        for s in held.slots:
            if s.turn_id in unretained:
                s = replace(s, turn_id=None, span=None)
            await self.sink.slot(self.call_id, s)
        if not retained:
            for t in self.turns:
                if t.turn_id in unretained:
                    self.turns[self.turns.index(t)] = replace(t, retained=False)

    # ------------------------------------------------------------------ line turns

    async def _flush_line(self) -> None:
        if self.pending_line is None:
            return
        turn = self.pending_line
        if self.pending_interrupted:
            turn = replace(turn, interrupted=True, end_ms=max(turn.at_ms, self.now_ms()))
        self.pending_line, self.pending_interrupted = None, False
        self._replace_turn(turn)
        await self._sink_turn(turn)

    def _replace_turn(self, turn: TurnRecord) -> None:
        for i, t in enumerate(self.turns):
            if t.turn_id == turn.turn_id:
                self.turns[i] = turn
                return

    async def say(
        self,
        text: str,
        text_en: str | None = None,
        *,
        expects_answer: bool = True,
        speaker: Speaker = Speaker.LINE,
        speaker_name: str | None = None,
    ) -> str:
        await self._flush_line()
        self.seq += 1
        turn_id = str(uuid.uuid4())
        at = self.now_ms()
        dur = speech_ms(text)
        record = TurnRecord(
            turn_id=turn_id,
            seq=self.seq,
            speaker=speaker,
            text=text,
            language=self.language,
            at_ms=at,
            end_ms=at + dur,
            stage=self.stage.value,
            retained=self.recording or self.holding,
            speaker_name=speaker_name,
            text_en=text_en if self.language == "fr" and text_en else None,
        )
        self.turns.append(record)
        if self.cfg.hold_line_turns:
            self.pending_line = record
        else:
            await self._sink_turn(record)
        self._outs.append(
            Say(
                turn_id,
                text,
                text_en if self.language == "fr" else None,
                self.language,
                speaker.value if speaker is Speaker.PERSON else "line",
                speaker_name,
                expects_answer,
                True,
                at,
            )
        )
        if expects_answer and speaker is Speaker.LINE:
            self.last_prompt = (text, text_en or text)
        self.clock.advance(dur)
        return turn_id

    def _sorry(self) -> tuple[str, str]:
        self.said_sorry = True
        return self._l("sorry_loss")

    def _l(self, key: str, **values: str) -> tuple[str, str]:
        return line(key, self.language, **values), line(key, "en", **values)

    async def _say_parts(self, parts: Sequence[tuple[str, str]], *, expects_answer: bool = True) -> str:
        text = " ".join(p[0] for p in parts if p[0])
        text_en = " ".join(p[1] for p in parts if p[1])
        return await self.say(text, text_en, expects_answer=expects_answer)

    # ------------------------------------------------------------------ facts

    async def _stage_to(self, event: Event) -> None:
        t = next_stage(self.stage, event, resume_stage=self.resume_stage)
        if not t.changed:
            return
        previous = self.stage
        if t.stage is Stage.HANDOFF and previous is not Stage.HANDOFF:
            self.resume_stage = previous
        self.stage = t.stage
        self.substate = None
        self.misses = 0
        await self.sink.stage(self.call_id, StageChange(t.stage.value, previous.value, event.value, self.now_ms()))
        self._event("stage", {"stage": t.stage.value, "previous": previous.value, "event": event.value})
        self._outs.append(StageOut(t.stage.value, self.stage_info()))

    async def _flag(self, kind: FlagKind, detail: str, turn_id: str | None = None) -> None:
        at = self.now_ms()
        await self.sink.flag(self.call_id, CallFlag(kind, detail, at, turn_id))
        self._event("flag", {"kind": kind.value, "detail": detail, "turnId": turn_id})
        lang = self.language
        self._outs.append(
            FlagOut(kind.value, FLAG_LABELS[kind.value][lang], detail, FLAG_SEVERITY[kind.value], turn_id, at)
        )

    def _notice(self, kind: str) -> None:
        self._outs.append(Notice(kind, NOTICES[kind][self.language]))
        self._event("notice", {"kind": kind})

    async def _tool(self, rec: ToolCallRecord) -> None:
        self._turn_tools_ms += rec.elapsed_ms
        await self.sink.tool_called(self.call_id, rec)
        self._event("tool", {"tool": rec.tool, "ok": rec.ok, "timedOut": rec.timed_out, "elapsedMs": rec.elapsed_ms})

    async def set_slot(
        self,
        key: str,
        value: Any,
        *,
        source: str = "heard",
        turn_id: str | None = None,
        span: tuple[int, int] | None = None,
        confidence: float = 0.9,
        corrects: bool = False,
    ) -> SlotState | None:
        old = self.slots.get(key)
        if old is not None and old.value == value and not corrects:
            return None
        at = self.now_ms()
        state = SlotState(
            key,
            value,
            display(key, value, self.language),
            display(key, value, "en"),
            confidence,
            source,
            turn_id,
            span,
            at,
            required=key in self.required(),
        )
        if old is not None:
            state.history = [*old.history, (old.value, old.display, old.turn_id, old.span)]
            state.changed_at_ms = at
            if key in KEY_FACTS and source == "heard":
                self.corrections_key_facts += 1
        self.slots[key] = state
        rec = SlotRecord(
            key, value, state.display, confidence, source, turn_id, span, confirmed=False, corrects=old is not None
        )
        await self._sink_slot(rec)
        self._outs.append(SlotOut(state, self.progress()))
        return state

    async def _apply(self, values: Sequence[SlotValue], turn_id: str, *, allow: set[str] | None = None) -> list[str]:
        changed: list[str] = []
        for v in values:
            if allow is not None and v.key not in allow:
                continue
            if v.key in ("date_of_birth", "postal_code", "policy_number", "photo_number", "callback_number"):
                continue  # identity details and numbers are handled by their stage, never stored as heard values
            if v.key == "loss_type" and self.loss_type and v.value != self.loss_type and not v.corrects:
                continue
            existing = self.slots.get(v.key)
            if v.key == "damage_areas" and existing is not None:  # damage accumulates over the call
                seen = [x.strip() for x in str(existing.value).split(",")]
                extra = [x.strip() for x in str(v.value).split(",") if x.strip() not in seen]
                if not extra:
                    continue
                v = replace(v, value=", ".join(seen + extra), corrects=False)
                self.slots.pop(v.key)
            corrects = v.corrects or (existing is not None and existing.value != v.value)
            if existing is not None and corrects and v.key in STATE_KEYS:
                corrects = False  # a change in the situation, not a story change
                self.slots.pop(v.key)
            st = await self.set_slot(
                v.key, v.value, turn_id=turn_id, span=v.span, confidence=v.confidence, corrects=corrects
            )
            if st is not None:
                changed.append(v.key)
        return changed

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> list[Out]:
        self._outs = []
        self.rules = await self.playbook.handoff_rules(self.cfg.org_id)
        rule = await self.playbook.consent_rule(self.cfg.org_id, self.region)
        self.consent_rule = rule.rule
        if self.cfg.language == "auto" and self.region in self.rules.french_first_regions:
            self.language = "fr"
        self.holding = self.consent_rule == "all_party"
        self.recording = not self.holding
        await self.sink.call_opened(
            CallOpened(
                self.call_id,
                self.cfg.org_id,
                self.cfg.mode,
                self.language,
                self.cfg.channel,
                self.cfg.caller_phone,
                self.region,
                self.cfg.scenario,
                self.cfg.started_by_user_id,
            )
        )
        self._event("answered", {"region": self.region, "language": self.language, "rule": self.consent_rule})
        announcement = rule.announcement.get(self.language, rule.announcement.get("en", ""))
        greet = line("greeting", self.language, org=self.cfg.org_name, announcement=announcement)
        greet_en = line("greeting", "en", org=self.cfg.org_name, announcement=rule.announcement.get("en", ""))
        if not self.language_decided:
            greet += " " + line("bilingual_hint", self.language)
        self._outs.append(StageOut(self.stage.value, self.stage_info()))
        await self.say(greet, greet_en)
        await self._stage_to(Event.GREETED)
        self._event(
            "consent",
            {"rule": self.consent_rule, "answer": "asked", "recording": self.recording, "region": self.region},
        )
        return self._take()

    def _take(self) -> list[Out]:
        outs, self._outs = self._outs, []
        return outs

    # ------------------------------------------------------------------ inbound

    async def barge_in(self, at_ms: int | None = None) -> list[Out]:
        """The caller started speaking over the line: stop speaking; the next caller text answers that question."""
        if self.pending_line is not None:
            self.pending_interrupted = True
            self._outs.append(StopOut(self.pending_line.turn_id, "barge_in"))
        return self._take()

    async def line_spoken(self, turn_id: str, event: str, at_ms: int | None = None) -> list[Out]:
        if self.pending_line is not None and self.pending_line.turn_id == turn_id and event in ("end", "cancelled"):
            if event == "cancelled":
                self.pending_interrupted = True
            await self._flush_line()
        return self._take()

    async def caller_turn(
        self,
        text: str,
        *,
        confidence: float | None = None,
        language: str | None = None,
        stt_ms: float = 0.0,
        duration_ms: int | None = None,
    ) -> list[Out]:
        self._outs = []
        if self.ended:
            return []
        started = time.perf_counter()
        self._turn_tools_ms = 0.0
        await self._flush_line()
        red = redact_card_numbers(text)
        clean = red.text
        self.seq += 1
        turn_id = str(uuid.uuid4())
        at = self.now_ms()
        dur = duration_ms or max(600, len(text.split()) * 330)
        self.clock.advance(dur)
        # language: the first caller turn decides in "auto"; later a clear switch is honoured
        detected = detect_language(clean) or (language[:2] if language else None)
        switched = False
        if detected and detected != self.language and len(clean.split()) >= 3:
            if not self.language_decided:
                self.language = detected
            else:
                self.language = detected
                switched = True
        if detected:
            self.language_decided = True
        turn = TurnRecord(
            turn_id=turn_id,
            seq=self.seq,
            speaker=Speaker.CALLER,
            text=clean,
            language=self.language,
            at_ms=at,
            end_ms=at + dur,
            stage=self.stage.value,
            confidence=confidence,
            redactions=red.count,
            retained=self.recording or self.holding,
        )
        self.turns.append(turn)
        await self._sink_turn(turn)
        self._outs.append(CallerTurnOut(turn))
        if red.count:
            self.redactions += red.count
            self._outs.append(HushOut(at, at + dur))
            self._notice("recording_paused")
            await self._flag(
                FlagKind.CARD_NUMBER_REMOVED, "Caller started reading a card number; it was removed.", turn_id
            )
            self._notice("recording_resumed")
            self._event("card", {"turnId": turn_id, "count": red.count})
        if switched:
            await self._flag(
                FlagKind.LANGUAGE_SWITCHED,
                "Caller switched to French." if self.language == "fr" else "Caller switched to English.",
                turn_id,
            )
            self._notice("language_switched")
        t_nlu = time.perf_counter()
        result = await self._understand(clean)
        understand_ms = (time.perf_counter() - t_nlu) * 1000
        if self.taken_over_by is not None or self.stage is Stage.HANDOFF:
            await self._while_with_person(result, turn_id)
        else:
            await self._handle(result, turn_id, clean, card=red.count > 0, switched=switched, stt_confidence=confidence)
        plan_ms = (time.perf_counter() - started) * 1000 - understand_ms - self._turn_tools_ms
        self._outs.append(
            MetricsOut(turn_id, round(understand_ms, 2), round(self._turn_tools_ms, 2), round(max(plan_ms, 0.0), 2))
        )
        return self._take()

    async def report_latency(
        self,
        turn_id: str,
        *,
        stt_ms: float,
        understand_ms: float,
        tools_ms: float,
        plan_ms: float,
        first_audio_ms: float,
    ) -> TurnLatency:
        total = stt_ms + understand_ms + tools_ms + plan_ms + first_audio_ms
        sample = TurnLatency(turn_id, stt_ms, understand_ms, tools_ms, plan_ms, first_audio_ms, total)
        self.latencies.append(total)
        await self.sink.latency(self.call_id, sample)
        return sample

    def _expecting(self) -> tuple[list[SlotSpec], str | None]:
        st = self.stage
        specs: list[SlotSpec] = []
        asked = self.asked
        if st is Stage.CONSENT:
            specs.append(SlotSpec("loss_type", "choice"))
        elif st is Stage.IDENTITY:
            specs += [
                SlotSpec("policy_number", "policy_number"),
                SlotSpec("date_of_birth", "date"),
                SlotSpec("postal_code", "postal"),
                SlotSpec("callback_number", "phone"),
                SlotSpec("loss_type", "choice"),
            ]
        elif st is Stage.PHOTOS:
            specs.append(SlotSpec("photo_number", "phone"))
        elif st in (Stage.SAFETY, Stage.LOSS_TYPE, Stage.LOSS_DETAILS, Stage.READ_BACK):
            specs += [SlotSpec(k, SLOT_CATALOG[k].kind) for k in SAFETY_KEYS]
            specs.append(SlotSpec("loss_type", "choice"))
            if st is not Stage.SAFETY or self.loss_type:
                specs += [SlotSpec("loss_date", "date"), SlotSpec("loss_time", "time")]
            if self.script is not None:
                specs += [SlotSpec(q.slot_key, q.kind, q.required, tuple(q.choices)) for q in self.script.questions]
                specs += [SlotSpec(k, SLOT_CATALOG[k].kind, False) for k in NOTE_KEYS]
            if self.loss_type in ("collision", "theft"):
                specs.append(SlotSpec("loss_place", "address"))
            if st is Stage.READ_BACK:
                specs += [SlotSpec(k, SLOT_CATALOG[k].kind) for k in self.slots if k in SLOT_CATALOG]
        uniq: list[SlotSpec] = []
        for spec in specs:
            if all(u.key != spec.key for u in uniq):
                uniq.append(spec)
        if self.pending_whisper is not None:
            asked = "extra_notes"
            uniq.append(SlotSpec("extra_notes", "text", False))
        return uniq, asked

    async def _understand(self, text: str) -> NluResult:
        expecting, asked = self._expecting()
        req = NluRequest(
            stage=self.stage.value,
            utterance=text,
            language=self.language,
            expecting=expecting,
            filled=self.values(),
            recent_turns=[(t.speaker.value, t.text) for t in self.turns[-6:]],
            loss_type=self.loss_type,
            asked=asked,
            now=self.business_now(),
            region=(self.policy.region if self.policy else self.region),
        )
        try:
            return await asyncio.wait_for(self.nlu.understand(req), timeout=NLU_TIMEOUT_MS / 1000)
        except Exception:  # a slow or failing cloud reader never stalls the call: the rules answer
            return await self._fallback_nlu.understand(req)

    # ------------------------------------------------------------------ the turn

    async def _handle(
        self,
        r: NluResult,
        turn_id: str,
        text: str,
        *,
        card: bool,
        switched: bool,
        stt_confidence: float | None,
    ) -> None:
        pre: list[tuple[str, str]] = []
        if card:
            pre.append(self._l("card_number"))
        if switched:
            pre.append(self._l("language_switched"))
        # 1. urgent safety outranks everything, consent included
        extra = tuple(self.rules.urgent_keywords)
        from claimvoice.nlu.fake import urgent_safety

        urgent = urgent_safety(text, extra) if extra else None
        if r.urgent_safety or urgent:
            reason = r.safety_reason or (urgent[0] if urgent else "keyword")
            await self._urgent(reason, text, turn_id, r)
            return
        # 2. a request for a person
        if r.intent is Intent.HANDOFF_REQUEST:
            self.handoff_asks += 1
            if self.handoff_asks >= max(1, self.rules.asked_times):
                await self._apply(r.slots, turn_id)
                await self._handoff(HandoffReason.CALLER_ASKED, "Asked for a person.", "handoff_asked", turn_id)
                return
        # 3. distress (wording only)
        if r.distress >= self.rules.distress_threshold:
            await self._apply(r.slots, turn_id)
            await self._flag(FlagKind.DISTRESS, "Caller sounds very distressed.", turn_id)
            await self._handoff(HandoffReason.DISTRESS, "Caller sounds very distressed.", "handoff_distress", turn_id)
            return
        if r.distress >= 0.4:
            pre.append(
                (
                    "Ça a l'air vraiment stressant. On va régler ça ensemble."
                    if self.language == "fr"
                    else "That sounds really stressful. We'll sort this out together.",
                    "That sounds really stressful. We'll sort this out together.",
                )
            )
        if r.intent is Intent.REPEAT and self.last_prompt:
            await self.say(*self.last_prompt)
            return
        # 4. the stage
        handler = {
            Stage.CONSENT: self._consent,
            Stage.IDENTITY: self._identity,
            Stage.SAFETY: self._safety,
            Stage.LOSS_TYPE: self._loss_type,
            Stage.LOSS_DETAILS: self._details,
            Stage.PHOTOS: self._photos,
            Stage.COVERAGE: self._coverage,
            Stage.READ_BACK: self._read_back,
            Stage.WRAP_UP: self._wrap_up,
        }.get(self.stage)
        if handler is None:
            return
        low_stt = stt_confidence is not None and stt_confidence < 0.45
        understood = await handler(r, turn_id, text, pre)
        if understood is False or low_stt:
            self.misses += 1
            if self.misses >= self.rules.low_confidence_turns:
                await self._flag(FlagKind.LOW_CONFIDENCE, "Two turns in a row weren't understood.", turn_id)
                await self._handoff(
                    HandoffReason.LOW_CONFIDENCE,
                    "ClaimVoice couldn't understand twice in a row.",
                    "handoff_low_confidence",
                    turn_id,
                )
                return
            prompt = self.last_prompt or self._l("ask_loss")
            await self._say_parts([*pre, self._l("not_caught"), prompt])
        else:
            self.misses = 0

    async def _ask(self, pre: list[tuple[str, str]], prompt: tuple[str, str], *, asked: str | None) -> None:
        self.asked = asked
        if asked:
            self.asked_counts[asked] = self.asked_counts.get(asked, 0) + 1
        await self._say_parts([*pre, prompt])
        self.last_prompt = prompt

    def _off_script(self, r: NluResult) -> tuple[str, str] | None:
        if r.intent is Intent.OFF_SCRIPT and r.topic:
            return self._l(TOPIC_LINES.get(r.topic, "faq_other"))
        return None

    # consent ---------------------------------------------------------------

    async def _consent(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        await self._note_loss(r, turn_id, text)
        if r.intent is Intent.AFFIRM:
            self.consent_answer = "given"
            self.recording = True
            await self.sink.consent(
                self.call_id, ConsentRecord(self.consent_rule, self.region, 0, "given", True, turn_id)
            )
            self._event(
                "consent",
                {
                    "rule": self.consent_rule,
                    "answer": "given",
                    "recording": True,
                    "region": self.region,
                    "turnId": turn_id,
                },
            )
            await self._release_held(retained=True)
            self._notice("recording_on")
            await self._stage_to(Event.CONSENT_GIVEN)
            parts = [*pre, self._l("thanks")]
            if self.loss_type and not self.said_sorry:
                parts.append(self._sorry())
            await self._ask(parts, self._l("ask_policy"), asked="policy_number")
            self.substate = "need_policy"
            return True
        if r.intent is Intent.DENY:
            self.consent_answer = "refused"
            self.recording = False
            await self.sink.consent(
                self.call_id, ConsentRecord(self.consent_rule, self.region, 0, "refused", False, turn_id)
            )
            self._event(
                "consent",
                {
                    "rule": self.consent_rule,
                    "answer": "refused",
                    "recording": False,
                    "region": self.region,
                    "turnId": turn_id,
                },
            )
            await self._release_held(retained=False)
            await self._flag(FlagKind.CONSENT_REFUSED, "Caller asked not to be recorded; notes only.", turn_id)
            self._notice("recording_off")
            await self._stage_to(Event.CONSENT_REFUSED)
            self.substate = "offer_person"
            await self._ask(pre, self._l("consent_refused"), asked=None)
            return True
        parts = list(pre)
        topic = self._off_script(r)
        if topic:
            parts.append(topic)
        elif self.loss_type and not self.said_sorry:
            parts.append(self._sorry())
        await self._ask(parts, self._l("consent_reask"), asked=None)
        return bool(self.loss_type) or topic is not None or r.intent is not Intent.UNKNOWN

    async def _note_loss(self, r: NluResult, turn_id: str, text: str) -> None:
        lt = next((v for v in r.slots if v.key == "loss_type"), None)
        if lt is not None and self.loss_type is None:
            self.loss_type = str(lt.value)
            await self.set_slot("loss_type", lt.value, turn_id=turn_id, span=lt.span, confidence=lt.confidence)
            start, end = 0, len(text)
            await self.set_slot("loss_description", text.strip(), turn_id=turn_id, span=(start, end), confidence=0.7)

    # identity ---------------------------------------------------------------

    def _postal_word(self) -> str:
        region = self.policy.region if self.policy else self.region
        if self.language == "fr":
            return "code postal"
        return "ZIP code" if region.startswith("US") else "postal code"

    async def _identity(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        if self.substate == "offer_person":
            if r.intent is Intent.AFFIRM:
                await self._handoff(
                    HandoffReason.CONSENT_REFUSED,
                    "Caller declined recording and asked for a person.",
                    "handoff_consent",
                    turn_id,
                )
                return True
            self.substate = "need_policy"
            await self._ask([*pre, self._l("carry_on")], self._l("ask_policy"), asked="policy_number")
            return True
        await self._note_loss(r, turn_id, text)
        got = {v.key: v for v in r.slots}
        if self.policy is None:
            number = got.get("policy_number")
            phone = got.get("callback_number")
            if number is None and phone is None:
                topic = self._off_script(r)
                if topic:
                    await self._ask([*pre, topic], self._l("ask_policy"), asked="policy_number")
                    return True
                return False
            match, rec = await self.tools.find_policy(
                at_ms=self.now_ms(),
                policy_number=str(number.value) if number else None,
                phone=str(phone.value) if phone else None,
            )
            await self._tool(rec)
            if not rec.ok:
                self.tool_failures += 1
                if self.tool_failures >= 2:
                    await self._handoff(
                        HandoffReason.TOOL_FAILED, "Policy lookup failed twice.", "handoff_tool", turn_id
                    )
                    return True
                await self._ask(pre, self._l("lookup_failed"), asked="policy_number")
                return True
            if match is None:
                self.identity_attempts += 1
                if self.identity_attempts >= self.rules.identity_attempts:
                    await self._identity_failed(turn_id)
                    return True
                await self._ask(pre, self._l("policy_not_found"), asked="policy_number")
                return True
            self.policy = match
            self.first_name = match.holder_name.split()[0]
            if number is not None:
                await self.set_slot(
                    "policy_number",
                    match.policy_number,
                    turn_id=turn_id,
                    span=number.span,
                    confidence=number.confidence,
                )
            else:
                await self.set_slot("policy_number", match.policy_number, source="policy_record", confidence=1.0)
            self.substate = "need_detail"
        detail_dob = got.get("date_of_birth")
        detail_postal = got.get("postal_code")
        if detail_dob is None and detail_postal is None:
            if self.substate == "need_detail" and "policy_number" in got:
                await self._ask(
                    pre,
                    self._l("ask_identity", first=self.first_name, postal=self._postal_word()),
                    asked="date_of_birth",
                )
                return True
            topic = self._off_script(r)
            if topic:
                await self._ask(
                    [*pre, topic],
                    self._l("ask_identity", first=self.first_name, postal=self._postal_word()),
                    asked="date_of_birth",
                )
                return True
            return False
        ok, rec = await self.tools.verify(
            self.policy.policy_id,
            at_ms=self.now_ms(),
            date_of_birth=date.fromisoformat(str(detail_dob.value)) if detail_dob else None,
            postal_code=str(detail_postal.value) if detail_postal else None,
        )
        await self._tool(rec)
        if not ok:
            self.identity_attempts += 1
            if self.identity_attempts >= self.rules.identity_attempts:
                await self._identity_failed(turn_id)
                return True
            await self._ask(pre, self._l("identity_mismatch", postal=self._postal_word()), asked="date_of_birth")
            return True
        await self._verified(turn_id, pre)
        return True

    async def _identity_failed(self, turn_id: str) -> None:
        await self.set_slot("identity_check", "failed", source="tool", confidence=1.0)
        await self._stage_to(Event.IDENTITY_FAILED)
        self._event("identity", {"verified": False})
        await self._handoff(
            HandoffReason.IDENTITY_UNVERIFIED,
            "Couldn't confirm the caller's identity.",
            "handoff_identity",
            turn_id,
            already_in_handoff=True,
        )

    async def _verified(self, turn_id: str, pre: list[tuple[str, str]]) -> None:
        assert self.policy is not None
        p = self.policy
        await self.sink.caller_identified(self.call_id, p.policy_id, p.holder_id, p.region)
        self._event("identity", {"verified": True, "policyId": p.policy_id})
        await self.set_slot("identity_check", "passed", source="tool", confidence=1.0)
        await self.set_slot("caller_name", p.holder_name, source="policy_record", confidence=1.0)
        if p.insured_items:
            await self.set_slot("insured_item", p.insured_items[0].get("label"), source="policy_record", confidence=1.0)
        if self.cfg.caller_phone:
            await self.set_slot(
                "callback_number", mask_phone(self.cfg.caller_phone), source="policy_record", confidence=1.0
            )
        if self.region != p.region:
            self.region = p.region
        await self._stage_to(Event.IDENTITY_VERIFIED)
        await self._ask([*pre, self._l("identity_ok")], self._l("ask_safety"), asked="injury_reported")

    # safety -----------------------------------------------------------------

    async def _safety(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        await self._note_loss(r, turn_id, text)
        await self._apply(
            r.slots,
            turn_id,
            allow=set(SAFETY_KEYS)
            | {"loss_date", "loss_time"}
            | ({q.slot_key for q in self.script.questions} if self.script else set()),
        )
        if "injury_reported" not in self.slots:
            if self.substate == "clarify":
                if r.intent in (Intent.AFFIRM, Intent.DENY):
                    await self.set_slot(
                        "injury_reported",
                        r.intent is Intent.AFFIRM,
                        turn_id=turn_id,
                        span=(0, len(text)),
                        confidence=0.8,
                    )
            elif r.intent is Intent.AFFIRM:
                await self.set_slot("injury_reported", False, turn_id=turn_id, span=(0, len(text)), confidence=0.8)
            elif r.intent is Intent.DENY:
                self.substate = "clarify"
                await self._ask(pre, self._l("safety_clarify"), asked="injury_reported")
                return True
        if "injury_reported" not in self.slots:
            topic = self._off_script(r)
            if topic:
                await self._ask([*pre, topic], self._l("ask_safety"), asked="injury_reported")
                return True
            return False
        if "danger_now" not in self.slots:
            await self.set_slot("danger_now", False, source="heard", turn_id=turn_id, span=None, confidence=0.7)
        parts = list(pre)
        parts.append(self._l("injury_care") if self.slots["injury_reported"].value else self._l("glad_safe"))
        await self._stage_to(Event.SAFETY_CLEAR)
        if self.loss_type:
            await self._loss_known(turn_id, parts)
        else:
            await self._ask(parts, self._l("ask_loss"), asked="loss_type")
        return True

    # loss type and details ---------------------------------------------------

    async def _loss_type(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        await self._note_loss(r, turn_id, text)
        if not self.loss_type:
            topic = self._off_script(r)
            if topic:
                await self._ask([*pre, topic], self._l("ask_loss"), asked="loss_type")
                return True
            if self.asked_counts.get("loss_type", 0) >= 1 and self.misses == 0:
                await self._ask(pre, self._l("ask_loss_choices"), asked="loss_type")
                self.misses += 1
                return True
            return False
        await self._loss_known(turn_id, [*pre, *([self._sorry()] if not self.said_sorry else [])], heard=r.slots)
        return True

    async def _loss_known(self, turn_id: str, parts: list[tuple[str, str]], heard: Sequence[SlotValue] = ()) -> None:
        """The loss type is known (heard now, or earlier in the call): load its script, check the weather and the
        surge, then ask the first open question. Values heard in the same turn are applied first."""
        assert self.loss_type is not None
        self.script = await self.playbook.script(self.cfg.org_id, self.loss_type)
        await self._stage_to(Event.LOSS_TYPE_SET)
        if heard:
            await self._apply(heard, turn_id)
        region = self.policy.region if self.policy else self.region
        self.surge = await self.playbook.active_surge(self.cfg.org_id, region)
        self.surge_questions = bool(self.surge and self.surge.get("surgeQuestionsOn"))
        if self.loss_type in ("wind", "hail", "water"):
            kinds = {"wind": ("wind",), "hail": ("hail",), "water": ("extreme_cold", "rainfall", "flood")}
            alerts, rec = await self.tools.weather_events(
                region, self.business_now(), at_ms=self.now_ms(), kinds=kinds[self.loss_type]
            )
            await self._tool(rec)
            self.weather_confirms = bool(alerts)
            if alerts and self.surge and self.loss_type in self.surge.get("lossTypes", []):
                await self._flag(FlagKind.SURGE, f"Matches the {self.surge.get('title', 'storm')}.")
        await self._next_detail(parts)

    def _next_question(self) -> ScriptQuestion | None:
        if self.script is None:
            return None
        filled = self.values()
        for q in self.script.questions:
            if q.surge_only and not self.surge_questions:
                continue
            if q.slot_key in self.slots:
                continue
            if not condition_holds(q.when, filled):
                continue
            limit = 2 if q.required else 1
            if self.asked_counts.get(q.slot_key, 0) >= limit:
                continue
            return q
        return None

    async def _next_detail(self, parts: list[tuple[str, str]]) -> None:
        if self.pending_whisper is not None:
            q = self.pending_whisper
            await self._ask(
                parts,
                (line("whisper_question", self.language, question=q), line("whisper_question", "en", question=q)),
                asked="extra_notes",
            )
            self.substate = "whisper"
            return
        nq = self._next_question()
        if nq is None:
            await self._stage_to(Event.DETAILS_COMPLETE)
            await self._photos_prompt(parts)
            return
        prompt = (nq.prompt.get(self.language) or nq.prompt["en"], nq.prompt["en"])
        await self._ask(parts, prompt, asked=nq.slot_key)

    async def _details(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        parts = list(pre)
        if self.substate == "whisper":
            note = next((v for v in r.slots if v.key == "extra_notes"), None)
            q = self.pending_whisper or ""
            self.pending_whisper = None
            self.substate = None
            if note is not None:
                prev = self.slots.get("extra_notes")
                val = f"{q} {note.value}" if not prev else f"{prev.value}; {q} {note.value}"
                await self.set_slot("extra_notes", val, turn_id=turn_id, span=note.span, confidence=note.confidence)
            await self._apply([v for v in r.slots if v.key != "extra_notes"], turn_id)
            parts.append(self._l("noted"))
            await self._next_detail(parts)
            return True
        changed = await self._apply(r.slots, turn_id)
        corrected = [k for k in changed if self.slots[k].changed_at_ms is not None and self.slots[k].history]
        if r.intent is Intent.CORRECTION and corrected:
            k = corrected[0]
            parts.append(self._l("changed", value=self.slots[k].display))
            parts[-1] = (
                line("changed", self.language, value=self.slots[k].display),
                line("changed", "en", value=self.slots[k].display_en),
            )
        topic = self._off_script(r)
        if topic and not changed:
            parts.append(topic)
            if r.topic == "other":
                await self._note_question(text, turn_id)
        if (
            self.slots.get("injury_reported")
            and self.slots["injury_reported"].value
            and "injury_reported" in changed
            and self.stage is Stage.LOSS_DETAILS
        ):
            parts.append(self._l("injury_care"))
        if not changed and not topic:
            asked = self.asked
            aq = next((x for x in (self.script.questions if self.script else ()) if x.slot_key == asked), None)
            if aq is not None and not aq.required and self.asked_counts.get(asked or "", 0) >= 1:
                await self._next_detail(parts)  # optional question, no answer: move on
                return True
            return False
        await self._next_detail(parts)
        return True

    async def _note_question(self, text: str, turn_id: str) -> None:
        prev = self.slots.get("extra_notes")
        val = text.strip() if not prev else f"{prev.value}; {text.strip()}"
        await self.set_slot("extra_notes", val, turn_id=turn_id, span=(0, len(text)), confidence=0.6)

    # photos -----------------------------------------------------------------

    def _photo_phone(self) -> str | None:
        return self.cfg.caller_phone

    async def _photos_prompt(self, parts: list[tuple[str, str]]) -> None:
        phone = self._photo_phone()
        if phone:
            digits = "".join(c for c in phone if c.isdigit())
            await self._ask(parts, self._l("ask_photos", last4=digits[-4:]), asked="photos_promised")
            self.substate = "confirm_number"
        else:
            await self._ask(parts, self._l("ask_photos_number"), asked="photo_number")
            self.substate = "need_number"

    async def _photos(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        number = next((v for v in r.slots if v.key == "photo_number"), None)
        to: str | None = None
        if number is not None:
            to = str(number.value)
        elif self.substate == "confirm_number" and r.intent is Intent.AFFIRM:
            to = self._photo_phone()
        elif self.substate == "confirm_number" and r.intent is Intent.DENY:
            self.substate = "other_number"
            await self._ask(pre, self._l("photos_other_number"), asked="photo_number")
            return True
        elif self.substate in ("other_number", "need_number") and r.intent is Intent.DENY:
            await self.set_slot("photos_promised", False, turn_id=turn_id, span=(0, len(text)), confidence=0.8)
            await self._stage_to(Event.PHOTOS_DECLINED)
            await self._coverage_prompt([*pre, self._l("photos_declined")])
            return True
        elif r.intent is Intent.AFFIRM and self._photo_phone():
            to = self._photo_phone()
        if to is None:
            topic = self._off_script(r)
            if topic:
                await self._ask(
                    [*pre, topic], self.last_prompt or self._l("ask_photos_number"), asked="photos_promised"
                )
                return True
            return False
        sent, rec = await self.tools.send_photo_link(
            to, at_ms=self.now_ms(), call_id=self.call_id, language=self.language, org_name=self.cfg.org_name
        )
        await self._tool(rec)
        if sent is None:
            await self.set_slot("photos_promised", True, turn_id=turn_id, span=(0, len(text)), confidence=0.8)
            await self._stage_to(Event.PHOTOS_DECLINED)
            await self._coverage_prompt([*pre, self._l("photos_failed")])
            return True
        receipt, token = sent
        await self.sink.photo_link_sent(self.call_id, receipt.to_masked, token)
        self._event("photo_link", {"toMasked": receipt.to_masked})
        await self.set_slot("photos_promised", True, turn_id=turn_id, span=(0, len(text)), confidence=0.9)
        await self.set_slot("photo_link_sent_to", receipt.to_masked, source="tool", confidence=1.0)
        self._notice("photo_link_sent")
        await self._stage_to(Event.PHOTOS_SENT)
        await self._coverage_prompt([*pre, self._l("photos_sent")])
        return True

    # coverage ----------------------------------------------------------------

    async def _coverage_prompt(self, parts: list[tuple[str, str]]) -> None:
        words: tuple[str, str] | None = None
        if self.policy is not None and self.loss_type:
            lt = self.loss_type
            if lt == "water" and "water_source" in self.slots:
                lt = f"water:{self.slots['water_source'].value}"
            loss_date = (
                date.fromisoformat(self.slots["loss_date"].value)
                if "loss_date" in self.slots
                else self.business_now().date()
            )
            cov, rec = await self.tools.coverage(self.policy.policy_id, lt, loss_date, at_ms=self.now_ms())
            await self._tool(rec)
            if cov is not None:
                words = (
                    cov.plain_words.get(self.language, cov.plain_words.get("en", "")),
                    cov.plain_words.get("en", ""),
                )
                labels = ", ".join(c.label for c in cov.lines if c.included)
                if labels:
                    await self.set_slot("coverage_lines_mentioned", labels, source="tool", confidence=1.0)
                ded = next((c.deductible for c in cov.lines if c.included and c.deductible), None)
                if ded:
                    await self.set_slot("deductible_mentioned", f"{ded:,.0f}", source="tool", confidence=1.0)
        if words is None:
            words = self._l("coverage_fallback")
        await self._ask([*parts, words], self._l("coverage_check"), asked=None)

    async def _coverage(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        parts = list(pre)
        topic = self._off_script(r)
        if topic:
            parts.append(topic)
        await self._stage_to(Event.COVERAGE_EXPLAINED)
        await self._read_back_prompt(parts)
        return True

    # read-back ---------------------------------------------------------------

    async def _read_back_prompt(self, parts: list[tuple[str, str]]) -> None:
        vals = self.values()
        text = read_back(vals, self.language)
        text_en = read_back(vals, "en")
        await self._ask(
            parts,
            (line("read_back", self.language, summary=text), line("read_back", "en", summary=text_en)),
            asked=None,
        )

    async def _read_back(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        changed = (
            await self._apply(r.slots, turn_id) if r.intent in (Intent.CORRECTION, Intent.DENY, Intent.ANSWER) else []
        )
        if changed:
            await self._stage_to(Event.READ_BACK_CORRECTED)
            self._event("read_back", {"corrected": changed})
            k = changed[0]
            s = self.slots[k]
            await self._ask(
                pre,
                (
                    line("changed", self.language, value=s.display) + " " + line("read_back_rest", self.language),
                    line("changed", "en", value=s.display_en) + " " + line("read_back_rest", "en"),
                ),
                asked=None,
            )
            self.substate = None
            return True
        if r.intent is Intent.AFFIRM or (self.substate is None and r.intent is Intent.GOODBYE):
            for key, s in list(self.slots.items()):
                if s.source == "heard" and not s.confirmed:
                    s.confirmed = True
                    await self._sink_slot(
                        SlotRecord(key, s.value, s.display, s.confidence, s.source, s.turn_id, s.span, confirmed=True)
                    )
            self._event("read_back", {"confirmed": True})
            await self._stage_to(Event.READ_BACK_CONFIRMED)
            await self._wrap_up_prompt(pre)
            return True
        if r.intent in (Intent.DENY, Intent.CORRECTION):
            self.substate = "fix"
            await self._ask(pre, self._l("read_back_fix"), asked=None)
            return True
        topic = self._off_script(r)
        if topic:
            await self._ask([*pre, topic], self.last_prompt or self._l("read_back_fix"), asked=None)
            return True
        return False

    # wrap-up -----------------------------------------------------------------

    async def _wrap_up_prompt(self, parts: list[tuple[str, str]]) -> None:
        self.claim_number = await self.sink.reserve_claim_number(self.call_id)
        auto = (self.policy.line if self.policy else "") == "auto" or self.loss_type == "collision"
        surge = bool(self.surge) and self.loss_type in (self.surge or {}).get("lossTypes", [])
        key = "next_auto" if auto else ("next_property_surge" if surge else "next_property")
        nxt, nxt_en = self._l(key)
        self.next_steps = [nxt]
        await self.set_slot("next_steps_given", nxt, source="heard", confidence=1.0)
        await self.set_slot(
            "adjuster_contact_window", "2 business days" if surge else "1 business day", source="tool", confidence=1.0
        )
        await self._ask(
            parts,
            (
                line("claim_number", self.language, number=self.claim_number, next_steps=nxt),
                line("claim_number", "en", number=self.claim_number, next_steps=nxt_en),
            ),
            asked=None,
        )
        self._event("claim_number", {"number": self.claim_number})

    async def _wrap_up(self, r: NluResult, turn_id: str, text: str, pre: list[tuple[str, str]]) -> bool:
        first = self.first_name
        noted = False
        if r.intent in (Intent.ANSWER, Intent.OFF_SCRIPT) and len(text.split()) > 3:
            await self._note_question(text, turn_id)
            noted = True
        topic = self._off_script(r)
        parts = list(pre)
        if topic and r.topic != "other":
            parts.append(topic)
        key = "goodbye_noted" if noted else "goodbye"
        bye = (
            line(key, self.language, org=self.cfg.org_name, first=first).replace(", .", ".").replace(" , ", " "),
            line(key, "en", org=self.cfg.org_name, first=first).replace(", .", "."),
        )
        await self._say_parts([*parts, bye], expects_answer=False)
        await self._stage_to(Event.WRAP_UP_DONE)
        await self.close("completed")
        return True

    # hand-offs ---------------------------------------------------------------

    async def _urgent(self, reason: str, text: str, turn_id: str, r: NluResult) -> None:
        label = SAFETY_REASONS.get(reason, SAFETY_REASONS["keyword"])["en"]
        quote = text.strip()
        if len(quote) > 120:
            quote = quote[:117] + "…"
        detail = f'{label}: "{quote}". Told to get to safety and call 911.'
        await self._apply(r.slots, turn_id)
        await self.set_slot("danger_now", True, turn_id=turn_id, span=(0, len(text)), confidence=0.95)
        if reason == "injury":
            await self.set_slot("injury_reported", True, turn_id=turn_id, span=(0, len(text)), confidence=0.9)
        await self._flag(FlagKind.URGENT_SAFETY, detail, turn_id)
        await self._handoff(
            HandoffReason.URGENT_SAFETY,
            detail,
            "handoff_urgent_gas" if reason == "gas" else "handoff_urgent",
            turn_id,
            actions=("Told them to get to safety and call 911",),
        )

    async def _handoff(
        self,
        reason: HandoffReason,
        detail: str,
        line_key: str,
        turn_id: str | None,
        *,
        already_in_handoff: bool = False,
        actions: tuple[str, ...] = (),
    ) -> None:
        event = {
            HandoffReason.URGENT_SAFETY: Event.URGENT_SAFETY,
            HandoffReason.CALLER_ASKED: Event.HANDOFF_REQUESTED,
            HandoffReason.CONSENT_REFUSED: Event.HANDOFF_REQUESTED,
            HandoffReason.LOW_CONFIDENCE: Event.LOW_CONFIDENCE,
            HandoffReason.DISTRESS: Event.DISTRESS_DETECTED,
            HandoffReason.TOOL_FAILED: Event.TOOL_FAILED,
            HandoffReason.IDENTITY_UNVERIFIED: Event.HANDOFF_REQUESTED,
            HandoffReason.SUPERVISOR: Event.SUPERVISOR_TAKEOVER,
        }[reason]
        if not already_in_handoff and self.stage is not Stage.HANDOFF:
            await self._stage_to(event)
        self.handoff_reason = reason.value
        priority = (
            "urgent"
            if reason is HandoffReason.URGENT_SAFETY
            else "high"
            if reason in (HandoffReason.DISTRESS, HandoffReason.IDENTITY_UNVERIFIED)
            else "normal"
        )
        ticket = await self.sink.handoff_requested(self.call_id, reason, detail)
        self._event(
            "handoff",
            {"reason": reason.value, "priority": priority, "detail": detail, "turnId": turn_id, "state": "requested"},
        )
        text, text_en = self._l(line_key)
        if reason is not HandoffReason.SUPERVISOR:
            await self.say(text, text_en, expects_answer=False)
        self._notice("waiting_for_person")
        self._outs.append(
            HandoffOut(
                ticket.handoff_id,
                reason.value,
                priority,
                detail,
                ticket.position,
                ticket.expected_wait_seconds,
                summary(self.values(), "en"),
                actions,
            )
        )

    async def _while_with_person(self, r: NluResult, turn_id: str) -> None:
        """A person is on the call, or the caller is waiting for one: keep taking notes, stay quiet."""
        await self._apply(r.slots, turn_id)
        if r.urgent_safety and self.handoff_reason != HandoffReason.URGENT_SAFETY.value:
            reason = SAFETY_REASONS.get(r.safety_reason or "keyword", SAFETY_REASONS["keyword"])["en"]
            await self._flag(FlagKind.URGENT_SAFETY, f"{reason}.", turn_id)
        if self.substate == "callback":
            if r.intent is Intent.AFFIRM or re.search(r"call (me )?back|rappel", self.turns[-1].text, re.I):
                await self.say(*self._l("callback_booked"), expects_answer=False)
                self.next_steps = [line("callback_booked", self.language)]
                await self.close("callback_requested")
                return
            await self.hand_back(user_id="line", reason="callback_declined")
            return
        if self.taken_over_by is None and self.waiting_prompts < 1:
            self.waiting_prompts += 1
            await self.say(*self._l("waiting"), expects_answer=False)

    # ------------------------------------------------------------------ supervisor actions (LineControl)

    async def whisper(self, text: str, *, from_name: str) -> list[Out]:
        """A note to the line, never spoken as written: it becomes one question at the line's next turn."""
        self._outs = []
        q = whisper_to_question(text)
        self.whispers.append(text)
        self._event("whisper", {"text": text, "by": from_name})
        if q:
            self.pending_whisper = q
        return self._take()

    async def take_over(self, *, user_id: str, name: str) -> list[Out]:
        self._outs = []
        if self.pending_line is not None:
            self._outs.append(StopOut(self.pending_line.turn_id, "takeover"))
            self.pending_interrupted = True
            await self._flush_line()
        self.taken_over_by = name
        if self.stage is not Stage.HANDOFF:
            await self._stage_to(Event.SUPERVISOR_TAKEOVER)
            self.handoff_reason = HandoffReason.SUPERVISOR.value
        self._event("takeover", {"userId": user_id, "name": name, "state": "accepted"})
        self._notice("person_joined")
        return self._take()

    async def say_as_person(self, text: str, *, user_id: str, name: str) -> tuple[str, list[Out]]:
        self._outs = []
        red = redact_card_numbers(text).text
        turn_id = await self.say(red, red, expects_answer=False, speaker=Speaker.PERSON, speaker_name=name)
        return turn_id, self._take()

    async def hand_back(self, *, user_id: str, reason: str = "returned") -> list[Out]:
        if self.stage is not Stage.HANDOFF or self.ended:
            return self._take()
        self.taken_over_by = None
        self.waiting_prompts = 0
        resume = self.resume_stage or Stage.IDENTITY
        if resume in (Stage.GREETING, Stage.CONSENT) and self.consent_answer == "pending":
            resume = Stage.CONSENT
        await self._stage_to(Event.HANDOFF_RETURNED)
        self.resume_stage = None
        self._event("returned", {"userId": user_id, "reason": reason})
        self._notice("back_with_line")
        parts = [self._l("back_with_line")]
        await self._reprompt(parts)
        return self._take()

    async def _reprompt(self, parts: list[tuple[str, str]]) -> None:
        st = self.stage
        if st is Stage.CONSENT:
            await self._ask(parts, self._l("consent_reask"), asked=None)
        elif st is Stage.IDENTITY:
            if self.policy is None:
                await self._ask(parts, self._l("ask_policy"), asked="policy_number")
                self.substate = "need_policy"
            else:
                self.substate = "need_detail"
                await self._ask(
                    parts,
                    self._l("ask_identity", first=self.first_name, postal=self._postal_word()),
                    asked="date_of_birth",
                )
        elif st is Stage.SAFETY:
            await self._ask(parts, self._l("ask_safety"), asked="injury_reported")
        elif st is Stage.LOSS_TYPE:
            await self._ask(parts, self._l("ask_loss"), asked="loss_type")
        elif st is Stage.LOSS_DETAILS:
            for k in list(self.asked_counts):
                if k not in self.slots:
                    self.asked_counts[k] = 0
            await self._next_detail(parts)
        elif st is Stage.PHOTOS:
            await self._photos_prompt(parts)
        elif st is Stage.COVERAGE:
            await self._coverage_prompt(parts)
        elif st is Stage.READ_BACK:
            await self._read_back_prompt(parts)
        elif st is Stage.WRAP_UP:
            await self._wrap_up_prompt(parts)

    async def handoff_timeout(self) -> list[Out]:
        """No one accepted within `maxWaitSeconds`: offer a call-back (never for urgent safety)."""
        self._outs = []
        if self.stage is not Stage.HANDOFF or self.taken_over_by or self.handoff_reason == "urgent_safety":
            return []
        self.substate = "callback"
        self._event("handoff", {"state": "callback_offered"})
        await self.say(*self._l("callback_offer"))
        return self._take()

    async def silence(self) -> list[Out]:
        """The caller said nothing after a question. Two re-prompts, then the call ends."""
        self._outs = []
        if self.ended or self.stage is Stage.HANDOFF:
            return []
        self.silences += 1
        if self.silences > 2:
            await self.say(*self._l("silence_end"), expects_answer=False)
            await self._stage_to(Event.SILENCE_TIMEOUT)
            await self.close("silence")
            return self._take()
        prompt = self.last_prompt or self._l("ask_loss")
        await self._say_parts([self._l("silence"), prompt])
        return self._take()

    async def hang_up(self, reason: str = "caller_hung_up", *, by_person: bool = False) -> list[Out]:
        self._outs = []
        if self.ended:
            return []
        if self.pending_line is not None:
            self._outs.append(StopOut(self.pending_line.turn_id, "hangup"))
        if self.stage is not Stage.ENDED:
            if self.stage is Stage.HANDOFF and by_person:
                await self._stage_to(Event.HANDOFF_COMPLETED)
            else:
                await self._stage_to(Event.CALLER_HUNG_UP)
        await self.close("ended_by_person" if by_person else reason)
        return self._take()

    # ------------------------------------------------------------------ close

    def latency_p95(self) -> float | None:
        if not self.latencies:
            return None
        xs = sorted(self.latencies)
        return round(xs[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))], 1)

    async def close(
        self, reason: str, *, recording_path: str | None = None, recording_seconds: float | None = None
    ) -> None:
        if self.ended:
            return
        await self._flush_line()
        if self.holding:  # never answered consent in an all-party region: nothing is kept
            await self._release_held(retained=False)
        self.ended = True
        self.end_reason = reason
        vals = self.values()
        caller = self.policy.holder_name if self.policy else None
        text = summary(vals, self.language, caller=caller)
        text_en = summary(vals, "en", caller=caller)
        closing = CallClosing(
            reason=reason,
            ended_at_ms=self.now_ms(),
            final_stage=self.stage.value,
            recording_path=recording_path if self.recording else None,
            recording_seconds=recording_seconds if self.recording else None,
            summary=text,
            summary_en=text_en if self.language != "en" else None,
            turn_count=len(self.turns),
            latency_p95_ms=self.latency_p95(),
        )
        self._closing = closing
        self._event("ended", {"reason": reason})
        await self.sink.call_closed(self.call_id, closing)
        self._outs.append(EndedOut(reason, self.claim_number, text or None, tuple(self.next_steps)))

    # ------------------------------------------------------------------ for routing at hang-up

    def call_facts(self) -> dict[str, Any]:
        """Facts the routing checks may use that the claim file alone doesn't carry."""
        return {
            "key_fact_corrections": self.corrections_key_facts,
            "weather_confirms_loss": self.weather_confirms,
            "surge_event_match": bool(self.surge) and self.loss_type in (self.surge or {}).get("lossTypes", []),
            "card_numbers_removed": self.redactions,
            "handoff_reason": self.handoff_reason,
            "consent": self.consent_answer,
            "language": self.language,
            "region": self.region,
        }


_ASK_PREFIX = re.compile(
    r"^\s*(please\s+)?(ask|check|find out|confirm)\s+(them\s+|him\s+|her\s+)?(if|whether|about)?\s*", re.I
)
_ASK_PREFIX_FR = re.compile(r"^\s*(demande[rz]?|vérifie[rz]?)\s+(lui\s+)?(si|s'|à propos de)?\s*", re.I)
_VERB = re.compile(r"\b(is|are|was|were|has|have|did|does|do|can|will)\b", re.I)


def whisper_to_question(note: str) -> str:
    """'Ask if the garage skylight is damaged too' -> 'Is the garage skylight damaged too?'. A note that isn't an
    instruction to ask is turned into a neutral question about it."""
    text = note.strip().rstrip(".?!")
    if not text:
        return ""
    m = _ASK_PREFIX.match(text) or _ASK_PREFIX_FR.match(text)
    body = text[m.end() :] if m else text
    about = bool(m and m.group(0).strip().lower().endswith("about"))
    if about:
        return f"Can you tell me about {body}?"
    if m:
        v = _VERB.search(body)
        if v and v.start() > 0:
            subject = body[: v.start()].strip()
            rest = body[v.end() :].strip()
            verb = v.group(1).lower()
            return f"{verb.capitalize()} {subject[0].lower() + subject[1:] if subject else ''} {rest}".strip() + "?"
        return body[0].upper() + body[1:] + "?"
    return body[0].upper() + body[1:] + ("" if body.endswith("?") else "?")


__all__ = [
    "CallEngine",
    "CallerTurnOut",
    "EndedOut",
    "EngineConfig",
    "FlagOut",
    "HandoffOut",
    "HushOut",
    "MetricsOut",
    "Notice",
    "Out",
    "Say",
    "SimClock",
    "SlotOut",
    "SlotState",
    "StageOut",
    "StopOut",
    "whisper_to_question",
]

_ = (Awaitable, Callable, EMPATHY_MARKERS, SCRIPT_ORDER)
