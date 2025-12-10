"""`SqlCallSink` (docs/API_CONTRACT.md Part 3): fast, ordered writes; per-call events; and the hang-up sequence
(purge unkept turns, claim with the reserved number, routing checks, closer-look referral, quality score)."""

import statistics
import time
from datetime import timedelta

from sqlalchemy import select

from claimvoice import clock
from claimvoice.calls.models import Call, CallSlot, CallTurn, Handoff, PhotoLink, QaScoreRow, SmsMessage
from claimvoice.calls.sink import sink_for
from claimvoice.claims.models import Claim, RoutingDecisionRow
from claimvoice.contracts import (
    CallClosing,
    CallFlag,
    CallMode,
    CallOpened,
    ConsentRecord,
    FlagKind,
    HandoffReason,
    SlotRecord,
    Speaker,
    StageChange,
    ToolCallRecord,
    TurnRecord,
)
from claimvoice.platform import db
from claimvoice.platform.db import new_id
from claimvoice.platform.events import bus, call_key, org_key
from claimvoice.platform.models import Organization
from claimvoice.policies.models import Policy


async def _org_and_policy(number="LM-AB-204118"):
    async with db.sessionmaker()() as s:
        org = (await s.execute(select(Organization).where(Organization.is_sample.is_(True)))).scalar_one()
        policy = (await s.execute(select(Policy).where(Policy.policy_number == number))).scalar_one()
        return org.id, policy


def _turn(call_turns, seq, speaker, text, stage, at, **kw):
    tid = new_id()
    call_turns.append(tid)
    return TurnRecord(tid, seq, speaker, text, "en", at, at + 1500, stage, **kw)


async def _drive(sink, org_id, policy, *, consent="given", refuse=False):
    call_id = new_id()
    ids: list[str] = []
    await sink.call_opened(CallOpened(call_id, org_id, CallMode.TYPED, "en", "test", "+14035550142", "CA-AB"))
    await sink.turn(
        call_id,
        _turn(ids, 1, Speaker.LINE, "Larkspur Mutual claims. Is it okay that this call is recorded?", "consent", 0),
    )
    await sink.turn(
        call_id,
        _turn(
            ids,
            2,
            Speaker.CALLER,
            "No thanks." if refuse else "Yes, that's fine.",
            "consent",
            3000,
            retained=not refuse,
        ),
    )
    await sink.consent(
        call_id, ConsentRecord("all_party", "CA-AB", 1000, "refused" if refuse else consent, not refuse, ids[1])
    )
    await sink.stage(
        call_id, StageChange("identity", "consent", "consent_refused" if refuse else "consent_given", 4000)
    )
    await sink.turn(call_id, _turn(ids, 3, Speaker.CALLER, "It's LM-AB-204118.", "identity", 6000, retained=not refuse))
    await sink.slot(
        call_id, SlotRecord("policy_number", "LM-AB-204118", "LM-AB-204118", 0.97, "heard", ids[2], (5, 17))
    )
    await sink.tool_called(call_id, ToolCallRecord("policy_lookup", True, 120.0, 300, False, 6500, "Policy found"))
    await sink.caller_identified(call_id, policy.id, policy.holder_id, "CA-AB")
    await sink.turn(
        call_id,
        _turn(
            ids,
            4,
            Speaker.CALLER,
            "The wind tore shingles off my roof last night.",
            "loss_details",
            9000,
            retained=not refuse,
        ),
    )
    await sink.slot(call_id, SlotRecord("loss_type", "wind", "Wind", 0.95, "heard", ids[3], (4, 8)))
    await sink.slot(
        call_id, SlotRecord("loss_date", clock.today().isoformat(), "last night", 0.9, "heard", ids[3], (34, 44))
    )
    await sink.slot(call_id, SlotRecord("injury_reported", False, "No", 0.9, "heard", ids[3], None))
    await sink.slot(call_id, SlotRecord("roof_or_window_damage", True, "Yes", 0.9, "heard", ids[3], (18, 32)))
    await sink.slot(
        call_id,
        SlotRecord(
            "loss_date", clock.today().isoformat(), "this morning", 0.92, "heard", ids[3], (34, 44), corrects=True
        ),
    )
    return call_id, ids


async def test_sink_calls_return_fast_and_keep_order(seeded):
    org_id, _ = await _org_and_policy()
    sink = sink_for(org_id)
    call_id = new_id()
    await sink.call_opened(CallOpened(call_id, org_id, CallMode.TYPED, "en", "test", None, "CA-AB"))
    timings = []
    for seq in range(1, 201):
        tid = new_id()
        started = time.perf_counter()
        await sink.turn(
            call_id, TurnRecord(tid, seq, Speaker.CALLER, f"turn {seq}", "en", seq * 10, seq * 10 + 5, "loss_details")
        )
        await sink.slot(call_id, SlotRecord("extra_notes", f"note {seq}", f"note {seq}", 0.9, "heard", tid, (0, 4)))
        timings.append((time.perf_counter() - started) * 1000)
    await sink.flush(call_id)
    p95 = statistics.quantiles(timings, n=20)[18]
    assert p95 < 20, f"p95 {p95:.2f} ms"
    async with db.sessionmaker()() as s:
        seqs = (
            (await s.execute(select(CallTurn.seq).where(CallTurn.call_id == call_id).order_by(CallTurn.created_at)))
            .scalars()
            .all()
        )
        current = (
            (await s.execute(select(CallSlot).where(CallSlot.call_id == call_id, CallSlot.superseded_at.is_(None))))
            .scalars()
            .all()
        )
    assert list(seqs) == list(range(1, 201))
    assert [c.value for c in current] == ["note 200"]
    await sink.call_closed(
        call_id, CallClosing("caller_hung_up", 3000, "loss_details", None, None, "", None, 200, None)
    )
    await sink.wait_closed(call_id)


