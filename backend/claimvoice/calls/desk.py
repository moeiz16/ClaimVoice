"""The line desk (docs/API_CONTRACT.md §1.8): the snapshot, today's numbers, the surge ribbon and who is free."""

from __future__ import annotations

import statistics
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.api import labels
from claimvoice.calls import views
from claimvoice.calls.models import Call, Handoff, QaScoreRow, Surge
from claimvoice.claims.models import Claim
from claimvoice.platform.events import bus, org_key
from claimvoice.platform.models import Membership, Organization, User
from claimvoice.policies.models import Policy, Policyholder
from claimvoice.schemas.base import PersonRef
from claimvoice.schemas.switchboard import Surge as SurgeOut
from claimvoice.schemas.switchboard import SwitchboardSnapshot, TodayStats

ZONE_CITY = {
    "America/Edmonton": "Calgary",
    "America/Denver": "Denver",
    "America/Toronto": "Toronto",
    "America/Montreal": "Montréal",
    "America/Vancouver": "Vancouver",
}
SURGE_SOURCE_EN = "Environment and Climate Change Canada wind warning (bundled snapshot)"


def local_midnight(org: Organization) -> datetime:
    tz = ZoneInfo(org.timezone)
    return datetime.combine(clock.today(tz), time(0), tz)


def _hour_label(dt: datetime, tz: str, lang: str) -> str:
    local = dt.astimezone(ZoneInfo(tz))
    if lang == "fr":
        return f"depuis {local.hour} h" + (f" {local.minute:02d}" if local.minute else "")
    hour = local.hour % 12 or 12
    suffix = "a.m." if local.hour < 12 else "p.m."
    return f"since {hour}{':' + format(local.minute, '02d') if local.minute else ''} {suffix}"


async def today_stats(db: AsyncSession, org_id: str) -> TodayStats:
    org = await db.get(Organization, org_id)
    assert org is not None
    start = local_midnight(org)
    calls = (
        (
            await db.execute(
                select(Call).where(Call.org_id == org_id, Call.answered_at >= start, Call.is_public_demo.is_(False))
            )
        )
        .scalars()
        .all()
    )
    ended = [c for c in calls if c.ended_at]
    handle = [(c.ended_at - c.answered_at).total_seconds() for c in ended if c.ended_at]
    handoffs = (
        await db.execute(
            select(func.count()).select_from(Handoff).where(Handoff.org_id == org_id, Handoff.requested_at >= start)
        )
    ).scalar_one()
    claims = (
        await db.execute(
            select(func.count()).select_from(Claim).where(Claim.org_id == org_id, Claim.reported_at >= start)
        )
    ).scalar_one()
    ids = [c.id for c in calls]
    qa = (await db.execute(select(QaScoreRow.score).where(QaScoreRow.call_id.in_(ids)))).scalars().all() if ids else []
    return TodayStats(
        calls_answered=len(calls),
        answered_first_ring_share=1.0 if calls else 0.0,  # the line picks up every call on the first ring
        median_handle_seconds=int(statistics.median(handle)) if handle else 0,
        handoffs=int(handoffs),
        claims_created=int(claims),
        average_qa_score=round(sum(qa) / len(qa), 1) if qa else None,
        surge_calls=sum(1 for c in calls if c.surge_id),
    )


async def surge_out(db: AsyncSession, surge: Surge, lang: str, tz: str) -> SurgeOut:
    now = clock.now()
    region_calls = (
        select(func.count())
        .select_from(Call)
        .where(Call.org_id == surge.org_id, Call.region == surge.region, Call.is_public_demo.is_(False))
    )
    last_hour = (await db.execute(region_calls.where(Call.answered_at >= now - timedelta(hours=1)))).scalar_one()
    since_start = (
        await db.execute(region_calls.where(Call.answered_at >= surge.started_at, Call.answered_at <= now))
    ).scalar_one()
    hours = max((now - surge.started_at).total_seconds() / 3600, 0.25)
    multiplier = round((since_start / hours) / surge.usual_calls_per_hour, 1) if surge.usual_calls_per_hour else 0.0
    cities = [c.strip() for c in surge.area_label.replace(" and ", ",").split(",") if c.strip()]
    in_area = (
        await db.execute(
            select(func.count())
            .select_from(Policy)
            .join(Policyholder, Policyholder.id == Policy.holder_id)
            .where(
                Policy.org_id == surge.org_id,
                Policy.region == surge.region,
                Policy.status == "active",
                or_(*[Policyholder.city == c for c in cities]) if cities else Policyholder.city.is_not(None),
            )
        )
    ).scalar_one()
    claims = (await db.execute(select(func.count()).select_from(Claim).where(Claim.surge_id == surge.id))).scalar_one()
    return SurgeOut(
        id=surge.id,
        kind=labels.lit(surge.kind),
        kind_label=labels.pick(labels.SURGE_KINDS.get(surge.kind), lang, surge.kind),
        title=surge.title,
        region=surge.region,
        region_label=labels.region(surge.region, lang) or surge.region,
        area_label=surge.area_label,
        started_at=surge.started_at,
        ended_at=surge.ended_at,
        active=surge.ended_at is None,
        headline=surge.headline,
        source=surge.source,
        calls_last_hour=int(last_hour),
        usual_calls_per_hour=surge.usual_calls_per_hour,
        multiplier=multiplier,
        since_label=_hour_label(surge.started_at, tz, lang),
        surge_questions_on=surge.surge_questions_on,
        wait_for_person_seconds=surge.wait_for_person_seconds,
        standby_available=surge.standby_available,
        standby_called=surge.standby_called_at is not None,
        policies_in_area=int(in_area),
        claims_so_far=int(claims),
        guidance=surge.guidance,
    )


