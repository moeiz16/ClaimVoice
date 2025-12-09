"""The seed is internally consistent: every name, time and number on one screen matches the others, every seeded
route and score came from the scorers, and re-seeding gives the same story."""

import time

from sqlalchemy import func, select

from claimvoice.calls.models import Call, CallSlot, CallTurn, QaScoreRow
from claimvoice.claims.models import Claim, RoutingDecisionRow
from claimvoice.platform import db
from claimvoice.policies.models import Policy

FINISHED = {
    "CV-26-01842": ("Dana Whitcombe", "wind", "fast_track"),
    "CV-26-01851": ("Arjun Bains", "wind", "adjuster"),
    "CV-26-01853": ("Leah Moreau", "wind", "fast_track"),
    "CV-26-01856": ("Tomás Reyes", "collision", "special_investigation"),
    "CV-26-01858": ("Sophie Tremblay", "water", "adjuster"),
}


async def test_line_desk_caption_matches_the_lines_and_tray(sup):
    board = await sup.j("/api/v1/switchboard")
    assert board["caption"].endswith(f"{len(board['lines'])} on the line, {len(board['handoffTray'])} waiting for a person")
    assert [x["callerLabel"] for x in board["lines"]] == ["Gord Lindqvist", "Kiara Booker", "Martine Gagnon"]
    tray = board["handoffTray"]
    assert [h["callerLabel"] for h in tray] == ["Hal Petrenko", "Wendy Arsenault"]  # urgent first
    assert tray[0]["priority"] == "urgent" and "gas" in tray[0]["detail"].lower()
    assert tray[0]["actionsTaken"] == ["Told him to leave the house and call 911", "He is outside and still on the line"]
    assert [p["name"] for p in board["freePeople"]] == ["Jamal Haddad", "Sofía Herrera", "Aurélie Fortin"]
    assert board["lastEventId"] >= 0


async def test_surge_ribbon_numbers(sup):
    surge = (await sup.j("/api/v1/switchboard"))["surge"]
    assert surge["title"] == "Chinook windstorm, Calgary"
    assert surge["multiplier"] == 3.4 and surge["sinceLabel"] == "since 6 a.m."
    assert surge["surgeQuestionsOn"] is True and surge["standbyAvailable"] == 2 and surge["standbyCalled"] is False
    assert surge["waitForPersonSeconds"] == 60 and surge["active"] is True
    assert surge["claimsSoFar"] >= 5 and surge["policiesInArea"] > 20


async def test_finished_this_morning_tickets(sup):
    board = await sup.j("/api/v1/switchboard")
    recent = {c["claimNumber"]: c for c in board["recentClaims"]}
    assert len(board["recentClaims"]) == 8
    assert board["recentClaims"][0]["claimNumber"] == "CV-26-01858"
    for number, (name, loss, _) in FINISHED.items():
        assert recent[number]["holderName"] == name and recent[number]["lossType"] == loss
    assert board["today"]["claimsCreated"] == 8


async def test_story_routes_come_from_the_routing_checks():
    async with db.sessionmaker()() as s:
        rows = (
            await s.execute(
                select(Claim.claim_number, RoutingDecisionRow.model_route, RoutingDecisionRow.route,
                       RoutingDecisionRow.model_versions)
                .join(RoutingDecisionRow, RoutingDecisionRow.claim_id == Claim.id)
                .where(Claim.claim_number.in_(FINISHED))
            )
        ).all()  # fmt: skip
    await db.dispose()
    by_number = {r[0]: r for r in rows}
    for number, (_, _, route) in FINISHED.items():
        assert by_number[number][1] == route, number
        assert by_number[number][3] == {"size": "5", "closer_look": "5"}
    assert by_number["CV-26-01856"][2] == "adjuster"  # Lena changed it; the referral stays open


async def test_every_claim_has_a_route_and_every_finished_call_a_quality_score():
    async with db.sessionmaker()() as s:
        claims = (await s.execute(select(func.count()).select_from(Claim))).scalar_one()
        routed = (await s.execute(select(func.count()).select_from(RoutingDecisionRow))).scalar_one()
        ended = (await s.execute(select(func.count()).select_from(Call).where(Call.state == "ended"))).scalar_one()
        scored = (await s.execute(select(func.count()).select_from(QaScoreRow))).scalar_one()
        policies = (await s.execute(select(func.count()).select_from(Policy))).scalar_one()
    await db.dispose()
    assert claims >= 55 and routed == claims
    assert scored == ended
    assert 190 <= policies <= 210


async def test_every_span_points_into_its_own_turn():
    async with db.sessionmaker()() as s:
        rows = (
            await s.execute(
                select(CallSlot, CallTurn).join(CallTurn, CallTurn.id == CallSlot.turn_id).where(CallSlot.span_start.is_not(None))
            )
        ).all()
    await db.dispose()
    assert len(rows) > 200
    for slot, turn in rows:
        assert slot.call_id == turn.call_id
        assert 0 <= slot.span_start < slot.span_end <= len(turn.text), (slot.key, turn.text)


async def test_times_never_run_ahead_of_now():
    from claimvoice import clock

    now = clock.now()
    async with db.sessionmaker()() as s:
        latest_call = (await s.execute(select(func.max(Call.answered_at)))).scalar_one()
        latest_claim = (await s.execute(select(func.max(Claim.reported_at)))).scalar_one()
        live = (await s.execute(select(Call).where(Call.state != "ended"))).scalars().all()
        for call in live:
            last = (await s.execute(select(func.max(CallTurn.end_ms)).where(CallTurn.call_id == call.id))).scalar_one() or 0
            assert call.answered_at.timestamp() + last / 1000 <= now.timestamp() + 1
    await db.dispose()
    assert latest_call <= now and latest_claim <= now


async def test_french_calls_carry_an_english_line_for_staff(sup):
    calls = (await sup.j("/api/v1/calls?language=fr&status=ended&pageSize=100"))["items"]
    transcript = await sup.j(f"/api/v1/calls/{calls[-1]['id']}/transcript")
    assert transcript["language"] == "fr"
    assert any(t["textEn"] for t in transcript["turns"])


async def test_quality_queue_holds_about_a_dozen_calls(sup):
    queue = await sup.j("/api/v1/qa/queue?pageSize=100")
    assert 5 <= queue["total"] <= 14
    reviewed = await sup.j("/api/v1/qa/queue?status=reviewed&pageSize=100")
    assert reviewed["total"] >= 6


async def test_reseeding_is_deterministic_and_fast(seeded):
    from claimvoice.seed import run

    async def snapshot():
        async with db.sessionmaker()() as s:
            numbers = (await s.execute(select(Claim.claim_number).order_by(Claim.claim_number))).scalars().all()
            texts = (await s.execute(select(CallTurn.text).order_by(CallTurn.text))).scalars().all()
        return numbers, texts

    before = await snapshot()
    started = time.perf_counter()
    await run()
    assert time.perf_counter() - started < 15
    after = await snapshot()
    await db.dispose()
    assert before[0] == after[0]
    assert before[1] == after[1]
