"""Rows to wire shapes for calls (docs/API_CONTRACT.md §1.6): live lines, call detail, transcript, claim file,
timeline, hand-offs and recordings. Shared by the HTTP routes, `SqlCallSink` (SSE payloads) and the line desk."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.api import labels
from claimvoice.calls.models import Call, CallEvent, CallSlot, CallTurn, Handoff, QaScoreRow, Whisper
from claimvoice.dialogue.slots import SECTIONS, SLOT_CATALOG, required_keys
from claimvoice.dialogue.stages import DISPLAY_STEPS, SCRIPT_ORDER, STAGE_LABELS, STAGE_STEP, Stage
from claimvoice.platform.models import User
from claimvoice.schemas import calls as w
from claimvoice.schemas.base import PersonRef, TextSpan
from claimvoice.schemas.claims import Moment, Recording, RecordingSegment
from claimvoice.settings.models import ScriptVersion

STEPS = len(DISPLAY_STEPS)


# ---------------------------------------------------------------- stages


def stage_info(stage: str, lang: str, resume_stage: str | None = None) -> w.StageInfo:
    try:
        s = Stage(stage)
    except ValueError:
        s = Stage.GREETING
    step_stage = s
    if s in (Stage.HANDOFF, Stage.ENDED):
        try:
            step_stage = Stage(resume_stage) if resume_stage else Stage.WRAP_UP if s is Stage.ENDED else Stage.GREETING
        except ValueError:
            step_stage = Stage.GREETING
        if step_stage in (Stage.HANDOFF, Stage.ENDED):
            step_stage = Stage.GREETING
    step = STAGE_STEP.get(step_stage, 1)
    next_label = None
    if step < STEPS and s is not Stage.ENDED:
        nxt = labels.pick(DISPLAY_STEPS[step], lang)
        next_label = f"Ensuite : {nxt}" if lang == "fr" else f"{nxt} next"
    return w.StageInfo(
        key=s.value,
        label=labels.pick(STAGE_LABELS[s], lang),
        step=step,
        step_label=labels.pick(DISPLAY_STEPS[step - 1], lang),
        steps=STEPS,
        next_label=next_label,
    )


def scripted_path(lang: str) -> list[w.StageInfo]:
    return [stage_info(s.value, lang) for s in SCRIPT_ORDER]


# ---------------------------------------------------------------- small pieces


def lang_of(value: str | None) -> str:
    return "fr" if value == "fr" else "en"


def flag_out(f: dict[str, Any], lang: str) -> w.Flag:
    kind = f.get("kind", "surge")
    at = f.get("at")
    return w.Flag(
        kind=kind,
        label=labels.pick(labels.FLAGS.get(kind), lang, kind),
        detail=f.get("detail", ""),
        severity=labels.lit(labels.FLAG_SEVERITY.get(kind, "info")),
        at=datetime.fromisoformat(at) if isinstance(at, str) else (at or clock.now()),
        turn_id=f.get("turnId"),
    )


def flags_out(call: Call, lang: str, *, siu: bool) -> list[w.Flag]:
    return [flag_out(f, lang) for f in (call.flags or []) if siu or f.get("kind") != "siu_signal"]


def caller_label(call: Call, lang: str = "en") -> str:
    if call.caller_name and call.caller_verified:
        return call.caller_name
    if call.caller_name:
        return call.caller_name
    return labels.t(lang, "Unverified caller", "Appelant non vérifié")


def line_label(call: Call) -> str | None:
    return f"Line {call.line_number}" if call.line_number and call.state != "ended" else None


def mood_out(call: Call, lang: str) -> w.Mood:
    key = (call.mood or {}).get("key", "calm")
    if key not in labels.MOODS:
        key = "calm"
    return w.Mood(key=key, label=labels.pick(labels.MOODS[key], lang), detail=(call.mood or {}).get("detail"))


def listeners_out(call: Call) -> list[w.Listener]:
    return [w.Listener(user_id=x["userId"], name=x["name"], mode=x.get("mode", "listening")) for x in call.listeners]


def duration_seconds(call: Call) -> int | None:
    if call.ended_at is None:
        return None
    return max(0, int((call.ended_at - call.answered_at).total_seconds()))


def consent_out(call: Call, lang: str) -> w.Consent:
    c = call.consent or {}
    region = c.get("region") or call.region or "CA-AB"
    rule = c.get("rule") or "all_party"
    answer = c.get("answer") or "pending"
    asked = c.get("askedAt")
    region_label = labels.region(region, lang) or region
    return w.Consent(
        rule=labels.lit(rule),
        rule_label=f"{labels.pick(labels.CONSENT_RULES.get(rule), lang, rule)} ({region_label})",
        region=region,
        answer=labels.lit(answer),
        answer_label=labels.pick(labels.CONSENT_ANSWERS.get(answer), lang, answer),
        recording=bool(c.get("recording", answer in ("given", "not_required"))),
        asked_at=datetime.fromisoformat(asked) if asked else None,
        turn_id=c.get("turnId"),
    )


def recording_kept(call: Call) -> bool:
    c = call.consent or {}
    return bool(c.get("recording", c.get("answer") in ("given", "not_required"))) and not call.is_public_demo


# ---------------------------------------------------------------- hand-offs


async def users_by_id(db: AsyncSession, ids: Iterable[str | None]) -> dict[str, User]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = (await db.execute(select(User).where(User.id.in_(wanted)))).scalars().all()
    return {u.id: u for u in rows}


def handoff_out(h: Handoff, call: Call, lang: str, people: dict[str, User]) -> w.HandoffInfo:
    end = h.accepted_at or h.resolved_at or clock.now()
    accepted = people.get(h.accepted_by or "")
    to = people.get(h.to_user_id or "")
    return w.HandoffInfo(
        id=h.id,
        call_id=call.id,
        reason=labels.lit(h.reason),
        reason_label=labels.pick(labels.HANDOFF_REASONS.get(h.reason), lang, h.reason),
        detail=h.detail,
        priority=labels.lit(h.priority),
        state=labels.lit(h.state),
        requested_at=h.requested_at,
        waiting_seconds=max(0, int((end - h.requested_at).total_seconds())),
        accepted_by=PersonRef(id=accepted.id, name=accepted.full_name) if accepted else None,
        accepted_at=h.accepted_at,
        caller_label=caller_label(call, lang),
        line_label=f"Line {call.line_number}" if call.line_number else call.reference,
        place=call.place,
        loss_type_label=labels.loss_type(call.loss_type, lang),
        language=labels.lit(lang_of(call.language)),
        summary=h.summary,
        actions_taken=list(h.actions or []),
        to=PersonRef(id=to.id, name=to.full_name) if to else None,
        team=labels.lit(h.team),
    )


async def current_handoff(db: AsyncSession, call: Call) -> Handoff | None:
    return (
        await db.execute(
            select(Handoff)
            .where(Handoff.call_id == call.id, Handoff.state.in_(("waiting", "accepted", "callback_offered")))
            .order_by(Handoff.requested_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def handoff_for(db: AsyncSession, call: Call, lang: str) -> w.HandoffInfo | None:
    h = await current_handoff(db, call)
    if h is None:
        return None
    people = await users_by_id(db, [h.accepted_by, h.to_user_id])
    return handoff_out(h, call, lang, people)


# ---------------------------------------------------------------- claim file


@dataclass(frozen=True, slots=True)
class FileParts:
    current: dict[str, CallSlot]
    history: dict[str, list[CallSlot]]


async def slot_rows(db: AsyncSession, call_id: str) -> FileParts:
    rows = (
        (await db.execute(select(CallSlot).where(CallSlot.call_id == call_id).order_by(CallSlot.created_at)))
        .scalars()
        .all()
    )
    current: dict[str, CallSlot] = {}
    history: dict[str, list[CallSlot]] = {}
    for r in rows:
        if r.superseded_at is None:
            current[r.key] = r
        else:
            history.setdefault(r.key, []).append(r)
    return FileParts(current, history)


async def script_required(db: AsyncSession, org_id: str, loss_type: str | None) -> list[str]:
    keys: list[str] = []
    if loss_type:
        row = (
            await db.execute(
                select(ScriptVersion)
                .where(ScriptVersion.org_id == org_id, ScriptVersion.loss_type == loss_type)
                .order_by(ScriptVersion.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is not None:
            keys = [q["slotKey"] for q in row.questions if q.get("required", True) and not q.get("surgeOnly")]
    return [k for k in required_keys(keys) if k in SLOT_CATALOG]


def _source_label(row: CallSlot, lang: str) -> str:
    if row.source == "heard":
        return "▸ " + labels.clock_seconds((row.at_ms or 0) / 1000)
    if row.source == "person":
        who = row.changed_by or labels.t(lang, "a person", "une personne")
        return labels.t(lang, f"edited by {who}", f"modifié par {who}")
    return labels.pick(labels.SLOT_SOURCES.get(row.source), lang, row.source)


def _confidence_label(conf: float | None) -> str | None:
    if conf is None:
        return None
    return "sure" if conf >= 0.85 else "likely" if conf >= 0.6 else "check"


def _span(row: CallSlot) -> TextSpan | None:
    if row.turn_id and row.span_start is not None and row.span_end is not None:
        return TextSpan(turn_id=row.turn_id, start=row.span_start, end=row.span_end)
    return None


def slot_out(row: CallSlot, lang: str, required: bool, history: Sequence[CallSlot] = ()) -> w.Slot:
    spec = SLOT_CATALOG.get(row.key)
    return w.Slot(
        key=row.key,
        label=spec.label(lang) if spec else row.key,
        value=row.value,
        display=row.display,
        confidence=row.confidence,
        confidence_label=labels.lit(_confidence_label(row.confidence)),
        source=labels.lit(row.source),
        source_label=_source_label(row, lang),
        span=_span(row),
        heard_at_seconds=(row.at_ms / 1000) if row.source == "heard" and row.at_ms is not None else None,
        changed_at_seconds=(row.at_ms / 1000) if row.corrects and row.at_ms is not None else None,
        confirmed=row.confirmed,
        required=required,
        history=[
            w.SlotHistory(
                value=h.value,
                display=h.display,
                source=labels.lit(h.source),
                changed_by=h.changed_by,
                at=h.created_at,
                span=_span(h),
                note=h.note,
            )
            for h in history
        ],
    )


def progress_of(current: dict[str, CallSlot], required: list[str]) -> tuple[float, list[str]]:
    if not required:
        return 0.0, []
    filled = [k for k in required if k in current and current[k].value not in (None, "")]
    missing = [k for k in required if k not in filled]
    return round(len(filled) / len(required), 3), missing


async def claim_file(
    db: AsyncSession, call: Call, lang: str, *, claim_id: str | None = None, parts: FileParts | None = None
) -> w.ClaimFile:
    parts = parts or await slot_rows(db, call.id)
    loss_type = call.loss_type or (parts.current["loss_type"].value if "loss_type" in parts.current else None)
    required = await script_required(db, call.org_id, loss_type)
    progress, missing = progress_of(parts.current, required)
    order = list(SLOT_CATALOG)
    sections = []
    for key, names in SECTIONS.items():
        rows = sorted(
            (r for k, r in parts.current.items() if SLOT_CATALOG.get(k) and SLOT_CATALOG[k].section == key),
            key=lambda r: order.index(r.key),
        )
        if not rows:
            continue
        sections.append(
            w.ClaimFileSection(
                key=labels.lit(key),
                label=labels.pick(names, lang),
                slots=[slot_out(r, lang, r.key in required, parts.history.get(r.key, ())) for r in rows],
            )
        )
    return w.ClaimFile(
        call_id=call.id,
        claim_id=claim_id,
        loss_type=loss_type,
        loss_type_label=labels.loss_type(loss_type, lang),
        progress=progress,
        missing=[SLOT_CATALOG[k].label(lang) for k in missing],
        sections=sections,
    )


# ---------------------------------------------------------------- transcript


def _speaker_label(t: CallTurn, call: Call, lang: str) -> str:
    if t.speaker == "line":
        return "ClaimVoice"
    if t.speaker == "caller":
        return call.caller_name or labels.t(lang, "Caller", "Appelant")
    if t.speaker == "person":
        return t.speaker_name or labels.t(lang, "A person", "Une personne")
    return labels.t(lang, "Notice", "Avis")


def turn_out(t: CallTurn, call: Call, lang: str) -> w.Turn:
    return w.Turn(
        id=t.id,
        seq=t.seq,
        speaker=labels.lit(t.speaker),
        speaker_label=_speaker_label(t, call, lang),
        text=t.text,
        text_en=t.text_en,
        language=labels.lit(lang_of(t.language)),
        at_ms=t.at_ms,
        end_ms=t.end_ms,
        stage=t.stage,
        confidence=t.confidence,
        interrupted=t.interrupted,
        redactions=t.redactions,
        flags=list(t.flags or []),
    )


def whisper_turn(wh: Whisper, seq: int, lang: str) -> w.Turn:
    first = wh.author_name.split(" ")[0]
    return w.Turn(
        id=wh.id,
        seq=seq,
        speaker="whisper",
        speaker_label=labels.t(lang, f"Whisper, ClaimVoice only · {first}", f"Murmure, ClaimVoice seulement · {first}"),
        text=wh.text,
        text_en=None,
        language="en",
        at_ms=wh.at_ms,
        end_ms=wh.at_ms,
        stage="",
        confidence=None,
        interrupted=False,
        redactions=0,
        flags=[],
    )


REFUSED_NOTICE = {
    "en": "Recording stopped at the caller's request. Notes only from here.",
    "fr": "Enregistrement arrêté à la demande de l'appelant. Notes seulement à partir d'ici.",
}


async def transcript(db: AsyncSession, call: Call, lang: str, *, staff: bool = True) -> w.Transcript:
    turns = (
        (
            await db.execute(
                select(CallTurn).where(CallTurn.call_id == call.id, CallTurn.retained.is_(True)).order_by(CallTurn.seq)
            )
        )
        .scalars()
        .all()
    )
    refused = (call.consent or {}).get("answer") == "refused"
    out = [turn_out(t, call, lang) for t in turns]
    if staff:
        whispers = (
            (await db.execute(select(Whisper).where(Whisper.call_id == call.id).order_by(Whisper.at_ms)))
            .scalars()
            .all()
        )
        for wh in whispers:
            seq = max((t.seq for t in out if t.at_ms <= wh.at_ms), default=0)
            out.append(whisper_turn(wh, seq, lang))
        out.sort(key=lambda t: (t.at_ms, 0 if t.speaker != "whisper" else 1, t.seq))
    retained = not refused
    return w.Transcript(
        call_id=call.id,
        language=labels.lit(lang_of(call.language)),
        retained=retained,
        notice=None if retained else labels.pick(REFUSED_NOTICE, lang),
        turns=out if retained else [t for t in out if t.speaker == "whisper"],
    )


# ---------------------------------------------------------------- timeline


async def timeline(db: AsyncSession, call: Call) -> list[w.CallEvent]:
    rows = (
        (
            await db.execute(
                select(CallEvent).where(CallEvent.call_id == call.id).order_by(CallEvent.at_ms, CallEvent.at)
            )
        )
        .scalars()
        .all()
    )
    return [
        w.CallEvent(
            id=r.id, at=r.at, at_ms=r.at_ms, kind=labels.lit(r.kind), label=r.label, actor=r.actor_label, data=r.data
        )
        for r in rows
    ]


# ---------------------------------------------------------------- summaries and detail


async def qa_scores_for(db: AsyncSession, call_ids: Sequence[str]) -> dict[str, float]:
    if not call_ids:
        return {}
    rows = (
        await db.execute(select(QaScoreRow.call_id, QaScoreRow.score).where(QaScoreRow.call_id.in_(call_ids)))
    ).all()
    return {r[0]: float(r[1]) for r in rows}


async def claims_for_calls(db: AsyncSession, call_ids: Sequence[str]) -> dict[str, tuple[str, str]]:
    from claimvoice.claims.models import Claim

    if not call_ids:
        return {}
    rows = (
        await db.execute(select(Claim.call_id, Claim.id, Claim.claim_number).where(Claim.call_id.in_(call_ids)))
    ).all()
    return {str(r[0]): (r[1], r[2]) for r in rows}


def summary_out(
    call: Call, lang: str, *, siu: bool, claim: tuple[str, str] | None = None, qa: float | None = None
) -> w.CallSummary:
    state = call.state
    return w.CallSummary(
        id=call.id,
        reference=call.reference,
        started_at=call.answered_at,
        ended_at=call.ended_at,
        duration_seconds=duration_seconds(call),
        state=labels.lit(state),
        state_label=labels.pick(labels.LINE_STATES.get(state), lang, state),
        mode=labels.lit(call.mode),
        language=labels.lit(lang_of(call.language)),
        caller_label=caller_label(call, lang),
        region_label=labels.region(call.region, lang),
        loss_type_label=labels.loss_type(call.loss_type, lang),
        outcome=labels.lit(call.outcome),
        outcome_label=labels.pick(labels.OUTCOMES.get(call.outcome), lang, call.outcome),
        claim_id=claim[0] if claim else None,
        claim_number=claim[1] if claim else None,
        flags=flags_out(call, lang, siu=siu),
        qa_score=qa,
        is_sample=call.is_sample,
    )


async def detail(db: AsyncSession, call: Call, lang: str, *, siu: bool) -> w.CallDetail:
    claim = (await claims_for_calls(db, [call.id])).get(call.id)
    qa = (await qa_scores_for(db, [call.id])).get(call.id)
    base = summary_out(call, lang, siu=siu, claim=claim, qa=qa)
    policy_number = None
    if call.policy_id:
        from claimvoice.policies.models import Policy

        policy = await db.get(Policy, call.policy_id)
        policy_number = policy.policy_number if policy else None
    fields = {f: getattr(base, f) for f in base.__struct_fields__}
    return w.CallDetail(
        **fields,
        line_label=line_label(call),
        place=call.place,
        stage=stage_info(call.stage, lang, call.resume_stage),
        stages=scripted_path(lang),
        consent=consent_out(call, lang),
        policy_id=call.policy_id,
        policy_number=policy_number,
        holder_id=call.holder_id,
        handoff=await handoff_for(db, call, lang),
        listeners=listeners_out(call),
        summary=call.summary,
        summary_en=call.summary_en,
        recording_available=recording_kept(call) and call.state == "ended",
        surge_id=call.surge_id,
    )


async def live_line(db: AsyncSession, call: Call, lang: str, *, siu: bool) -> w.LiveLine:
    parts = await slot_rows(db, call.id)
    loss_type = call.loss_type or (parts.current["loss_type"].value if "loss_type" in parts.current else None)
    required = await script_required(db, call.org_id, loss_type)
    progress, _missing = progress_of(parts.current, required)
    last = call.last_asked or None
    return w.LiveLine(
        call_id=call.id,
        line_label=f"Line {call.line_number}" if call.line_number else call.reference,
        state=labels.lit(call.state),
        state_label=labels.pick(labels.LINE_STATES.get(call.state), lang, call.state),
        stage=stage_info(call.stage, lang, call.resume_stage),
        mode=labels.lit(call.mode),
        language=labels.lit(lang_of(call.language)),
        caller_label=caller_label(call, lang),
        caller_verified=call.caller_verified,
        caller_phone_masked=labels.mask_phone(call.caller_phone_e164),
        region=call.region,
        region_label=labels.region(call.region, lang),
        loss_type=loss_type,
        loss_type_label=labels.loss_type(loss_type, lang),
        answered_at=call.answered_at,
        flags=flags_out(call, lang, siu=siu),
        mood=mood_out(call, lang),
        handoff=await handoff_for(db, call, lang),
        listeners=listeners_out(call),
        in_surge=call.surge_id is not None,
        last_asked=w.LastAsked(text=last["text"], text_en=last.get("textEn")) if last else None,
        place=call.place,
        heard=[w.HeardPill(key=h["key"], text=h["text"], tone=h.get("tone", "normal")) for h in (call.heard or [])[:4]],
        claim_file_progress=progress,
        is_sample=call.is_sample,
    )


# ---------------------------------------------------------------- recording


def _peaks(call: Call, turns: Sequence[CallTurn], total_ms: int, n: int = 800) -> list[float]:
    """A deterministic envelope from the turn timing (the waveform draws before the audio loads)."""
    if total_ms <= 0:
        return [0.0] * n
    peaks = [0.02] * n
    for t in turns:
        if t.speaker not in ("caller", "line", "person"):
            continue
        a = int(t.at_ms / total_ms * n)
        b = max(a + 1, int(t.end_ms / total_ms * n))
        seed = hashlib.sha256(t.id.encode()).digest()
        base = 0.55 if t.speaker == "caller" else 0.42
        for i in range(a, min(b, n)):
            wobble = seed[i % len(seed)] / 255
            env = math.sin(math.pi * (i - a + 0.5) / max(1, b - a)) ** 0.4
            peaks[i] = round(min(1.0, base * env + 0.35 * wobble * env), 3)
    for t in turns:  # card-number cuts are silent
        if t.redactions:
            a, b = int(t.at_ms / total_ms * n), int(t.end_ms / total_ms * n)
            for i in range(a, min(b + 1, n)):
                peaks[i] = 0.0
    return peaks


MOMENT_LABELS: dict[str, dict[str, str]] = {
    "consent": {"en": "Consent", "fr": "Consentement"},
    "policy": {"en": "Policy found", "fr": "Police trouvée"},
    "safety": {"en": "Safety asked", "fr": "Sécurité demandée"},
    "photos": {"en": "Photo link sent", "fr": "Lien photo envoyé"},
    "read_back": {"en": "Read-back", "fr": "Relecture"},
    "claim_number": {"en": "Claim number given", "fr": "Numéro de réclamation donné"},
    "handoff": {"en": "Hand-off", "fr": "Transfert"},
    "whisper": {"en": "Whisper", "fr": "Murmure"},
}


async def recording(db: AsyncSession, call: Call, lang: str, *, audio_url: str, retained_until: Any) -> Recording:
    kept = recording_kept(call)
    if not kept or call.state != "ended":
        reason = None
        if (call.consent or {}).get("answer") == "refused":
            reason = labels.t(lang, "The caller did not agree to recording", "L'appelant a refusé l'enregistrement")
        elif call.state != "ended":
            reason = labels.t(lang, "The call is still on the line", "L'appel est en cours")
        else:
            reason = labels.t(lang, "Nothing was kept from this call", "Rien n'a été conservé de cet appel")
        return Recording(
            available=False,
            reason=reason,
            audio_url=None,
            duration_seconds=None,
            peaks=None,
            segments=[],
            moments=[],
            hushes=[],
            retained_until=None,
        )
    if (call.consent or {}).get("purgedAt"):
        return Recording(
            available=False,
            reason=labels.t(lang, "Removed after the retention period", "Supprimé après la durée de conservation"),
            audio_url=None,
            duration_seconds=None,
            peaks=None,
            segments=[],
            moments=[],
            hushes=[],
            retained_until=None,
        )
    turns = (
        (
            await db.execute(
                select(CallTurn).where(CallTurn.call_id == call.id, CallTurn.retained.is_(True)).order_by(CallTurn.seq)
            )
        )
        .scalars()
        .all()
    )
    total_ms = int((call.recording_seconds or 0) * 1000) or (
        int((call.ended_at - call.answered_at).total_seconds() * 1000) if call.ended_at else 0
    )
    total_ms = max(total_ms, max((t.end_ms for t in turns), default=0))
    segments = [
        RecordingSegment(
            turn_id=t.id,
            speaker=labels.lit(t.speaker if t.speaker in ("caller", "line", "person") else "system"),
            start_seconds=round(t.at_ms / 1000, 2),
            end_seconds=round(t.end_ms / 1000, 2),
            paused=t.redactions > 0,
        )
        for t in turns
    ]
    events = (await db.execute(select(CallEvent).where(CallEvent.call_id == call.id))).scalars().all()
    moments: list[Moment] = []
    by_stage_first: dict[str, CallTurn] = {}
    for t in turns:
        if t.speaker == "line":
            by_stage_first.setdefault(t.stage, t)

    def add(kind: str, at_ms: int, turn_id: str | None, label: str | None = None) -> None:
        moments.append(
            Moment(
                kind=labels.lit(kind),
                label=label or labels.pick(MOMENT_LABELS.get(kind), lang, kind),
                at_seconds=round(at_ms / 1000, 2),
                turn_id=turn_id,
            )
        )

    for e in events:
        if e.kind == "consent":
            add("consent", e.at_ms, e.data.get("turnId"))
        elif e.kind == "tool" and e.data.get("tool") == "policy_lookup" and e.data.get("ok"):
            add("policy", e.at_ms, None)
        elif e.kind == "photo_link":
            add("photos", e.at_ms, None)
        elif e.kind == "handoff":
            add("handoff", e.at_ms, None)
        elif e.kind == "whisper":
            add("whisper", e.at_ms, None)
        elif e.kind == "flag" and e.data.get("kind") == "siu_signal":
            add("sign", e.at_ms, e.data.get("turnId"), e.data.get("detail"))
    if "safety" in by_stage_first:
        add("safety", by_stage_first["safety"].at_ms, by_stage_first["safety"].id)
    if "read_back" in by_stage_first:
        add("read_back", by_stage_first["read_back"].at_ms, by_stage_first["read_back"].id)
    if "wrap_up" in by_stage_first:
        add("claim_number", by_stage_first["wrap_up"].at_ms, by_stage_first["wrap_up"].id)
    moments.sort(key=lambda m: m.at_seconds)
    return Recording(
        available=True,
        reason=None,
        audio_url=audio_url,
        duration_seconds=round(total_ms / 1000, 2),
        peaks=_peaks(call, turns, total_ms),
        segments=segments,
        moments=moments,
        hushes=[(round(t.at_ms / 1000, 2), round(t.end_ms / 1000, 2)) for t in turns if t.redactions],
        retained_until=retained_until,
    )


def retained_until(call: Call, years: int) -> Any:
    end = call.ended_at or call.answered_at
    return (end + timedelta(days=365 * years)).date()