async def active_surge(db: AsyncSession, org_id: str) -> Surge | None:
    return (
        await db.execute(
            select(Surge)
            .where(Surge.org_id == org_id, Surge.ended_at.is_(None))
            .order_by(Surge.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def free_people(db: AsyncSession, org_id: str, surge: Surge | None) -> list[PersonRef]:
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id, Membership.role == "intake_agent")
            .order_by(Membership.created_at)
        )
    ).all()
    busy: set[str] = set()
    live = (await db.execute(select(Call).where(Call.org_id == org_id, Call.state != "ended"))).scalars().all()
    for call in live:
        busy |= {x["userId"] for x in call.listeners or [] if x.get("mode") == "took_over"}
    accepted = (
        (await db.execute(select(Handoff.accepted_by).where(Handoff.org_id == org_id, Handoff.state == "accepted")))
        .scalars()
        .all()
    )
    busy |= {a for a in accepted if a}
    standby_ok = surge is not None and surge.standby_called_at is not None
    out = []
    for m, u in rows:
        if u.id in busy:
            continue
        if "standby" in (m.title or "").lower() and not standby_ok:
            continue
        out.append(PersonRef(id=u.id, name=u.full_name))
    return out


def names_sentence(people: list[PersonRef]) -> str:
    """ "Jamal, Sofía and Aurélie"."""
    first = [p.name.split(" ")[0] for p in people]
    if not first:
        return ""
    return first[0] if len(first) == 1 else ", ".join(first[:-1]) + " and " + first[-1]


async def snapshot(db: AsyncSession, org: Organization, lang: str, *, siu: bool) -> SwitchboardSnapshot:
    live = (
        (
            await db.execute(
                select(Call)
                .where(Call.org_id == org.id, Call.state != "ended")
                .order_by(Call.line_number, Call.answered_at)
            )
        )
        .scalars()
        .all()
    )
    on_line = [c for c in live if c.state != "waiting_for_person"]
    lines = [await views.live_line(db, c, lang, siu=siu) for c in on_line]
    tray_rows = (
        (
            await db.execute(
                select(Handoff).where(Handoff.org_id == org.id, Handoff.state.in_(("waiting", "callback_offered")))
            )
        )
        .scalars()
        .all()
    )
    calls_by_id = {c.id: c for c in live}
    people = await views.users_by_id(db, [h.accepted_by for h in tray_rows] + [h.to_user_id for h in tray_rows])
    tray = [views.handoff_out(h, calls_by_id[h.call_id], lang, people) for h in tray_rows if h.call_id in calls_by_id]
    tray.sort(key=lambda h: ({"urgent": 0, "high": 1}.get(h.priority, 2), h.requested_at))
    surge = await active_surge(db, org.id)
    from claimvoice.claims import views as claim_views

    recent = (
        (
            await db.execute(
                select(Claim)
                .where(Claim.org_id == org.id, Claim.reported_at >= local_midnight(org))
                .order_by(Claim.reported_at.desc())
                .limit(8)
            )
        )
        .scalars()
        .all()
    )
    free = await free_people(db, org.id, surge)
    now = clock.now()
    city = ZONE_CITY.get(org.timezone, org.timezone.split("/")[-1].replace("_", " "))
    on, waiting = len(on_line), len(tray)
    day = labels.day_label(clock.today(org.timezone), lang)
    at = labels.time_label(now, org.timezone, lang)
    if lang == "fr":
        caption = f"{org.name} · {day} · {at}, heure de {city} · {on} en ligne, {waiting} en attente d'une personne"
    else:
        caption = f"{org.name} · {day} · {at} {city} time · {on} on the line, {waiting} waiting for a person"
    return SwitchboardSnapshot(
        lines=lines,
        handoff_tray=tray,
        surge=await surge_out(db, surge, lang, org.timezone) if surge else None,
        recent_claims=await claim_views.summaries(db, recent, lang, siu=siu),
        free_people=free,
        caption=caption,
        today=await today_stats(db, org.id),
        last_event_id=bus.last_id(org_key(org.id)),
    )