async def test_full_call_closes_into_a_claim_with_the_reserved_number(seeded):
    org_id, policy = await _org_and_policy()
    sink = sink_for(org_id)
    call_id, _ids = await _drive(sink, org_id, policy)
    number = await sink.reserve_claim_number(call_id)
    assert number.startswith("CV-")
    await sink.call_closed(call_id, CallClosing("completed", 60_000, "wrap_up", None, 60.0,
                                                "Wind damage to the roof.", None, 4, 310.0))  # fmt: skip
    await sink.wait_closed(call_id)
    async with db.sessionmaker()() as s:
        call = await s.get(Call, call_id)
        claim = (await s.execute(select(Claim).where(Claim.call_id == call_id))).scalar_one()
        routing = (
            await s.execute(select(RoutingDecisionRow).where(RoutingDecisionRow.claim_id == claim.id))
        ).scalar_one()
        qa = (await s.execute(select(QaScoreRow).where(QaScoreRow.call_id == call_id))).scalar_one()
        history = (
            (await s.execute(select(CallSlot).where(CallSlot.call_id == call_id, CallSlot.key == "loss_date")))
            .scalars()
            .all()
        )
    assert call.state == "ended" and call.outcome == "claim_created" and call.line_number is None
    assert claim.claim_number == number and claim.loss_type == "wind"
    assert routing.route in ("fast_track", "adjuster", "special_investigation")
    assert routing.features and "region" not in {k for k in routing.features if k != "region"}
    assert routing.fairness_groups["region"] == "CA-AB"
    assert qa.items and len(qa.beads) == 6
    assert sum(1 for h in history if h.superseded_at is None) == 1 and len(history) == 2


async def test_refused_consent_keeps_notes_but_not_the_transcript(seeded):
    org_id, policy = await _org_and_policy()
    sink = sink_for(org_id)
    call_id, _ = await _drive(sink, org_id, policy, refuse=True)
    await sink.call_closed(
        call_id, CallClosing("completed", 30_000, "wrap_up", None, None, "Notes only.", None, 4, None)
    )
    await sink.wait_closed(call_id)
    async with db.sessionmaker()() as s:
        kept = (await s.execute(select(CallTurn).where(CallTurn.call_id == call_id))).scalars().all()
        call = await s.get(Call, call_id)
        claim = (await s.execute(select(Claim).where(Claim.call_id == call_id))).scalar_one_or_none()
    assert [t.speaker for t in kept] == ["line"]
    assert call.consent["answer"] == "refused" and call.recording_path is None
    assert claim is not None
    assert any(f["kind"] == "consent_refused" for f in call.flags)


async def test_flags_handoffs_photo_links_and_events(seeded):
    org_id, policy = await _org_and_policy()
    sink = sink_for(org_id)
    q_org, _, _ = bus.subscribe(org_key(org_id), None)
    call_id, ids = await _drive(sink, org_id, policy)
    q_call, _, _ = bus.subscribe(call_key(call_id), None)
    await sink.partial(call_id, Speaker.CALLER, "and the gutter")
    await sink.flag(call_id, CallFlag(FlagKind.URGENT_SAFETY, "Caller smells gas", 12000, ids[3]))
    ticket = await sink.handoff_requested(call_id, HandoffReason.URGENT_SAFETY, "Smells gas near the meter")
    await sink.photo_link_sent(call_id, "•••-•••-0142", "photo-token-abc")
    await sink.flush(call_id)
    assert ticket.handoff_id and ticket.position >= 1
    async with db.sessionmaker()() as s:
        h = await s.get(Handoff, ticket.handoff_id)
        call = await s.get(Call, call_id)
        link = (await s.execute(select(PhotoLink).where(PhotoLink.call_id == call_id))).scalar_one()
        sms = (await s.execute(select(SmsMessage).where(SmsMessage.call_id == call_id))).scalar_one()
    assert h.priority == "urgent" and h.state == "waiting" and h.summary
    assert call.state == "waiting_for_person" and call.mood["key"] == "upset"
    assert link.token_hash != "photo-token-abc" and link.expires_at > clock.real_now() + timedelta(hours=71)
    assert "/p/photo-token-abc" in sms.body
    call_types = []
    while not q_call.empty():
        call_types.append(q_call.get_nowait().type)
    assert {"turn.partial", "flag.raised", "notice"} <= set(call_types)
    org_types = []
    while not q_org.empty():
        org_types.append(q_org.get_nowait().type)
    assert {"line.opened", "line.updated", "handoff.requested"} <= set(org_types)
    await sink.call_closed(call_id, CallClosing("caller_hung_up", 40_000, "handoff", None, None, "", None, 4, None))
    await sink.wait_closed(call_id)
    async with db.sessionmaker()() as s:
        assert (await s.get(Handoff, ticket.handoff_id)).state == "completed"


async def test_partial_captions_are_never_stored_or_replayed(seeded):
    org_id, _ = await _org_and_policy()
    sink = sink_for(org_id)
    call_id = new_id()
    await sink.call_opened(CallOpened(call_id, org_id, CallMode.TYPED, "en", "test", None, "CA-AB"))
    await sink.partial(call_id, Speaker.CALLER, "half a sente")
    _, replay, _ = bus.subscribe(call_key(call_id), 0)
    assert all(e.type != "turn.partial" for e in replay)
    await sink.call_closed(call_id, CallClosing("caller_hung_up", 1000, "greeting", None, None, "", None, 0, None))
    await sink.wait_closed(call_id)
    async with db.sessionmaker()() as s:
        call = await s.get(Call, call_id)
    assert call.outcome in ("abandoned", "no_claim")
