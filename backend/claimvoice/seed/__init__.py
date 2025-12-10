"""`make seed`: Larkspur Mutual, end to end (docs/DATA.md "Seed plan").

Order: the organisation and its people, shipped settings, the book of business, the Chinook surge, about 60 calls of
history (templated transcripts closed through the real hang-up sequence), the five "finished this morning" calls and
the five live lines (scripted callers through the real dialogue engine and `SqlCallSink`), the routing-check
registry with sign-offs, quality reviews, people's decisions and a back-dated, hash-chained activity trail.

Everything is dated relative to the demo clock's "now" (default Thursday 8 January 2026, 7:42 a.m. Calgary time) and
is deterministic. Re-running replaces the sample organisation."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.platform.models import Membership, Organization, User
from claimvoice.platform.security import hash_password
from claimvoice.seed.plan import DEMO_PASSWORD, DEMO_TIME, ORG, PERSONAS

log = structlog.get_logger("claimvoice.seed")
TZ = ZoneInfo("America/Edmonton")


async def seed_org(session: AsyncSession) -> Organization:
    """The organisation and one membership per persona. Replaces an existing sample organisation."""
    old = (await session.execute(select(Organization).where(Organization.slug == ORG["slug"]))).scalar_one_or_none()
    if old is not None:
        await session.execute(delete(Organization).where(Organization.id == old.id))
        await session.commit()
    org = Organization(
        name=ORG["name"],
        slug=ORG["slug"],
        timezone=ORG["timezone"],
        regions=list(ORG["regions"]),
        languages=list(ORG["languages"]),
        is_sample=True,
        settings={},
        created_at=clock.now() - timedelta(days=400),
    )
    session.add(org)
    await session.flush()
    password_hash: str | None = None
    for p in PERSONAS:
        user = (await session.execute(select(User).where(User.email == p.email))).scalar_one_or_none()
        if user is None:
            password_hash = password_hash or hash_password(DEMO_PASSWORD)
            user = User(
                email=p.email,
                full_name=p.full_name,
                password_hash=password_hash,
                preferred_language=p.language,
                avatar_color=p.color,
                created_at=clock.now() - timedelta(days=380),
            )
            session.add(user)
            await session.flush()
        session.add(
            Membership(
                org_id=org.id, user_id=user.id, role=p.role, title=p.title, created_at=clock.now() - timedelta(days=370)
            )
        )
    await session.commit()
    return org


class Moments:
    """Times relative to the demo moment: `at(0, "02:14")` is 2:14 a.m. today in Calgary when the clock reads 7:42."""

    def __init__(self, now: datetime) -> None:
        self.now = now
        h, m = (int(x) for x in DEMO_TIME.split(":"))
        self.anchor = timedelta(hours=h, minutes=m)

    def at(self, days_ago: int, hh_mm: str) -> datetime:
        h, m = (int(x) for x in hh_mm.split(":"))
        return self.now - self.anchor + timedelta(hours=h, minutes=m) - timedelta(days=days_ago)

    def today(self) -> date:
        return self.now.astimezone(TZ).date()


async def run() -> dict[str, int]:
    from claimvoice.calls import closing
    from claimvoice.calls.models import Call, QaScoreRow
    from claimvoice.claims.models import Claim, ModelVersion, SiuReferral
    from claimvoice.platform import db
    from claimvoice.platform.events import bus
    from claimvoice.settings.service import install_defaults

    now = clock.now()
    m = Moments(now)
    token = closing.AUDIT_ON_CLOSE.set(False)
    trail: list[Any] = []
    try:
        async with db.sessionmaker()() as session:
            org = await seed_org(session)
            people = await _people(session, org.id)
            await install_defaults(session, org, user_id=people["admin"].id)
            _org_settings(org, m)
            book = _book(session, org.id, m.today())
            await session.commit()
            surge = _surge(session, org.id, m)
            await session.commit()
            org_id, surge_id = org.id, surge.id
        rng = random.Random(8012026)  # noqa: S311  (deterministic demo data, not security)
        trail += await _history(org_id, surge_id, book, m, rng)
        trail += await _story_calls(org_id, m)
        async with db.sessionmaker()() as session:
            trail += await _decisions(session, org_id, people, m, rng)
            trail += await _governance(session, org_id, people, m)
            await session.commit()
            trail += _platform_trail(surge_id, people, m)
            counts = {
                "policies": int((await session.execute(select(func.count()).select_from(_Policy()))).scalar_one()),
                "calls": int((await session.execute(select(func.count()).select_from(Call))).scalar_one()),
                "claims": int((await session.execute(select(func.count()).select_from(Claim))).scalar_one()),
                "qa_queue": int(
                    (
                        await session.execute(
                            select(func.count()).select_from(QaScoreRow).where(QaScoreRow.status == "needs_review")
                        )
                    ).scalar_one()
                ),
                "siu_open": int(
                    (
                        await session.execute(
                            select(func.count()).select_from(SiuReferral).where(SiuReferral.status == "open")
                        )
                    ).scalar_one()
                ),
                "model_versions": int(
                    (await session.execute(select(func.count()).select_from(ModelVersion))).scalar_one()
                ),
            }
        from claimvoice.platform import auditlog

        trail.sort(key=lambda pair: pair[0])
        await auditlog.record_many(org_id, [entry for _, entry in trail])
        counts["audit"] = len(trail)
    finally:
        closing.AUDIT_ON_CLOSE.reset(token)
        from claimvoice.calls.sink import close_all

        await close_all()
        bus.reset()
    return counts


def _Policy() -> Any:  # noqa: N802
    from claimvoice.policies.models import Policy

    return Policy


async def _people(session: AsyncSession, org_id: str) -> dict[str, User]:
    rows = (
        await session.execute(
            select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.org_id == org_id)
        )
    ).all()
    by_name = {u.full_name: u for _, u in rows}
    return {
        "admin": by_name["Nadia Kassem"],
        "supervisor": by_name["Renée Kowalchuk"],
        "adjuster": by_name["Lena Ortiz"],
        "siu": by_name["Dev Malhotra"],
        "compliance": by_name["Priya Sandhu"],
        "quality": by_name["Owen Fairweather"],
        "jamal": by_name["Jamal Haddad"],
    }


def _org_settings(org: Organization, m: Moments) -> None:
    from claimvoice.settings import service

    service.put_section(
        org,
        "privacy",
        {
            "privacyOfficerName": "Priya Sandhu",
            "privacyOfficerEmail": "privacy@larkspur.example",
            "privacyNoticeUrl": "https://larkspur.example/privacy",
        },
    )
    retention = service.section(org, "retention")
    retention.update(deletionRequestsWaiting=1, lastPurgeAt=m.at(0, "03:00").isoformat())
    service.put_section(org, "retention", retention)
    settings = dict(org.settings or {})
    settings["claimSeq"] = 1858  # the next claim a live line opens is CV-26-01859
    org.settings = settings


def _book(session: AsyncSession, org_id: str, today: date) -> Any:
    from claimvoice.seed.book import build

    book = build(org_id, today)
    session.add_all(book.holders)
    session.add_all(book.policies)
    return book


def _surge(session: AsyncSession, org_id: str, m: Moments) -> Any:
    from claimvoice.calls.models import Surge
    from claimvoice.seed.plan import SURGE

    surge = Surge(
        org_id=org_id,
        kind=SURGE["kind"],
        loss_type="wind",
        region=SURGE["region"],
        area_label=SURGE["area"],
        title=SURGE["title"],
        headline=SURGE["headline"],
        alert_id=SURGE["alert_id"],
        source="Environment and Climate Change Canada wind warning (bundled snapshot)",
        started_at=m.at(0, SURGE["started"]),
        usual_calls_per_hour=SURGE["usual_calls_per_hour"],
        surge_questions_on=True,
        standby_available=SURGE["standby_available"],
        wait_for_person_seconds=SURGE["wait_for_person_seconds"],
        guidance="Wind damage to roofs, siding and skylights is covered under Home Comprehensive and Home Standard; "
        "fences up to $5,000. A person confirms coverage on every claim.",
        created_at=m.at(0, "06:00"),
    )
    session.add(surge)
    return surge


# ---------------------------------------------------------------- history


def _entry(
    at: datetime,
    action: str,
    summary: str,
    *,
    actor: User | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    target_label: str | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[datetime, Any]:
    from claimvoice.platform import auditlog

    return at, auditlog.Entry(
        action=action,
        summary=summary,
        actor_user_id=actor.id if actor else None,
        actor_label=actor.full_name if actor else auditlog.SYSTEM,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=details or {},
        at=at,
    )


def _plan_history(book: Any, m: Moments, rng: random.Random) -> list[dict[str, Any]]:
    """Who called, when, about what. Claim numbers run up to CV-26-01841 before this morning."""
    story_numbers = set(book.demo)
    candidates: dict[tuple[str, str], list[Any]] = {}
    for p in book.policies:
        if p.policy_number in story_numbers or p.status != "active":
            continue
        candidates.setdefault((p.region, p.line), []).append(p)
    plan: list[dict[str, Any]] = []
    variants = [
        "missed_consent",
        "late_handoff",
        "card_number",
        "no_safety",
        "short",
        "short",
        "short",
        "abandoned",
        "abandoned",
        "abandoned",
        "inquiry",
        "inquiry",
    ]
    n_history = 52
    for i in range(n_history):
        days_ago = 1 + int((37 * i) / n_history) + rng.choice([0, 0, 1])
        loss = rng.choices(["collision", "water", "theft", "wind", "fire"], [36, 30, 16, 12, 6])[0]
        if 18 <= days_ago <= 26 and rng.random() < 0.5:
            loss = "water"  # the mid-December cold snap
        region = rng.choices(["CA-AB", "US-CO", "CA-QC"], [50, 30, 20])[0]
        line = (
            "auto"
            if loss == "collision"
            else ("property" if loss in ("water", "wind", "fire") else rng.choice(["auto", "property"]))
        )
        policy = rng.choice(candidates[(region, line)])
        variant = variants[i] if i < len(variants) and i % 4 == 1 else "normal"
        late = rng.random() < 0.06
        plan.append(
            {
                "policy": policy,
                "loss": loss,
                "days_ago": min(days_ago, 37),
                "variant": variant,
                "time": f"{rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}",
                "late": late,
                "injury": loss == "collision" and rng.random() < 0.12,
            }
        )
    for v in variants:  # every quality-review variant appears at least once
        if not any(p["variant"] == v for p in plan):
            spare = next(p for p in plan if p["variant"] == "normal" and p["days_ago"] < 14)
            spare["variant"] = v
    plan.sort(key=lambda p: (-p["days_ago"], p["time"]))
    # this morning, besides the five scripted story calls
    ab_home = candidates[("CA-AB", "property")]
    morning = [
        {"policy": ab_home[1], "loss": "wind", "days_ago": 0, "time": "03:05", "variant": "normal", "number": 1845},
        {"policy": ab_home[2], "loss": "wind", "days_ago": 0, "time": "03:40", "variant": "abandoned"},
        {"policy": ab_home[3], "loss": "wind", "days_ago": 0, "time": "04:40", "variant": "normal", "number": 1848},
        {"policy": ab_home[4], "loss": "wind", "days_ago": 0, "time": "06:09", "variant": "abandoned"},
        {"policy": ab_home[5], "loss": "wind", "days_ago": 0, "time": "06:30", "variant": "inquiry"},
        {"policy": ab_home[6], "loss": "wind", "days_ago": 0, "time": "06:58", "variant": "normal", "number": 1857},
        {"policy": ab_home[7], "loss": "wind", "days_ago": 0, "time": "07:12", "variant": "inquiry"},
    ]
    for p in morning:
        p.setdefault("late", False)
        p.setdefault("injury", False)
    return plan + morning


def _fixture_moment(m: Moments, i: int) -> datetime:
    return m.at(2 + i * 2, f"{9 + i % 9:02d}:{(i * 13) % 60:02d}")


def _number_history(plan: list[dict[str, Any]], book: Any, m: Moments, rng: random.Random) -> dict[int, int]:
    """Claim numbers in report order for the month before this morning, ending at CV-26-01841 (this morning's
    numbers are fixed). Returns the numbers for the reviewed calls that open a claim, by their index."""
    try:
        from claimvoice.qa.fixtures import reviewed_calls

        fixtures = list(reviewed_calls().values())
    except ImportError:
        fixtures = []
    items: list[tuple[datetime, Any]] = []
    for p in plan:
        if "number" not in p and p["variant"] not in ("abandoned", "inquiry"):
            items.append((m.at(p["days_ago"], p["time"]), p))
    for i, fx in enumerate(fixtures):
        number = fx.slots.get("policy_number")
        if fx.slots.get("loss_type") and number is not None and str(number.value) in book.by_number:
            items.append((_fixture_moment(m, i), i))
    items.sort(key=lambda x: x[0])
    gaps = [rng.choice([1, 1, 1, 2]) for _ in items]
    n = 1841 - sum(gaps[1:])
    fixture_numbers: dict[int, int] = {}
    for (_, item), gap in zip(items, gaps, strict=True):
        n += gap if item is not items[0][1] else 0
        if isinstance(item, int):
            fixture_numbers[item] = n
        else:
            item["number"] = n
    return fixture_numbers


INQUIRY = {
    "en": [
        "Hi, I'm calling about the claim I made last week.",
        "Thanks. I've noted that, and the adjuster on your claim "
        "will call you back today. Is there anything new to add?",
        "No, I just wanted an update. Thanks.",
    ],
    "fr": [
        "Bonjour, j'appelle pour la réclamation que j'ai faite la semaine dernière.",
        "Merci. C'est noté, et l'expert "
        "responsable vous rappellera aujourd'hui. Avez-vous quelque chose de nouveau à ajouter?",
        "Non, je voulais juste des nouvelles. Merci.",
    ],
}


async def _history(org_id: str, surge_id: str, book: Any, m: Moments, rng: random.Random) -> list[Any]:
    from claimvoice.calls import closing
    from claimvoice.platform import db
    from claimvoice.seed import history as h

    trail: list[Any] = []
    holders = {x.id: x for x in book.holders}
    per_day: dict[date, int] = {}
    today = m.today()
    plan = _plan_history(book, m, rng)
    fixture_numbers = _number_history(plan, book, m, rng)
    async with db.sessionmaker()() as session:
        for item in plan:
            policy = item["policy"]
            holder = holders[policy.holder_id]
            answered = m.at(item["days_ago"], item["time"])
            local_day = answered.astimezone(TZ).date()
            loss_date = local_day - timedelta(days=rng.choice([0, 0, 0, 1, 1, 2]))
            if item["late"]:
                loss_date = local_day - timedelta(days=rng.randint(18, 30))
            lang = "fr" if policy.region == "CA-QC" else "en"
            number = item.get("number")
            year = (answered.astimezone(TZ).year) % 100
            story = h.Story(
                holder=holder,
                policy=policy,
                loss_type=item["loss"],
                answered_at=answered,
                loss_date=loss_date,
                language=lang,
                variant=item["variant"],
                injury=item["injury"],
                claim_number=f"CV-{year:02d}-{number:05d}" if number else None,
            )
            state = rng.getstate()
            inquiry = item["variant"] == "inquiry"
            turns = _inquiry_turns(story) if inquiry else h.build_turns(rng, story, local_day)
            if lang == "fr" and item["variant"] != "inquiry":
                twin = random.Random()  # noqa: S311
                twin.setstate(state)
                story_en = replace(story, language="en", extra={})
                en_turns = h.build_turns(twin, story_en, local_day)
                story.extra["description_en"] = story_en.extra.get("description")
            else:
                en_turns = []
            per_day[local_day] = per_day.get(local_day, 0) + 1
            reference = f"CALL-{local_day:%y%m%d}-{per_day[local_day]:03d}"
            call, rows = h.write_call(session, org_id, story, turns, reference=reference, rng=rng)
            if en_turns and len(en_turns) == len(turns):
                texts = iter(t.text for t in en_turns)
                for row in rows:
                    if row.__class__.__name__ == "CallTurn":
                        row.text_en = next(texts, None)
            if lang == "fr" and call.summary and not call.summary_en:
                call.summary_en = story.extra.get("description_en")
            if local_day == today and policy.region == "CA-AB" and item["loss"] == "wind":
                call.surge_id = surge_id
                call.flags = [
                    *call.flags,
                    {
                        "kind": "surge",
                        "detail": "In the Chinook windstorm area",
                        "at": answered.isoformat(),
                        "turnId": None,
                    },
                ]
            if item["variant"] == "inquiry":
                call.loss_type = None
            session.add(call)
            await session.flush()
            session.add_all(rows)
            await session.flush()
            result = await closing.finalize(session, call)
            if result.claim_id:
                trail.append(
                    _entry(
                        call.ended_at or answered,
                        "claim.created",
                        f"ClaimVoice opened claim {result.claim_number} at the end of {reference}.",
                        target_type="claim",
                        target_id=result.claim_id,
                        target_label=result.claim_number,
                    )
                )
            if result.siu_opened:
                trail.append(
                    _entry(
                        call.ended_at or answered,
                        "siu.referral_opened",
                        f"The closer-look check asked special investigations to review {result.claim_number}.",
                        target_type="claim",
                        target_id=result.claim_id,
                        target_label=result.claim_number,
                    )
                )
        trail += await _reviewed_calls(session, org_id, book, m, per_day, fixture_numbers)
        await session.commit()
    return trail


async def _reviewed_calls(
    session: Any, org_id: str, book: Any, m: Moments, per_day: dict[date, int], numbers: dict[int, int]
) -> list[Any]:
    """Calls with known quality problems (missed consent, a late hand-off, a card number read aloud, ...), from the
    quality scorer's reviewed set, so the review queue shows what the scorer really flags."""
    from claimvoice.calls import closing
    from claimvoice.calls.models import Call, CallEvent, CallSlot, CallTurn, Handoff
    from claimvoice.platform.db import new_id

    try:
        from claimvoice.qa.fixtures import reviewed_calls
    except ImportError:
        return []
    trail: list[Any] = []
    holders = {x.id: x for x in book.holders}
    for i, fx in enumerate(reviewed_calls().values()):
        answered = _fixture_moment(m, i)
        local_day = answered.astimezone(TZ).date()
        per_day[local_day] = per_day.get(local_day, 0) + 1
        number_slot = fx.slots.get("policy_number")
        policy = book.by_number.get(str(number_slot.value)) if number_slot is not None else None
        holder = holders.get(policy.holder_id) if policy is not None else None
        consent = next((e["data"] for e in fx.events if e["kind"] == "consent"), None)
        flags = [
            {
                "kind": e["data"]["kind"],
                "detail": e["data"].get("detail", ""),
                "at": (answered + timedelta(milliseconds=e["atMs"])).isoformat(),
                "turnId": e["data"].get("turnId"),
            }
            for e in fx.events
            if e["kind"] == "flag"
        ]
        last_ms = max(t.end_ms for t in fx.turns)
        loss = fx.slots.get("loss_type")
        call = Call(
            id=new_id(),
            org_id=org_id,
            reference=f"CALL-{local_day:%y%m%d}-{per_day[local_day]:03d}",
            mode="voice",
            channel="phone",
            language=fx.language,
            state="ended",
            stage="ended",
            answered_at=answered,
            ended_at=answered + timedelta(milliseconds=last_ms + 1500),
            end_reason="completed",
            caller_name=holder.full_name if holder else None,
            caller_verified=holder is not None,
            region=fx.region,
            place=holder.city if holder else None,
            loss_type=loss.value if loss else None,
            policy_id=policy.id if policy else None,
            holder_id=holder.id if holder else None,
            consent={**consent, "askedAt": answered.isoformat(), "turnId": None} if consent else {},
            recording_seconds=round((last_ms + 1500) / 1000, 1),
            outcome="in_progress",
            is_sample=True,
            flags=flags,
            mood={"key": "calm", "detail": None},
            turn_count=len(fx.turns),
            resume_stage=fx.turns[-1].stage,
            summary=fx.title,
            claim_number=f"CV-{answered.astimezone(TZ).year % 100:02d}-{numbers[i]:05d}" if i in numbers else None,
        )
        session.add(call)
        await session.flush()
        for t in fx.turns:
            session.add(
                CallTurn(
                    id=new_id(),
                    org_id=org_id,
                    call_id=call.id,
                    seq=t.seq,
                    speaker=t.speaker.value,
                    speaker_name=t.speaker_name or (fx.person if t.speaker.value == "person" else None),
                    text=t.text,
                    language=t.language,
                    at_ms=t.at_ms,
                    end_ms=t.end_ms,
                    stage=t.stage,
                    confidence=t.confidence,
                    interrupted=t.interrupted,
                    redactions=t.redactions,
                    retained=t.retained,
                    flags=["card_number_removed"] if t.redactions else [],
                )
            )
        for key, slot in fx.slots.items():
            session.add(
                CallSlot(
                    org_id=org_id,
                    call_id=call.id,
                    key=key,
                    value=slot.value,
                    display=slot.display,
                    confidence=slot.confidence,
                    source=slot.source,
                    confirmed=True,
                    created_at=answered,
                )
            )
        for e in fx.events:
            at = answered + timedelta(milliseconds=e["atMs"])
            session.add(
                CallEvent(
                    org_id=org_id,
                    call_id=call.id,
                    at=at,
                    at_ms=e["atMs"],
                    kind=e["kind"],
                    label=e["kind"].replace("_", " ").capitalize(),
                    data=dict(e["data"]),
                )
            )
            if e["kind"] == "handoff":
                reason = e["data"].get("reason", "caller_asked")
                session.add(
                    Handoff(
                        org_id=org_id,
                        call_id=call.id,
                        reason=reason,
                        detail=fx.title,
                        priority=e["data"].get("priority", "normal"),
                        state="completed",
                        requested_at=at,
                        accepted_at=at + timedelta(seconds=20),
                        resolved_at=call.ended_at,
                        summary=fx.title,
                    )
                )
        await session.flush()
        result = await closing.finalize(session, call)
        if result.claim_id:
            trail.append(
                _entry(
                    call.ended_at or answered,
                    "claim.created",
                    f"ClaimVoice opened claim {result.claim_number} at the end of {call.reference}.",
                    target_type="claim",
                    target_id=result.claim_id,
                    target_label=result.claim_number,
                )
            )
    return trail


