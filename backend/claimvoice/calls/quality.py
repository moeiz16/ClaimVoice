"""Call-quality scores: persisting the scorer's result with its evidence, beads and the review focus, and the wire
shapes for the review queue (docs/API_CONTRACT.md §1.9)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import contracts
from claimvoice.api import labels
from claimvoice.calls import views
from claimvoice.calls.models import Call, CallTurn, QaScoreRow
from claimvoice.platform.models import User
from claimvoice.qa.rubric import RUBRIC
from claimvoice.schemas import qa as w
from claimvoice.schemas.base import PersonRef

RUBRIC_BY_KEY = {r.key: r for r in RUBRIC}
_FRACTION = re.compile(r"(\d+)\s*/\s*(\d+)")


def reason_queued(result: contracts.QaResult) -> str | None:
    if not result.needs_review:
        return None
    for item in result.items:
        spec = RUBRIC_BY_KEY.get(item.key)
        if spec and spec.critical and item.passed is False:
            return f"Critical item failed: {spec.label.lower()}"
    if result.score < 70:
        return "Score under 70"
    handoff = next((i for i in result.items if i.key == "handoff_correct"), None)
    if handoff is not None and handoff.passed is not None:
        return "A hand-off rule applied"
    return "Random 10% sample"


def to_row(
    org_id: str, call_id: str, result: contracts.QaResult, turns: Sequence[CallTurn], at: datetime
) -> QaScoreRow:
    by_id = {t.id: t for t in turns}
    items: list[dict[str, Any]] = []
    for it in result.items:
        spec = RUBRIC_BY_KEY.get(it.key)
        evidence = [{"turnId": tid, "quote": by_id[tid].text[:160]} for tid in it.evidence_turn_ids if tid in by_id]
        first = by_id.get(it.evidence_turn_ids[0]) if it.evidence_turn_ids else None
        items.append(
            {
                "key": it.key,
                "label": spec.label if spec else it.key,
                "passed": it.passed,
                "points": it.points,
                "maxPoints": it.max_points,
                "critical": bool(spec and spec.critical),
                "method": it.method,
                "note": it.note,
                "evidence": evidence,
                "atMs": first.at_ms if first else None,
            }
        )
    beads = []
    for spec in RUBRIC:
        if not spec.bead:
            continue
        found = next((i for i in items if i["key"] == spec.key), None)
        detail = None
        if found is not None:
            m = _FRACTION.search(found["note"] or "")
            detail = f"{m.group(1)}/{m.group(2)}" if m else None
        passed = found["passed"] if found else None
        beads.append({"key": spec.key, "label": spec.label, "passed": passed, "detail": detail})
    focus = None
    failed = [i for i in items if i["passed"] is False]
    failed.sort(key=lambda i: (not i["critical"], i["atMs"] is None))
    if failed and failed[0]["atMs"] is not None:
        at_s = failed[0]["atMs"] / 1000
        what = failed[0]["note"] or failed[0]["label"]
        focus = {"atSeconds": at_s, "text": f"Jumped to {labels.clock_seconds(at_s)}, where {_lower_first(what)}"}
    return QaScoreRow(
        org_id=org_id,
        call_id=call_id,
        score=round(float(result.score), 1),
        band=result.band,
        status="needs_review" if result.needs_review else "auto_passed",
        reason_queued=reason_queued(result),
        items=items,
        beads=beads,
        focus=focus,
        scorer_version=result.scorer_version,
        scored_at=at,
    )


def _lower_first(text: str) -> str:
    text = text.rstrip(".")
    return text[:1].lower() + text[1:] if text else text


def events_for_scorer(rows: Sequence[Any]) -> list[dict[str, Any]]:
    return [{"kind": e.kind, "atMs": e.at_ms, "data": dict(e.data or {})} for e in rows]


def turn_records(turns: Sequence[CallTurn]) -> list[contracts.TurnRecord]:
    return [
        contracts.TurnRecord(
            turn_id=t.id,
            seq=t.seq,
            speaker=contracts.Speaker(t.speaker) if t.speaker != "whisper" else contracts.Speaker.SYSTEM,
            text=t.text,
            language=t.language,
            at_ms=t.at_ms,
            end_ms=t.end_ms,
            stage=t.stage,
            confidence=t.confidence,
            interrupted=t.interrupted,
            redactions=t.redactions,
            retained=t.retained,
            speaker_name=t.speaker_name,
        )
        for t in turns
    ]


def slot_records(current: Mapping[str, Any]) -> dict[str, contracts.SlotRecord]:
    return {
        k: contracts.SlotRecord(
            key=r.key,
            value=r.value,
            display=r.display,
            confidence=r.confidence or 0.0,
            source=r.source,
            turn_id=r.turn_id,
            span=(r.span_start, r.span_end) if r.span_start is not None else None,
            confirmed=r.confirmed,
            corrects=r.corrects,
        )
        for k, r in current.items()
    }


# ---------------------------------------------------------------- wire


def _beads(row: QaScoreRow) -> list[w.Bead]:
    return [w.Bead(key=b["key"], label=b["label"], passed=b["passed"], detail=b.get("detail")) for b in row.beads]


def score_out(row: QaScoreRow, claim: tuple[str, str] | None, people: dict[str, User], lang: str) -> w.QaScore:
    review = row.review or {}
    verdicts = {v["key"]: v for v in review.get("items", [])}
    reviewer = people.get(row.reviewed_by or "")
    return w.QaScore(
        call_id=row.call_id,
        claim_id=claim[0] if claim else None,
        claim_number=claim[1] if claim else None,
        score=row.score,
        band=labels.lit(row.band),
        band_label=labels.pick(labels.QA_BANDS.get(row.band), lang, row.band),
        status=labels.lit(row.status),
        items=[
            w.QaItem(
                key=i["key"],
                label=i["label"],
                passed=i["passed"],
                points=i["points"],
                max_points=i["maxPoints"],
                critical=i["critical"],
                method=i["method"],
                note=i["note"],
                evidence=[w.Evidence(turn_id=e["turnId"], quote=e["quote"]) for e in i["evidence"]],
                at_seconds=i["atMs"] / 1000 if i.get("atMs") is not None else None,
                reviewer_verdict=verdicts.get(i["key"], {}).get("verdict"),
                reviewer_note=verdicts.get(i["key"], {}).get("note"),
            )
            for i in row.items
        ],
        beads=_beads(row),
        focus=w.Focus(at_seconds=row.focus["atSeconds"], text=row.focus["text"]) if row.focus else None,
        scored_at=row.scored_at,
        scorer_version=row.scorer_version,
        reviewed_by=PersonRef(id=reviewer.id, name=reviewer.full_name) if reviewer else None,
        reviewed_at=row.reviewed_at,
        review_note=review.get("note"),
    )


def queue_item(
    row: QaScoreRow, call: Call, claim: tuple[str, str] | None, people: dict[str, User], lang: str
) -> w.QaQueueItem:
    reviewer = people.get(row.reviewed_by or "")
    return w.QaQueueItem(
        call_id=call.id,
        reference=call.reference,
        claim_id=claim[0] if claim else None,
        claim_number=claim[1] if claim else None,
        started_at=call.answered_at,
        duration_seconds=views.duration_seconds(call) or 0,
        language=labels.lit(views.lang_of(call.language)),
        loss_type_label=labels.loss_type(call.loss_type, lang),
        score=row.score,
        band=labels.lit(row.band),
        band_label=labels.pick(labels.QA_BANDS.get(row.band), lang, row.band),
        failed_items=[i["label"] for i in row.items if i["passed"] is False],
        beads=_beads(row),
        caller_label=views.caller_label(call, lang),
        line_label=None,
        reviewer=PersonRef(id=reviewer.id, name=reviewer.full_name) if reviewer else None,
        status=labels.lit(row.status),
        reason_queued=row.reason_queued or ("Reviewed" if row.status == "reviewed" else "Met the rubric"),
    )


async def queue_item_for(db: AsyncSession, row: QaScoreRow, lang: str) -> w.QaQueueItem | None:
    call = await db.get(Call, row.call_id)
    if call is None:
        return None
    claim = (await views.claims_for_calls(db, [call.id])).get(call.id)
    people = await views.users_by_id(db, [row.reviewed_by])
    return queue_item(row, call, claim, people, lang)
