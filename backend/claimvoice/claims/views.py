"""Rows to wire shapes for claims (docs/API_CONTRACT.md §1.7): ledger rows, the claim file, "Where it goes" (routing
decision with reasons), closer-look referrals and photos. Closer-look fields are removed without `siu:read`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice.api import labels
from claimvoice.calls import views as call_views
from claimvoice.calls.models import Call, Surge
from claimvoice.claims.models import Claim, ClaimPhoto, RoutingDecisionRow, SiuReferral
from claimvoice.platform.models import User
from claimvoice.policies.models import Policy, Policyholder
from claimvoice.schemas import claims as w
from claimvoice.schemas.base import PersonRef

ROUTING_STATEMENT = {
    "en": "For a person to review. A sign is never a reason to deny a claim on its own, and nothing here was decided "
    "automatically.",
    "fr": "À examiner par une personne. Un signe n'est jamais à lui seul une raison de refuser une réclamation, et "
    "rien ici n'a été décidé automatiquement.",
}
SIU_STATEMENT = {
    "en": "A referral is a request for review. It is not a finding of fraud and never denies a claim.",
    "fr": "Un renvoi est une demande d'examen. Ce n'est pas une conclusion de fraude et il ne refuse jamais une "
    "réclamation.",
}
SOURCE_LABELS = {
    "policy": {"en": "from the policy", "fr": "selon la police"},
    "claim_history": {"en": "claim history", "fr": "historique des réclamations"},
    "weather": {"en": "weather records", "fr": "données météo"},
}


def money(amount: float, currency: str, lang: str) -> str:
    whole = f"{round(amount):,}"
    if lang == "fr":
        return whole.replace(",", " ") + " $" + (" US" if currency == "USD" else "")
    return ("US$" if currency == "USD" else "$") + whole


def person(people: dict[str, User], user_id: str | None) -> PersonRef | None:
    u = people.get(user_id or "")
    return PersonRef(id=u.id, name=u.full_name) if u else None


@dataclass
class Related:
    holders: dict[str, Policyholder]
    policies: dict[str, Policy]
    routes: dict[str, RoutingDecisionRow]
    siu_open: set[str]
    photos: dict[str, int]
    people: dict[str, User]
    surges: dict[str, Surge]


async def related(db: AsyncSession, claims: Sequence[Claim]) -> Related:
    ids = [c.id for c in claims]
    if not ids:
        return Related({}, {}, {}, set(), {}, {}, {})
    holders = {
        h.id: h
        for h in (
            await db.execute(select(Policyholder).where(Policyholder.id.in_({c.holder_id for c in claims})))
        ).scalars()
    }
    policies = {
        p.id: p
        for p in (await db.execute(select(Policy).where(Policy.id.in_({c.policy_id for c in claims})))).scalars()
    }
    routes = {
        r.claim_id: r
        for r in (await db.execute(select(RoutingDecisionRow).where(RoutingDecisionRow.claim_id.in_(ids)))).scalars()
    }
    siu_open = set(
        (
            await db.execute(
                select(SiuReferral.claim_id).where(
                    SiuReferral.claim_id.in_(ids), SiuReferral.status.in_(("open", "investigating"))
                )
            )
        )
        .scalars()
        .all()
    )
    photos = dict(
        (
            await db.execute(
                select(ClaimPhoto.claim_id, func.count())
                .where(ClaimPhoto.claim_id.in_(ids))
                .group_by(ClaimPhoto.claim_id)
            )
        ).all()
    )
    people = await call_views.users_by_id(
        db, [c.assigned_to for c in claims] + [r.override_by for r in routes.values()]
    )
    surge_ids = {c.surge_id for c in claims if c.surge_id}
    surges = (
        {s.id: s for s in (await db.execute(select(Surge).where(Surge.id.in_(surge_ids)))).scalars()}
        if surge_ids
        else {}
    )
    return Related(holders, policies, routes, siu_open, {str(k): int(v) for k, v in photos.items()}, people, surges)


def route_summary(r: RoutingDecisionRow | None, lang: str) -> w.RouteSummary | None:
    if r is None:
        return None
    top = r.reasons[0]["text"] if r.reasons else {}
    top_text = labels.pick(top, lang) if isinstance(top, dict) else str(top)
    if r.override_route:
        top_text = r.override_reason or top_text
    return w.RouteSummary(
        route=labels.lit(r.route),
        label=labels.route(r.route, lang),
        decided_by="person" if r.override_route else "model",
        top_reason=top_text,
    )


def summary_out(c: Claim, rel: Related, lang: str, *, siu: bool) -> w.ClaimSummary:
    holder = rel.holders.get(c.holder_id)
    policy = rel.policies.get(c.policy_id)
    surge = rel.surges.get(c.surge_id or "")
    return w.ClaimSummary(
        id=c.id,
        claim_number=c.claim_number,
        status=labels.lit(c.status),
        status_label=labels.pick(labels.CLAIM_STATUSES.get(c.status), lang, c.status),
        line=labels.lit(c.line),
        loss_type=c.loss_type,
        loss_type_label=labels.loss_type(c.loss_type, lang) or c.loss_type,
        loss_date=c.loss_date,
        loss_place=c.loss_place,
        holder_name=holder.full_name if holder else "",
        policy_number=policy.policy_number if policy else "",
        region_label=labels.region(policy.region if policy else None, lang) or "",
        language=labels.lit(call_views.lang_of(c.language)),
        reported_at=c.reported_at,
        route=route_summary(rel.routes.get(c.id), lang),
        urgent_safety=c.urgent_safety,
        siu_open=siu and c.id in rel.siu_open,
        photos=int(rel.photos.get(c.id, 0)),
        assigned_to=person(rel.people, c.assigned_to),
        surge_label=surge.title if surge else None,
        is_sample=c.is_sample,
    )


async def summaries(db: AsyncSession, claims: Sequence[Claim], lang: str, *, siu: bool) -> list[w.ClaimSummary]:
    rel = await related(db, claims)
    return [summary_out(c, rel, lang, siu=siu) for c in claims]


async def detail(db: AsyncSession, c: Claim, lang: str, *, siu: bool) -> w.Claim:
    rel = await related(db, [c])
    base = summary_out(c, rel, lang, siu=siu)
    call = await db.get(Call, c.call_id) if c.call_id else None
    if call is not None:
        file = await call_views.claim_file(db, call, lang, claim_id=c.id)
        flags = call_views.flags_out(call, lang, siu=siu)
        has_recording = call_views.recording_kept(call) and not (call.consent or {}).get("purgedAt")
    else:
        from claimvoice.schemas.calls import ClaimFile

        file = ClaimFile(
            call_id="",
            claim_id=c.id,
            loss_type=c.loss_type,
            loss_type_label=labels.loss_type(c.loss_type, lang),
            progress=1.0,
            missing=[],
            sections=[],
        )
        flags, has_recording = [], False
    ins = c.in_short or {}
    checked = ins.get("checkedBy")
    text = ins.get("textEn") if (lang == "en" and ins.get("textEn")) else ins.get("text", c.description)
    links = ins.get("links", []) if text == ins.get("text") else ins.get("linksEn", [])
    fields = {f: getattr(base, f) for f in base.__struct_fields__}
    return w.Claim(
        **fields,
        call_id=c.call_id,
        policy_id=c.policy_id,
        holder_id=c.holder_id,
        description=c.description,
        description_en=c.description_en,
        in_short=w.InShort(
            text=text or "",
            links=[
                w.SummaryLink(start=x["start"], end=x["end"], turn_id=x["turnId"], at_seconds=x.get("atSeconds"))
                for x in links
            ],
            checked_by=PersonRef(id=checked["id"], name=checked["name"]) if checked else None,
            checked_at=datetime.fromisoformat(ins["checkedAt"]) if ins.get("checkedAt") else None,
        ),
        flags=flags,
        file=file,
        next_steps=list(c.next_steps or []),
        recording_available=has_recording,
    )


def _indicator(i: dict[str, Any], lang: str) -> w.SiuIndicator:
    source = i.get("source", "call")
    at_ms = i.get("atMs")
    at_seconds = at_ms / 1000 if isinstance(at_ms, int | float) else None
    source_label = (
        "▸ " + labels.clock_seconds(at_seconds)
        if source == "call" and at_seconds is not None
        else labels.pick(SOURCE_LABELS.get(source), lang, source)
    )
    label = i.get("label", {})
    evidence = i.get("evidence", {})
    return w.SiuIndicator(
        key=i.get("key", ""),
        label=labels.pick(label, lang) if isinstance(label, dict) else str(label),
        evidence=labels.pick(evidence, lang) if isinstance(evidence, dict) else str(evidence or ""),
        source=source,
        source_label=source_label,
        turn_id=i.get("turnId"),
        at_seconds=at_seconds,
        weight=float(i.get("weight", 0)),
    )


def routing_out(r: RoutingDecisionRow, c: Claim, lang: str, *, siu: bool, people: dict[str, User]) -> w.RoutingDecision:
    band_label = labels.pick(labels.SIZE_BANDS.get(r.severity_band), lang, r.severity_band)
    low, high = money(r.settle_low, r.currency, lang), money(r.settle_high, r.currency, lang)
    severity = w.ScoreBand(
        probability=round(r.severity_probability, 3),
        band=r.severity_band,
        label=labels.t(lang, f"Likely size: {band_label}", f"Ampleur probable : {band_label}"),
        detail=labels.t(
            lang,
            f"Claims like this usually settle at {low} to {high}",
            f"Les réclamations semblables se règlent d'habitude entre {low} et {high}",
        ),
        settle_range=w.SettleRange(low=r.settle_low, high=r.settle_high, currency=labels.lit(r.currency)),
    )
    fraud = None
    signs = None
    if siu:
        fraud_label = labels.pick(labels.FRAUD_BANDS.get(r.fraud_band), lang, r.fraud_band)
        n = len(r.fraud_indicators or [])
        fraud = w.ScoreBand(
            probability=round(r.fraud_score, 3),
            band=r.fraud_band,
            label=fraud_label,
            detail=labels.t(
                lang, f"{n} of the {r.signs_checked} signs we check", f"{n} des {r.signs_checked} signes vérifiés"
            ),
            settle_range=None,
        )
        signs = [_indicator(i, lang) for i in r.fraud_indicators or []]
    reasons = []
    for x in r.reasons or []:
        at_ms = x.get("atMs")
        text = x.get("text", {})
        reasons.append(
            w.Reason(
                feature=x.get("feature", ""),
                text=labels.pick(text, lang) if isinstance(text, dict) else str(text),
                direction=x.get("direction", "raises"),
                weight=float(x.get("weight", 0)),
                turn_id=x.get("turnId"),
                at_seconds=at_ms / 1000 if isinstance(at_ms, int | float) else None,
            )
        )
    override = None
    if r.override_route and r.override_at:
        by = person(people, r.override_by) or PersonRef(id="", name="")
        override = w.RouteOverride(
            route=labels.lit(r.override_route), reason=r.override_reason or "", by=by, at=r.override_at
        )
    rules = [labels.pick(x, lang) if isinstance(x, dict) else str(x) for x in r.rules_applied or []]
    return w.RoutingDecision(
        claim_id=c.id,
        route=labels.lit(r.route),
        route_label=labels.route(r.route, lang),
        model_route=labels.lit(r.model_route),
        decided_at=r.decided_at,
        severity=severity,
        fraud=fraud,
        reasons=reasons[:3],
        signs=signs,
        signs_checked=r.signs_checked,
        accepted_by=person(people, r.accepted_by),
        accepted_at=r.accepted_at,
        rules_applied=rules,
        model_versions={str(k): str(v) for k, v in (r.model_versions or {}).items()},
        override=override,
        statement=labels.pick(ROUTING_STATEMENT, lang),
    )


def siu_out(s: SiuReferral, c: Claim, lang: str, people: dict[str, User]) -> w.SiuReferral:
    return w.SiuReferral(
        id=s.id,
        claim_id=c.id,
        claim_number=c.claim_number,
        status=labels.lit(s.status),
        status_label=labels.pick(labels.SIU_STATUSES.get(s.status), lang, s.status),
        opened_at=s.opened_at,
        score=round(s.score, 3),
        indicators=[_indicator(i, lang) for i in s.indicators or []],
        decided_by=person(people, s.decided_by),
        decided_at=s.decided_at,
        note=s.note,
        statement=labels.pick(SIU_STATEMENT, lang),
    )


def photo_out(p: ClaimPhoto) -> w.Photo:
    return w.Photo(
        id=p.id,
        url=f"/api/v1/photos/{p.id}",
        thumbnail_url=f"/api/v1/photos/{p.id}/thumbnail",
        caption=p.caption,
        received_at=p.received_at,
        source=labels.lit(p.source),
        width=p.width,
        height=p.height,
    )