def _inquiry_turns(story: Any) -> list[Any]:
    from claimvoice.seed.history import Say

    lang = story.language
    t = INQUIRY[lang]
    return [
        Say(
            "line",
            "greeting",
            "Larkspur Mutual claims, this is ClaimVoice. What can I do for you?"
            if lang == "en"
            else "Mutuelle Larkspur, réclamations, ici ClaimVoice. Que puis-je faire pour vous?",
        ),
        Say("caller", "greeting", t[0]),
        Say(
            "line",
            "consent",
            "This call is recorded to help with your claim. Is that okay with you?"
            if lang == "en"
            else "Cet appel est enregistré pour traiter votre réclamation. Êtes-vous d'accord?",
        ),
        Say("caller", "consent", "Sure." if lang == "en" else "Oui."),
        Say(
            "line",
            "identity",
            "Thanks. What's your policy number?" if lang == "en" else "Merci. Quel est votre numéro de police?",
        ),
        Say(
            "caller",
            "identity",
            story.policy.policy_number,
            [("policy_number", story.policy.policy_number, story.policy.policy_number)],
        ),
        Say("line", "wrap_up", t[1]),
        Say("caller", "wrap_up", t[2]),
    ]


# ---------------------------------------------------------------- the scripted story calls and live lines


STORY_CALLS = (
    ("dana-skylight", "02:14", 1842),
    ("arjun-shingles", "06:21", 1851),
    ("leah-fence", "06:38", 1853),
    ("tomas-rear-end", "06:47", 1856),
    ("sophie-frozen-pipe", "07:05", 1858),
)
LIVE_TARGET = {"calgary-windstorm": "loss_details", "denver-rear-end": "loss_details", "montreal-basement": "photos"}
HANDOFF_SCENARIOS = {"airdrie-gas": "airdrie-gas", "calgary-fence": "bridgeland-fence-person"}


