"""`CallScorer` (docs/API_CONTRACT.md §1.9): every finished call scored against the rubric (`qa/rubric.py`).

Rules read the transcript, the call events and the claim file; two items (kind words, no promises) also go through a
language check (`qa/language.py`: rules offline, the cloud reader when configured, rules always win on promises).
Each item says whether it passed, was not applicable, or failed, with the turns that show it. A failed critical item
makes the call "failed" whatever the score. Calls go to the review queue when a critical item fails, the score is under
70, a hand-off rule applied, or by a stable 10 % sample.

Inputs (from the platform at hang-up): `turns` (retained, after purge), `events` as `{kind, atMs, data}` (the call
timeline plus a final `{kind: "ended", data: {reason}}`) and `slots` `{key: SlotRecord}`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any

from claimvoice.contracts import QaItemResult, QaResult, SlotRecord, Speaker, TurnRecord
from claimvoice.dialogue.scripts import condition_holds, load_default_scripts
from claimvoice.dialogue.slots import required_keys
from claimvoice.nlu.fake import _HANDOFF, detect_language, urgent_safety
from claimvoice.nlu.redaction import contains_card_number
from claimvoice.qa.language import LanguageChecker, RuleLanguageChecker
from claimvoice.qa.rubric import GOOD_AT, NEEDS_ATTENTION_AT, RUBRIC, RubricItem

SCORER_VERSION = "qa-rules-2"
HANDOFF_LATE_MS = 30_000  # a person must be asked for within 30 s of a hand-off rule applying
_CONSENT_ASK = re.compile(r"\b(recorded|recording|enregistr\w+)\b", re.I)
_LOSS_STAGES = {"loss_type", "loss_details", "photos", "coverage", "read_back", "wrap_up"}
_CLAIM_NUMBER = re.compile(r"\bCV-\d{2}-\d{5}\b")


@dataclass(frozen=True, slots=True)
class _Verdict:
    passed: bool | None
    note: str
    evidence: tuple[str, ...] = ()
    fraction: float | None = None  # partial credit (required fields)
    method: str = "rule"


def _line_turns(turns: Sequence[TurnRecord]) -> list[TurnRecord]:
    return [t for t in turns if t.speaker in (Speaker.LINE, Speaker.PERSON)]


def _events(events: Sequence[Mapping[str, Any]], kind: str) -> list[Mapping[str, Any]]:
    return [e for e in events if e.get("kind") == kind]


def _stages_reached(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]]) -> set[str]:
    reached = {t.stage for t in turns}
    reached |= {str(e.get("data", {}).get("stage")) for e in _events(events, "stage")}
    return reached


def check_consent_first(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], **_: Any) -> _Verdict:
    lines = _line_turns(turns)
    ask = next((t for t in lines if _CONSENT_ASK.search(t.text)), None)
    first_loss = next((t for t in lines if t.stage in _LOSS_STAGES or t.stage in ("identity", "safety")), None)
    if ask is None:
        if not lines:
            return _Verdict(None, "No line turns were kept.")
        return _Verdict(False, "Recording consent was never asked.", (lines[0].turn_id,))
    if first_loss is not None and first_loss.seq < ask.seq:
        return _Verdict(
            False,
            "A question about the claim came before recording consent was asked.",
            (first_loss.turn_id, ask.turn_id),
        )
    return _Verdict(True, "Recording consent was the first thing asked.", (ask.turn_id,))


def check_consent_rule(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], **_: Any) -> _Verdict:
    consent = [
        e for e in _events(events, "consent") if e.get("data", {}).get("answer") in ("given", "refused", "not_required")
    ]
    rule = next((e["data"].get("rule") for e in _events(events, "consent") if e.get("data", {}).get("rule")), None)
    if not consent:
        if rule == "all_party" and any(t.retained for t in turns if t.speaker is Speaker.CALLER):
            return _Verdict(
                False,
                "All-party region: words were kept without a yes.",
                tuple(t.turn_id for t in turns if t.speaker is Speaker.CALLER)[:1],
            )
        return _Verdict(None, "The caller never answered the consent question.")
    answer = consent[-1]["data"]["answer"]
    at = int(consent[-1].get("atMs", 0))
    if answer == "refused":
        kept = [t for t in turns if t.at_ms > at and t.retained and t.speaker is Speaker.CALLER]
        if kept:
            return _Verdict(False, "Recording continued after the caller said no.", (kept[0].turn_id,))
        return _Verdict(True, "The caller said no and recording stopped; notes only.")
    return _Verdict(
        True, f"Consent {answer.replace('_', ' ')} under the {str(rule or 'region').replace('_', '-')} rule."
    )


def check_identity(
    turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], slots: Mapping[str, SlotRecord], **_: Any
) -> _Verdict:
    verified = any(e.get("data", {}).get("verified") for e in _events(events, "identity"))
    check = slots.get("identity_check")
    if verified or (check is not None and check.value == "passed"):
        return _Verdict(True, "The policy was found and one identity detail matched.")
    if check is not None and check.value == "failed":
        return _Verdict(True, "Identity couldn't be confirmed, and the call went to a person as the rules require.")
    reached = _stages_reached(turns, events)
    if not (reached & (_LOSS_STAGES | {"safety"})):
        return _Verdict(None, "The call went to a person before identity was checked.")
    return _Verdict(False, "Claim details were taken without confirming who was calling.")


def check_required(
    turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], slots: Mapping[str, SlotRecord], **_: Any
) -> _Verdict:
    loss = slots.get("loss_type")
    reached = _stages_reached(turns, events)
    if loss is None or not (reached & {"photos", "coverage", "read_back", "wrap_up"}):
        return _Verdict(None, "The call didn't reach the end of the questions (handed to a person or ended early).")
    script = load_default_scripts().get(str(loss.value))
    values = {k: s.value for k, s in slots.items()}
    keys = [q.slot_key for q in (script.questions if script else ()) if q.required and condition_holds(q.when, values)]
    req = required_keys(keys)
    have = [k for k in req if k in slots]
    missing = [k for k in req if k not in slots]
    frac = len(have) / len(req) if req else 1.0
    if not missing:
        return _Verdict(True, f"All {len(req)} required details are in the claim file.", fraction=1.0)
    return _Verdict(False, f"{len(have)} of {len(req)} required details; missing: {', '.join(missing)}.", fraction=frac)


def check_safety(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], **_: Any) -> _Verdict:
    lines = _line_turns(turns)
    asked = next(
        (
            t
            for t in lines
            if t.stage == "safety"
            or re.search(
                r"\b(is everyone safe|anyone hurt|en sécurité|quelqu'un est-il blessé|is anyone injured)\b",
                t.text,
                re.I,
            )
        ),
        None,
    )
    urgent = any(e.get("data", {}).get("reason") == "urgent_safety" for e in _events(events, "handoff"))
    details = next((t for t in lines if t.stage in ("loss_details", "photos")), None)
    if asked is not None and (details is None or asked.seq <= details.seq):
        return _Verdict(True, "The caller was asked whether anyone is hurt or in danger.", (asked.turn_id,))
    if urgent:
        return _Verdict(True, "Urgent safety was caught and a person brought in.")
    if details is None:
        return _Verdict(None, "The call didn't reach the claim details.")
    return _Verdict(False, "Claim details were taken before asking whether everyone is safe.", (details.turn_id,))


def check_read_back(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], **_: Any) -> _Verdict:
    lines = _line_turns(turns)
    numbered = next((t for t in lines if _CLAIM_NUMBER.search(t.text)), None)
    read = next(
        (
            t
            for t in lines
            if t.stage == "read_back"
            or re.search(r"\b(here's what I have|voici ce que j'ai noté|let me read that back)\b", t.text, re.I)
        ),
        None,
    )
    if numbered is None:
        return _Verdict(None, "No claim number was given on this call.")
    if read is not None and read.seq < numbered.seq:
        return _Verdict(True, "The summary was read back before the claim number.", (read.turn_id,))
    return _Verdict(False, "The claim number was given without reading the summary back.", (numbered.turn_id,))


def check_no_cards(turns: Sequence[TurnRecord], slots: Mapping[str, SlotRecord], **_: Any) -> _Verdict:
    leaked = [t for t in turns if contains_card_number(t.text)]
    leaked_slots = [k for k, s in slots.items() if contains_card_number(f"{s.value} {s.display}")]
    if leaked or leaked_slots:
        return _Verdict(False, "A card number appears in the record.", tuple(t.turn_id for t in leaked)[:2])
    removed = [t for t in turns if t.redactions]
    if removed:
        return _Verdict(True, "A card number was started and removed before anything was kept.", (removed[0].turn_id,))
    return _Verdict(True, "No card numbers anywhere in the record.")


def check_handoff(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], **_: Any) -> _Verdict:
    handoffs = [e for e in _events(events, "handoff") if e.get("data", {}).get("state", "requested") == "requested"]
    takeovers = _events(events, "takeover")
    flags = [e for e in _events(events, "flag") if e.get("data", {}).get("kind") in ("urgent_safety", "distress")]
    triggers: list[tuple[int, str, str | None]] = []
    for f in flags:
        triggers.append((int(f.get("atMs", 0)), str(f["data"]["kind"]), f["data"].get("turnId")))
    for t in turns:
        if t.speaker is Speaker.CALLER and (_HANDOFF.search(t.text)):
            triggers.append((t.end_ms, "caller_asked", t.turn_id))
        elif t.speaker is Speaker.CALLER and urgent_safety(t.text) and not flags:
            triggers.append((t.end_ms, "urgent_safety", t.turn_id))
    if not triggers:
        if handoffs:
            return _Verdict(True, "A person was brought in.")
        return _Verdict(None, "No hand-off rule applied on this call.")
    first_at, kind, turn_id = min(triggers)
    reached = [int(e.get("atMs", 0)) for e in handoffs + takeovers]
    answer = min((a for a in reached if a >= first_at - 1000), default=None)
    if answer is None:
        return _Verdict(
            False,
            f"A hand-off rule applied ({kind.replace('_', ' ')}) but no person was brought in.",
            (turn_id,) if turn_id else (),
        )
    late = answer - first_at
    if late > HANDOFF_LATE_MS:
        return _Verdict(False, f"The hand-off came {round(late / 1000)} seconds late.", (turn_id,) if turn_id else ())
    return _Verdict(
        True, f"A person was brought in right away ({kind.replace('_', ' ')}).", (turn_id,) if turn_id else ()
    )


def check_language(turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], **_: Any) -> _Verdict:
    """The line answers in the caller's language (one turn of grace after the caller switches); a Québec call starts
    in French unless the caller speaks English."""
    region = next(
        (
            e["data"].get("region")
            for e in events
            if e.get("kind") in ("answered", "consent") and e.get("data", {}).get("region")
        ),
        None,
    )
    ordered = sorted(turns, key=lambda x: x.seq)
    lines = _line_turns(ordered)
    if not lines:
        return _Verdict(None, "No line turns were kept.")
    misses: list[str] = []
    caller_lang: str | None = None
    grace = 0
    for t in ordered:
        if t.speaker is Speaker.CALLER:
            lang = detect_language(t.text)
            if lang and lang != caller_lang:
                grace = 1 if caller_lang is not None else 0
                caller_lang = lang
        elif t.speaker in (Speaker.LINE, Speaker.PERSON) and caller_lang and t.language != caller_lang:
            if grace:
                grace -= 1
            else:
                misses.append(t.turn_id)
    first_caller = next((detect_language(t.text) for t in ordered if t.speaker is Speaker.CALLER), None)
    if region == "CA-QC" and lines[0].language != "fr" and first_caller != "en":
        return _Verdict(False, "A Québec call didn't start in French.", (lines[0].turn_id,))
    if misses:
        return _Verdict(False, "The call wasn't kept in the caller's language.", (misses[0],))
    return _Verdict(True, "The call stayed in the caller's language.")


def _sample(turns: Sequence[TurnRecord]) -> bool:
    key = turns[0].turn_id if turns else ""
    return int(hashlib.sha256(key.encode()).hexdigest()[:4], 16) % 10 == 0


class RubricCallScorer:
    """Rules plus a language check for every rubric item."""

    def __init__(self, language: LanguageChecker | None = None) -> None:
        self.language = language or RuleLanguageChecker()

    def verdicts(
        self, turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], slots: Mapping[str, SlotRecord]
    ) -> dict[str, _Verdict]:
        turns = sorted(turns, key=lambda t: t.seq)
        kw: dict[str, Any] = {"turns": turns, "events": events, "slots": slots}
        lang = self.language.check(turns, events)
        return {
            "consent_first": check_consent_first(**kw),
            "consent_rule": check_consent_rule(**kw),
            "identity_verified": check_identity(**kw),
            "required_fields": check_required(**kw),
            "safety_check": check_safety(**kw),
            "read_back": check_read_back(**kw),
            "empathy": _Verdict(lang.empathy, lang.empathy_note, lang.empathy_evidence, method="language_check"),
            "no_card_numbers": check_no_cards(**kw),
            "handoff_correct": check_handoff(**kw),
            "language_honoured": check_language(**kw),
            "no_promises": _Verdict(
                lang.no_promises, lang.promises_note, lang.promise_evidence, method="language_check"
            ),
        }

    def score(
        self, turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]], slots: Mapping[str, SlotRecord]
    ) -> QaResult:
        verdicts = self.verdicts(turns, events, slots)
        items: list[QaItemResult] = []
        got = possible = 0.0
        critical_failed = False
        for item in RUBRIC:
            v = verdicts[item.key]
            pts = _points(item, v)
            if v.passed is not None:
                got += pts
                possible += item.points
            if v.passed is False and item.critical:
                critical_failed = True
            items.append(QaItemResult(item.key, v.passed, pts, item.points, v.evidence, v.note, v.method))
        score = round(100.0 * got / possible, 1) if possible else 100.0
        band = (
            "failed"
            if critical_failed or score < NEEDS_ATTENTION_AT
            else ("good" if score >= GOOD_AT else "needs_attention")
        )
        handoff_rule = verdicts["handoff_correct"].passed is not None
        needs_review = critical_failed or score < NEEDS_ATTENTION_AT or handoff_rule or _sample(turns)
        return QaResult(score, band, tuple(items), needs_review, SCORER_VERSION)


def _points(item: RubricItem, v: _Verdict) -> float:
    if v.passed is None:
        return 0.0
    if v.fraction is not None:
        return round(item.points * v.fraction, 2)
    return float(item.points) if v.passed else 0.0


def events_from_engine(engine: Any) -> list[dict[str, Any]]:
    """The `{kind, atMs, data}` events the platform passes, from a `CallEngine` (eval and seed)."""
    return [*engine.events]


def slots_from_engine(engine: Any) -> dict[str, SlotRecord]:
    return {
        k: SlotRecord(k, s.value, s.display, s.confidence, s.source, s.turn_id, s.span, s.confirmed)
        for k, s in engine.slots.items()
    }


@cache
def get_call_scorer() -> RubricCallScorer:
    """The process-wide scorer: rules, plus the cloud language check when LLM_FAKE=false and a key is set."""
    from claimvoice.nlu.fake import FakeLlm
    from claimvoice.nlu.llm import get_llm
    from claimvoice.qa.language import LlmLanguageChecker

    llm = get_llm()
    return RubricCallScorer(RuleLanguageChecker() if isinstance(llm, FakeLlm) else LlmLanguageChecker(llm))
