"""At hang-up (docs/API_CONTRACT.md Part 3, "At hang-up"), in order:

1. purge the turns that may not be kept (recording consent refused) and close any open hand-off;
2. create the claim when a loss was reported on a found policy (with the claim number the line already read out);
3. build the routing checks' input from the claim file, the policy and the call, call `TriageScorer`, persist the
   decision with its reasons linked to the moments they were heard;
4. open a closer-look referral when the checks ask for one: a request for review, never a denial;
5. score the call with `CallScorer` and queue it for review when needed;
6. publish `line.closed`, `claim.created`, `qa.flagged` and the day's numbers.

`finalize` does steps 1-5 inside the caller's session and is also what the seed uses, so every seeded route and score
comes from the same scorers as a live call."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func, select, update

from claimvoice import clock, contracts
from claimvoice.api import labels
from claimvoice.calls import quality, scoring, views
from claimvoice.calls.models import Call, CallEvent, CallTurn, Handoff, PhotoLink, QaScoreRow
from claimvoice.claims.models import Claim, ClaimPhoto, RoutingDecisionRow, SiuReferral
from claimvoice.dialogue.slots import KEY_FACTS
from claimvoice.platform import auditlog, db
from claimvoice.platform.events import bus, call_key, org_key
from claimvoice.policies.models import Coverage, InsuredItem, Policy, Policyholder
from claimvoice.schemas.switchboard import LineClosed

log = structlog.get_logger("claimvoice.closing")
PUBLIC_DEMO_KEEP = timedelta(minutes=10)

COVERAGE_FOR_LOSS: dict[str, tuple[str, ...]] = {
    "collision": ("collision",),
    "hail": ("wind_hail", "comprehensive", "dwelling"),
    "wind": ("wind_hail", "dwelling", "comprehensive"),
    "water": ("water_escape", "sewer_backup", "dwelling"),
    "fire": ("dwelling", "comprehensive"),
    "theft": ("comprehensive", "contents"),
}

NEXT_STEPS: dict[str, dict[str, list[str]]] = {
    "fast_track": {
        "en": ["Send photos through the texted link", "A claims specialist calls within one business day"],
        "fr": ["Envoyer les photos par le lien texté", "Un spécialiste rappelle d'ici un jour ouvrable"],
    },
    "adjuster": {
        "en": ["Send photos through the texted link", "An adjuster calls today to book a visit"],
        "fr": ["Envoyer les photos par le lien texté", "Un expert appelle aujourd'hui pour planifier une visite"],
    },
    "special_investigation": {
        "en": ["Send photos through the texted link", "An adjuster calls within one business day"],
        "fr": ["Envoyer les photos par le lien texté", "Un expert rappelle d'ici un jour ouvrable"],
    },
}


@dataclass
class Closed:
    claim_id: str | None = None
    claim_number: str | None = None
    qa_flagged: bool = False
    siu_opened: bool = False


def age_band(dob: date | None, on: date) -> str:
    if dob is None:
        return "unknown"
    years = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
    return "under_35" if years < 35 else "65_plus" if years >= 65 else "35_64"


async def _policy_facts(session: Any, policy: Policy, loss_type: str, loss_date: date | None) -> dict[str, Any]:
    coverages = (await session.execute(select(Coverage).where(Coverage.policy_id == policy.id))).scalars().all()
    wanted = COVERAGE_FOR_LOSS.get(loss_type, ())
    cov = next((c for k in wanted for c in coverages if c.key == k and c.included), None)
    since = (loss_date or clock.today()) - timedelta(days=36 * 30)
    prior = (
        await session.execute(
            select(func.count())
            .select_from(Claim)
            .where(
                Claim.holder_id == policy.holder_id, Claim.loss_date >= since, Claim.loss_date < (loss_date or date.max)
            )
        )
    ).scalar_one()
    vehicle_year = None
    item = (
        (
            await session.execute(
                select(InsuredItem).where(InsuredItem.policy_id == policy.id, InsuredItem.kind == "vehicle")
            )
        )
        .scalars()
        .first()
    )
    if item is not None:
        vehicle_year = item.details.get("year")
    return {
        "policy_number": policy.policy_number,
        "line": policy.line,
        "product": policy.product,
        "region": policy.region,
        "status": policy.status,
        "effective_from": policy.effective_from.isoformat(),
        "effective_to": policy.effective_to.isoformat(),
        "coverage_changed_at": policy.coverage_changed_at.isoformat() if policy.coverage_changed_at else None,
        "currency": policy.currency,
        "deductible": cov.deductible if cov else None,
        "coverage_limit": cov.limit if cov else None,
        "prior_claims_36m": int(prior),
        "vehicle_age_years": (loss_date or clock.today()).year - int(vehicle_year) if vehicle_year else None,
    }


def _link(parts: views.FileParts, slot_key: str | None) -> tuple[str | None, int | None]:
    row = parts.current.get(slot_key or "")
    if row is None or row.source != "heard":
        return None, None
    return row.turn_id, row.at_ms


def _reason_json(r: contracts.Reason, parts: views.FileParts) -> dict[str, Any]:
    slot_key = getattr(r, "slot_key", None)
    source = getattr(r, "source", "call")
    turn_id, at_ms = _link(parts, slot_key) if source == "call" else (None, None)
    return {
        "feature": r.feature,
        "text": dict(r.text),
        "direction": r.direction,
        "weight": round(float(r.weight), 4),
        "slotKey": slot_key,
        "source": source,
        "turnId": turn_id,
        "atMs": at_ms,
    }


def _indicator_json(r: contracts.Reason, parts: views.FileParts, policy: Policy) -> dict[str, Any]:
    out = _reason_json(r, parts)
    source = out["source"]
    row = parts.current.get(out["slotKey"] or "")
    if source == "call" and row is not None:
        evidence = {"en": f"Heard on the call: “{row.display}”", "fr": f"Entendu pendant l'appel : « {row.display} »"}
    elif source == "policy":
        evidence = {
            "en": f"Policy {policy.policy_number} record",
            "fr": f"Dossier de la police {policy.policy_number}",
        }
    elif source == "claim_history":
        evidence = {"en": "Claims on file for this policyholder", "fr": "Réclamations au dossier de ce titulaire"}
    else:
        evidence = {"en": "Weather records for the date and place", "fr": "Données météo pour la date et le lieu"}
    return {
        "key": out["feature"],
        "label": out["text"],
        "evidence": evidence,
        "source": source,
        "turnId": out["turnId"],
        "atMs": out["atMs"],
        "weight": out["weight"],
    }


def _in_short(summary: str, summary_en: str | None, parts: views.FileParts) -> dict[str, Any]:
    def links_for(text: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        lower = text.lower()
        for row in parts.current.values():
            if row.source != "heard" or not row.turn_id or not row.display or len(row.display) < 4:
                continue
            i = lower.find(row.display.lower())
            if i >= 0:
                found.append(
                    {
                        "start": i,
                        "end": i + len(row.display),
                        "turnId": row.turn_id,
                        "atSeconds": (row.at_ms or 0) / 1000,
                    }
                )
        found.sort(key=lambda x: int(x["start"]))
        out: list[dict[str, Any]] = []
        for link in found:  # no overlaps
            if not out or link["start"] >= out[-1]["end"]:
                out.append(link)
        return out

    doc: dict[str, Any] = {"text": summary, "links": links_for(summary), "checkedBy": None, "checkedAt": None}
    if summary_en and summary_en != summary:
        doc["textEn"] = summary_en
        doc["linksEn"] = []
    return doc


def _value(parts: views.FileParts, key: str) -> Any:
    row = parts.current.get(key)
    return row.value if row is not None else None


async def finalize(session: Any, call: Call) -> Closed:
    """Steps 1-5 for an ended call (its fields already set). Commits nothing."""
    at = call.ended_at or clock.now()
    result = Closed()
    # 1. purge what may not be kept
    await session.execute(delete(CallTurn).where(CallTurn.call_id == call.id, CallTurn.retained.is_(False)))
    if (call.consent or {}).get("answer") == "refused":
        call.recording_path = None
    open_handoffs = (
        (await session.execute(select(Handoff).where(Handoff.call_id == call.id, Handoff.resolved_at.is_(None))))
        .scalars()
        .all()
    )
    for h in open_handoffs:
        h.resolved_at = at
        if h.state in ("waiting", "accepted", "callback_offered"):
            h.state = "completed"
    await session.flush()
    if call.is_public_demo:
        call.outcome = "no_claim"
        return result

    parts = await views.slot_rows(session, call.id)
    loss_type = call.loss_type or _value(parts, "loss_type")
    policy = await session.get(Policy, call.policy_id) if call.policy_id else None

    # 2. the claim
    if loss_type and policy is not None:
        loss_date_raw = _value(parts, "loss_date")
        try:
            loss_date = date.fromisoformat(str(loss_date_raw)) if loss_date_raw else None
        except ValueError:
            loss_date = None
        number = call.claim_number
        if not number:
            from claimvoice.calls.sink import allocate_claim_number

            number = await allocate_claim_number(call.org_id, at.year)
            call.claim_number = number
        place = parts.current["loss_place"].display if "loss_place" in parts.current else call.place
        urgent = any(f.get("kind") == "urgent_safety" for f in call.flags or [])
        claim = Claim(
            org_id=call.org_id,
            claim_number=number,
            call_id=call.id,
            policy_id=policy.id,
            holder_id=policy.holder_id,
            line=policy.line,
            loss_type=loss_type,
            loss_date=loss_date,
            loss_place=place,
            description=call.summary
            or (parts.current["loss_description"].display if "loss_description" in parts.current else ""),
            description_en=call.summary_en,
            status="new",
            urgent_safety=urgent,
            surge_id=call.surge_id,
            language=call.language,
            reported_at=at,
            in_short=_in_short(call.summary or "", call.summary_en, parts),
            is_sample=call.is_sample,
            created_at=at,
        )
        session.add(claim)
        await session.flush()
        result.claim_id, result.claim_number = claim.id, number
        call.outcome = "claim_created"
        await session.execute(
            update(ClaimPhoto)
            .where(ClaimPhoto.call_id == call.id, ClaimPhoto.claim_id.is_(None))
            .values(claim_id=claim.id)
        )
        await session.execute(update(PhotoLink).where(PhotoLink.call_id == call.id).values(claim_id=claim.id))

        # 3. routing checks
        holder = await session.get(Policyholder, policy.holder_id)
        policy_facts = await _policy_facts(session, policy, loss_type, loss_date)
        corrections = sum(1 for k, rows in parts.history.items() if k in KEY_FACTS for _ in rows)
        call_facts = {
            "answered_at": call.answered_at.isoformat(),
            "language": call.language,
            "region": call.region,
            "surge_match": call.surge_id is not None,
            "urgent_safety": urgent,
            "key_fact_corrections": corrections,
            "photos_declined": _value(parts, "photos_promised") is False,
            "flags": [{"kind": f.get("kind"), "detail": f.get("detail")} for f in call.flags or []],
            **(call.facts or {}),
        }
        claim_file = {k: r.value for k, r in parts.current.items()}
        features = scoring.build_features(claim_file, policy_facts, call_facts)
        features.setdefault("currency", policy.currency)
        groups = {
            "region": policy.region,
            "language": call.language,
            "age_band": age_band(holder.date_of_birth if holder else None, loss_date or at.date()),
        }
        item = contracts.TriageInput(claim.id, call.org_id, policy.line, loss_type, features, groups)
        decision = scoring.triage_scorer().score(item)
        route = decision.route
        session.add(
            RoutingDecisionRow(
                org_id=call.org_id,
                claim_id=claim.id,
                route=route,
                model_route=route,
                decided_at=at,
                settle_low=float(getattr(decision, "settle_low", 0.0)),
                settle_high=float(getattr(decision, "settle_high", 0.0)),
                currency=policy.currency,
                severity_probability=float(decision.severity_probability),
                severity_band=decision.severity_band,
                fraud_score=float(decision.fraud_score),
                fraud_band=decision.fraud_band,
                signs_checked=int(getattr(decision, "signs_checked", 14)),
                reasons=[_reason_json(r, parts) for r in decision.reasons],
                fraud_indicators=[_indicator_json(r, parts, policy) for r in decision.fraud_indicators],
                rules_applied=list(decision.rules_applied),
                model_versions=dict(decision.model_versions),
                features=dict(features),
                fairness_groups=groups,
            )
        )
        steps = _value(parts, "next_steps_given")
        claim.next_steps = (
            [str(steps)]
            if steps
            else NEXT_STEPS.get(route, NEXT_STEPS["adjuster"])["fr" if call.language == "fr" else "en"]
        )
        # 4. closer-look referral (a request for review; never a denial)
        if decision.siu_referral:
            session.add(
                SiuReferral(
                    org_id=call.org_id,
                    claim_id=claim.id,
                    status="open",
                    score=float(decision.fraud_score),
                    indicators=[_indicator_json(r, parts, policy) for r in decision.fraud_indicators],
                    opened_at=at,
                )
            )
            result.siu_opened = True
    else:
        handed = (await session.execute(select(Handoff.id).where(Handoff.call_id == call.id))).first()
        early = call.stage in ("greeting", "consent", "identity") or (call.resume_stage in ("greeting", "consent"))
        call.outcome = "handed_off" if handed else "abandoned" if early else "no_claim"

    # 5. call quality
    turns = (
        (await session.execute(select(CallTurn).where(CallTurn.call_id == call.id).order_by(CallTurn.seq)))
        .scalars()
        .all()
    )
    events = (
        (await session.execute(select(CallEvent).where(CallEvent.call_id == call.id).order_by(CallEvent.at_ms)))
        .scalars()
        .all()
    )
    events_in = quality.events_for_scorer(events)
    events_in.append(
        {
            "kind": "ended",
            "atMs": int((at - call.answered_at).total_seconds() * 1000),
            "data": {"reason": call.end_reason or "completed"},
        }
    )
    qa_result = scoring.call_scorer().score(quality.turn_records(turns), events_in, quality.slot_records(parts.current))
    existing = (await session.execute(select(QaScoreRow).where(QaScoreRow.call_id == call.id))).scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        await session.flush()
    row = quality.to_row(call.org_id, call.id, qa_result, turns, at)
    session.add(row)
    result.qa_flagged = row.status == "needs_review" and (
        row.band == "failed" or any(i["critical"] and i["passed"] is False for i in row.items)
    )
    await session.flush()
    return result


async def close_call(
    org_id: str,
    call_id: str,
    closing: contracts.CallClosing | None,
    *,
    latency_p95_ms: float | None = None,
    reason: str | None = None,
) -> Closed:
    async with db.sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None or call.org_id != org_id:
            return Closed()
        if call.state == "ended" and call.outcome != "in_progress":
            return Closed()
        if closing is not None:
            ended = call.answered_at + timedelta(milliseconds=max(0, closing.ended_at_ms))
            call.ended_at = ended
            call.end_reason = closing.reason
            call.recording_path = closing.recording_path
            call.recording_seconds = closing.recording_seconds
            call.summary = closing.summary or call.summary
            call.summary_en = closing.summary_en or call.summary_en
            call.resume_stage = (
                closing.final_stage if closing.final_stage not in ("ended", "handoff") else call.resume_stage
            )
            call.latency_p95_ms = closing.latency_p95_ms if closing.latency_p95_ms is not None else latency_p95_ms
        else:
            call.ended_at = clock.now()
            call.end_reason = reason or "ended_by_person"
        if call.stage not in ("ended",):
            call.resume_stage = call.resume_stage or call.stage
        call.stage = "ended"
        call.state = "ended"
        call.line_number = None
        call.listeners = []
        call.caller_token_hash = None
        session.add(
            CallEvent(
                org_id=org_id,
                call_id=call_id,
                at=call.ended_at,
                at_ms=int((call.ended_at - call.answered_at).total_seconds() * 1000),
                kind="ended",
                label="Call ended",
                data={"reason": call.end_reason},
            )
        )
        result = await finalize(session, call)
        await session.commit()
        await publish_closed(session, call, result)
    if result.claim_id:
        await auditlog.record(
            org_id,
            auditlog.Entry(
                action="claim.created",
                summary=f"ClaimVoice opened claim {result.claim_number} at the end of {call.reference}.",
                target_type="claim",
                target_id=result.claim_id,
                target_label=result.claim_number,
            ),
        )
    if result.siu_opened:
        await auditlog.record(
            org_id,
            auditlog.Entry(
                action="siu.referral_opened",
                summary=f"The closer-look check asked special investigations to review {result.claim_number}.",
                target_type="claim",
                target_id=result.claim_id,
                target_label=result.claim_number,
            ),
        )
    if call.is_public_demo:
        schedule_public_demo_purge(call_id)
    return result


async def publish_closed(session: Any, call: Call, result: Closed) -> None:
    from claimvoice.claims import views as claim_views

    org_id = call.org_id
    outcome_label = labels.pick(labels.OUTCOMES.get(call.outcome), "en", call.outcome)
    closed = LineClosed(
        call_id=call.id,
        outcome=labels.lit(call.outcome),
        outcome_label=outcome_label,
        claim_id=result.claim_id,
        claim_number=result.claim_number,
    )
    bus.publish(org_key(org_id), "line.closed", closed, org_id=org_id, call_id=call.id)
    bus.publish(
        call_key(call.id),
        "call.ended",
        {"reason": call.end_reason, "claimId": result.claim_id, "claimNumber": result.claim_number},
        org_id=org_id,
        call_id=call.id,
    )
    if result.claim_id:
        claim = await session.get(Claim, result.claim_id)
        summary = (await claim_views.summaries(session, [claim], "en", siu=True))[0]
        bus.publish(org_key(org_id), "claim.created", summary, org_id=org_id, call_id=call.id)
        bus.publish(org_key(org_id), "claim.routed", summary, org_id=org_id, call_id=call.id)
    if result.qa_flagged:
        row = (await session.execute(select(QaScoreRow).where(QaScoreRow.call_id == call.id))).scalar_one()
        item = await quality.queue_item_for(session, row, "en")
        if item is not None:
            bus.publish(org_key(org_id), "qa.flagged", item, org_id=org_id, call_id=call.id)
    from claimvoice.calls.desk import today_stats

    bus.publish(org_key(org_id), "stats.updated", await today_stats(session, org_id), org_id=org_id)


_purges: set[asyncio.Task[None]] = set()


def schedule_public_demo_purge(call_id: str) -> None:
    async def later() -> None:
        await asyncio.sleep(PUBLIC_DEMO_KEEP.total_seconds())
        await purge_public_demo(call_id)

    try:
        task = asyncio.get_running_loop().create_task(later())
    except RuntimeError:
        return
    _purges.add(task)
    task.add_done_callback(_purges.discard)


async def purge_public_demo(call_id: str) -> None:
    """'Nothing you say is kept after you close the page': the transcript and claim slip go 10 minutes after the
    end screen."""
    async with db.sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is not None and call.is_public_demo:
            await session.delete(call)
            await session.commit()