async def _set_claim_seq(org_id: str, value: int) -> None:
    from claimvoice.calls.sink import forget_claim_counter
    from claimvoice.platform import db

    forget_claim_counter(org_id)
    async with db.sessionmaker()() as session:
        org = await session.get(Organization, org_id)
        assert org is not None
        settings = dict(org.settings or {})
        settings["claimSeq"] = value
        org.settings = settings
        await session.commit()


async def _scenario(org_id: str, key: str, answered: datetime, **kwargs: Any) -> tuple[str, Any]:
    from claimvoice.calls.sink import sink_for
    from claimvoice.dialogue.simulate import run_scenario
    from claimvoice.platform.db import new_id
    from claimvoice.policies.directory import get_directory
    from claimvoice.settings.playbook import get_playbook

    sink = sink_for(org_id)
    call_id = new_id()
    with clock.travel(answered):
        result = await run_scenario(
            key,
            sink,
            org_id=org_id,
            call_id=call_id,
            policies=get_directory(),
            playbook=get_playbook(),
            answered_at=answered,
            **kwargs,
        )
        await sink.flush(call_id)
        await sink.wait_closed(call_id)
    return call_id, result


async def _dry_run(key: str, target: str | None) -> tuple[int, int]:
    """The most caller turns that still leave the call at `target`, and how long the call has run by then (ms)."""
    from claimvoice.contracts import MemoryCallSink
    from claimvoice.dialogue.simulate import load_callers, run_scenario

    best = (1, 60_000)
    for n in range(1, len(load_callers()[key].turns) + 1):
        sink = MemoryCallSink()
        res = await run_scenario(key, sink, upto_caller_turn=n, hang_up_after=False)
        if target is None or str(res.stage_at_end_of_script) == target:
            best = (n, max((t.end_ms for t in sink.of("turn")), default=0) or best[1])
    return best


async def _story_calls(org_id: str, m: Moments) -> list[Any]:
    from claimvoice.calls.models import Call, Handoff
    from claimvoice.dialogue.simulate import load_callers
    from claimvoice.platform import db
    from claimvoice.seed.plan import LIVE_LINES

    callers = load_callers()
    trail: list[Any] = []
    for key, hh_mm, number in STORY_CALLS:
        if key not in callers:
            log.warning("seed_story_caller_missing", key=key)
            continue
        await _set_claim_seq(org_id, number - 1)
        await _scenario(org_id, key, m.at(0, hh_mm))
    await _set_claim_seq(org_id, 1858)
    # live lines, in line order
    for line in LIVE_LINES:
        scenario = HANDOFF_SCENARIOS.get(line["scenario"], line["scenario"])
        if scenario not in callers:
            log.warning("seed_live_caller_missing", key=scenario)
            continue
        minutes = float(line["answered"])
        upto, ran_ms = await _dry_run(scenario, LIVE_TARGET.get(scenario))
        # the call has been on the line for as long as its turns took, plus the caller thinking about the next answer
        thinking = {1: 18_000, 2: 52_000, 3: 36_000, 4: 75_000, 5: 44_000}.get(line["line"], 30_000)
        elapsed = timedelta(milliseconds=ran_ms + thinking) if ran_ms > 30_000 else timedelta(minutes=minutes)
        call_id, _result = await _scenario(
            org_id, scenario, m.now - elapsed, upto_caller_turn=upto, hang_up_after=False
        )
        async with db.sessionmaker()() as session:
            call = await session.get(Call, call_id)
            assert call is not None
            call.scenario = line["scenario"] if scenario == line["scenario"] else scenario
            call.mood = {
                "key": line["mood"],
                "detail": {"shaken": "speaking slower", "upset": "speaking fast"}.get(line["mood"]),
            }
            call.place = line["place"]
            call.heard = [
                {"key": f"pill{i}", "text": text, "tone": "caution" if text in ("Sore neck",) else "normal"}
                for i, text in enumerate(reversed(line.get("heard", [])))
            ] or call.heard
            if not call.caller_name:  # not verified yet, but caller ID matches the policyholder's phone on file
                call.caller_name = line["caller"]
            handoff = (await session.execute(select(Handoff).where(Handoff.call_id == call_id))).scalars().first()
            if handoff is not None:
                handoff.requested_at = min(
                    m.now - timedelta(seconds=40), call.answered_at + timedelta(milliseconds=ran_ms)
                )
                handoff.actions = list(line.get("actions", handoff.actions))
                handoff.detail = line.get("detail", handoff.detail)
                if not call.caller_verified:
                    handoff.summary = (
                        f"{line['caller']} (caller ID matches the policy on file), {line['place']}.\n{line['detail']}"
                    )
            await session.commit()
    return trail


# ---------------------------------------------------------------- people's decisions after the calls


async def _decisions(
    session: AsyncSession, org_id: str, people: dict[str, User], m: Moments, rng: random.Random
) -> list[Any]:
    from claimvoice.calls.models import Call, QaScoreRow
    from claimvoice.claims.models import Claim, RoutingDecisionRow, SiuReferral
    from claimvoice.policies.models import Policy

    trail: list[Any] = []
    today = m.today()
    claims = (
        (await session.execute(select(Claim).where(Claim.org_id == org_id).order_by(Claim.reported_at))).scalars().all()
    )
    for c in claims:
        policy = await session.get(Policy, c.policy_id)
        routing = (
            await session.execute(select(RoutingDecisionRow).where(RoutingDecisionRow.claim_id == c.id))
        ).scalar_one_or_none()
        age = (today - c.reported_at.astimezone(TZ).date()).days
        owner = people["adjuster"] if policy is not None and policy.region == "US-CO" else people["supervisor"]
        if age >= 1:
            c.status = (
                "closed"
                if age > 12 and rng.random() < 0.7
                else rng.choice(["in_review", "assigned", "waiting_on_customer"])
            )
            if policy is not None and policy.region == "US-CO":
                c.assigned_to = people["adjuster"].id
            if routing is not None and routing.route != "special_investigation":
                routing.accepted_by, routing.accepted_at = (
                    owner.id,
                    c.reported_at + timedelta(hours=2, minutes=rng.randint(0, 50)),
                )
                trail.append(
                    _entry(
                        routing.accepted_at,
                        "claim.route_accepted",
                        f"{owner.full_name} accepted the {routing.route.replace('_', '-')} route for {c.claim_number}.",
                        actor=owner,
                        target_type="claim",
                        target_id=c.id,
                        target_label=c.claim_number,
                        details={"route": routing.route},
                    )
                )
        referral = (await session.execute(select(SiuReferral).where(SiuReferral.claim_id == c.id))).scalar_one_or_none()
        if referral is not None and age >= 3:
            referral.status, referral.decided_by = "closed_no_concern", people["siu"].id
            referral.decided_at = referral.opened_at + timedelta(days=2, hours=3)
            referral.note = "Spoke with the policyholder and checked the police report; nothing further."
            trail.append(
                _entry(
                    referral.decided_at,
                    "siu.decision",
                    f"Dev Malhotra marked the closer-look referral on {c.claim_number} “closed, no concern”.",
                    actor=people["siu"],
                    target_type="claim",
                    target_id=c.id,
                    target_label=c.claim_number,
                    details={"decision": "close_no_concern"},
                )
            )
    # Tomás Reyes: the closer-look check sent it to special investigations; Lena changed the route, the referral stays.
    tomas = next((c for c in claims if c.claim_number.endswith("01856")), None)
    if tomas is not None:
        routing = (
            await session.execute(select(RoutingDecisionRow).where(RoutingDecisionRow.claim_id == tomas.id))
        ).scalar_one_or_none()
        tomas.assigned_to, tomas.status = people["adjuster"].id, "assigned"
        at = m.at(0, "07:20")
        reason = "Police report confirms the SUV."
        ins = dict(tomas.in_short or {})
        ins.update(
            checkedBy={"id": people["adjuster"].id, "name": "Lena Ortiz"}, checkedAt=m.at(0, "07:16").isoformat()
        )
        tomas.in_short = ins
        trail.append(
            _entry(
                m.at(0, "07:14"),
                "recording.played",
                "Lena Ortiz played the recording of CV-26-01856.",
                actor=people["adjuster"],
                target_type="claim",
                target_id=tomas.id,
                target_label=tomas.claim_number,
            )
        )
        if routing is not None and routing.route != "adjuster":
            before = routing.route
            routing.override_route, routing.override_reason = "adjuster", reason
            routing.override_by, routing.override_at, routing.route = people["adjuster"].id, at, "adjuster"
            trail.append(
                _entry(
                    at,
                    "claim.route_override",
                    f"Lena Ortiz changed CV-26-01856 from {_route_words(before)} to Adjuster: “{reason}”",
                    actor=people["adjuster"],
                    target_type="claim",
                    target_id=tomas.id,
                    target_label=tomas.claim_number,
                    details={"from": before, "to": "adjuster", "reason": reason},
                )
            )
    # Quality: keep about a dozen calls in the review queue; Owen has reviewed the rest of the flagged ones and a
    # sample of the calls that met the rubric.
    rows = (
        await session.execute(
            select(QaScoreRow, Call)
            .join(Call, Call.id == QaScoreRow.call_id)
            .where(QaScoreRow.org_id == org_id)
            .order_by(Call.answered_at)
        )
    ).all()
    queued = [(r, c) for r, c in rows if r.status == "needs_review" and c.state == "ended"]
    keep = 12
    to_review = queued[: max(0, len(queued) - keep)]
    sample = [
        (r, c) for r, c in rows if r.status == "auto_passed" and (today - c.answered_at.astimezone(TZ).date()).days > 7
    ][:6]
    for i, (r, qcall) in enumerate([*to_review, *sample]):
        verdicts = [{"key": it["key"], "verdict": "agree", "note": None} for it in r.items if it["passed"] is not None]
        if i == 1 and verdicts:
            for v in verdicts:
                if v["key"] == "empathy":
                    v["verdict"], v["note"] = "disagree", "The line acknowledged the caller twice; this should pass."
        r.status, r.reviewed_by = "reviewed", people["quality"].id
        r.reviewed_at = (qcall.ended_at or qcall.answered_at) + timedelta(days=1, hours=2)
        r.review = {"items": verdicts, "note": "Listened to the whole call."}
        if r.reviewed_at < m.now:
            trail.append(
                _entry(
                    r.reviewed_at,
                    "qa.review",
                    f"Owen Fairweather reviewed {qcall.reference}.",
                    actor=people["quality"],
                    target_type="call",
                    target_id=qcall.id,
                    target_label=qcall.reference,
                )
            )
    await session.flush()
    return trail


# ---------------------------------------------------------------- routing checks: registry and sign-offs


async def _governance(session: AsyncSession, org_id: str, people: dict[str, User], m: Moments) -> list[Any]:
    from claimvoice.claims import checks
    from claimvoice.claims.models import CheckSignoff

    trail: list[Any] = []
    registry = checks.load_registry()
    if not registry:
        log.warning("seed_routing_registry_missing")
        return trail
    rows = await checks.mirror_registry(session, org_id, registry, today=m.today())
    names = {"size": "size check", "closer_look": "closer-look check"}
    by_check: dict[str, list[Any]] = {}
    for r in rows:
        by_check.setdefault(r.check_key, []).append(r)
    for key, versions in by_check.items():
        versions.sort(key=lambda v: v.version)
        starts = {v.version: v.in_use_since for v in versions}
        for v in versions:
            if v.stage == "candidate" or v.in_use_since is None:
                continue
            days = (m.today() - v.in_use_since).days
            since = m.at(days, "10:00")
            if v.stage == "retired":
                later = [d for ver, d in starts.items() if ver > v.version and d is not None]
                v.retired_at = m.at((m.today() - min(later)).days, "10:00") if later else None
            label = f"{names[key].capitalize()} v{v.version}"
            for side, person, offset, note in (
                ("model_risk", people["compliance"], 2, "Gates pass; fairness within band; fact sheet reviewed."),
                ("claims", people["supervisor"], 1, "Reasons read well to adjusters; fast-track mix looks right."),
            ):
                at = m.at(days + offset, "15:10")
                session.add(
                    CheckSignoff(
                        org_id=org_id, model_version_id=v.id, side=side, user_id=person.id, note=note, signed_at=at
                    )
                )
                trail.append(
                    _entry(
                        at,
                        "check.signed_off",
                        f"{person.full_name} signed off version {v.version} of the {names[key]} for "
                        f"{checks.SIDE_LABELS[side].lower()}: “{note}”",
                        actor=person,
                        target_type="routing_check",
                        target_id=key,
                        target_label=label,
                        details={"side": side, "version": v.version},
                    )
                )
            trail.append(
                _entry(
                    since,
                    "check.version_in_use",
                    f"Version {v.version} of the {names[key]} went into use after two sign-offs.",
                    target_type="routing_check",
                    target_id=key,
                    target_label=label,
                    details={"version": v.version},
                )
            )
    await session.flush()
    return trail


def _route_words(route: str) -> str:
    return {"special_investigation": "Closer look", "fast_track": "Fast-track", "adjuster": "Adjuster"}.get(
        route, route
    )


def _platform_trail(surge_id: str, people: dict[str, User], m: Moments) -> list[Any]:
    trail = [
        _entry(
            m.at(37, "09:12"),
            "settings.privacy_changed",
            "Nadia Kassem named Priya Sandhu as privacy officer.",
            actor=people["admin"],
            target_type="settings",
            target_id="privacy",
            target_label="Privacy officer",
        ),
        _entry(
            m.at(30, "11:40"),
            "settings.retention_changed",
            "Nadia Kassem set retention to 7 years for recordings, 7 for transcripts and 7 for photos.",
            actor=people["admin"],
            target_type="settings",
            target_id="retention",
            target_label="Retention",
        ),
        _entry(
            m.at(0, "03:00"),
            "retention.purged",
            "Retention checked recordings, transcripts and photos; nothing was past its keep period.",
            target_type="retention",
            target_id="daily",
            target_label="Retention",
            details={"recordings": 0, "transcripts": 0, "photos": 0},
        ),
        _entry(
            m.at(0, "06:02"),
            "auth.login",
            "Renée Kowalchuk signed in.",
            actor=people["supervisor"],
            target_type="user",
            target_id=people["supervisor"].id,
            target_label="Renée Kowalchuk",
        ),
        _entry(
            m.at(0, "06:06"),
            "surge.questions",
            "Renée Kowalchuk switched the wind surge questions on.",
            actor=people["supervisor"],
            target_type="surge",
            target_id=surge_id,
            target_label="Chinook windstorm, Calgary",
            details={"on": True},
        ),
        _entry(
            m.at(0, "06:44"),
            "auth.login",
            "Lena Ortiz signed in.",
            actor=people["adjuster"],
            target_type="user",
            target_id=people["adjuster"].id,
            target_label="Lena Ortiz",
        ),
        _entry(
            m.at(0, "07:25"),
            "auth.login",
            "Dev Malhotra signed in.",
            actor=people["siu"],
            target_type="user",
            target_id=people["siu"].id,
            target_label="Dev Malhotra",
        ),
        _entry(
            m.at(0, "07:31"),
            "auth.login",
            "Owen Fairweather signed in.",
            actor=people["quality"],
            target_type="user",
            target_id=people["quality"].id,
            target_label="Owen Fairweather",
        ),
    ]
    return trail
