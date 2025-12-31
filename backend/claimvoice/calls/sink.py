"""`SqlCallSink`: how the voice runtime's call facts reach the database and the line desk (docs/API_CONTRACT.md
Part 3).

Every method returns in well under 20 ms: it updates a little in-memory state, publishes the per-call SSE event that
needs no database read, and appends the write to the call's queue. One writer task per call drains the queue in
order, in its own session, so a slot can never be written before its turn and the turn path never waits on SQLite.
After each write, when the queue is empty, the writer republishes the line (`line.updated`) for the line desk.

`call_closed` flushes the queue and hands the call to `calls.closing`, which purges what may not be kept, creates the
claim, runs the routing checks and the quality scorer, and publishes the results."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.api import labels
from claimvoice.calls import views
from claimvoice.calls.models import Call, CallEvent, CallSlot, CallTurn, Handoff, PhotoLink, SmsMessage, Surge
from claimvoice.config import get_settings
from claimvoice.contracts import (
    CallClosing,
    CallFlag,
    CallOpened,
    ConsentRecord,
    HandoffReason,
    HandoffTicket,
    SlotRecord,
    Speaker,
    StageChange,
    ToolCallRecord,
    TurnLatency,
    TurnRecord,
)
from claimvoice.dialogue.summary import facts, in_brief
from claimvoice.platform import db
from claimvoice.platform.events import bus, call_key, org_key
from claimvoice.platform.models import Organization
from claimvoice.platform.security import token_digest
from claimvoice.policies.models import Policy, Policyholder
from claimvoice.schemas import calls as w

log = structlog.get_logger("claimvoice.sink")

Op = Callable[[AsyncSession, Any], Awaitable[None]]
PHOTO_LINK_HOURS = 72
EVENT_LANG = "en"  # SSE payload labels; each page reloads in the viewer's language from the REST snapshot

TOOL_LABELS = {
    "policy_lookup": ("Policy found in {s} s", "The policy lookup didn't answer in time"),
    "identity_check": ("Identity checked in {s} s", "The identity check didn't answer in time"),
    "coverage_check": ("Coverage looked up in {s} s", "The coverage lookup didn't answer in time"),
    "photo_link_sms": ("Photo link texted in {s} s", "The photo link couldn't be texted"),
    "weather_lookup": ("Weather records checked in {s} s", "Weather records didn't answer in time"),
}

# Facts worth a pill on the line strip (most recent first, at most 4). Caution pills are amber on the desk.
HEARD_PILLS: dict[str, tuple[str, str]] = {
    "roof_or_window_damage": ("Roof or window damage", "normal"),
    "siding_or_fence_damage": ("Siding or fence damage", "normal"),
    "open_to_weather": ("Open to the weather", "caution"),
    "water_still_entering": ("Water still coming in", "caution"),
    "other_party_involved": ("Another driver involved", "normal"),
    "vehicle_drivable": ("Car can't be driven", "normal"),
    "injury_detail": ("", "caution"),
    "debris_source": ("", "normal"),
    "damage_areas": ("", "normal"),
    "water_source": ("", "normal"),
    "items_stolen": ("", "normal"),
}


@dataclass
class _Live:
    """What the sink remembers about a live call between writes."""

    call_id: str
    org_id: str
    language: str = "en"
    caller_name: str | None = None
    turn_ms: dict[str, int] = field(default_factory=dict)
    last_ms: int = 0  # end of the latest turn (virtual time for scripted calls, real time for live ones)
    latencies: list[float] = field(default_factory=list)
    queue: asyncio.Queue[tuple[Op | None, asyncio.Future[None] | None, bool]] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None
    closing: asyncio.Task[None] | None = None


_claim_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_claim_next: dict[str, int] = {}


async def allocate_claim_number(org_id: str, year: int) -> str:
    """The next claim number for the organisation: CV-<yy>-<running number> (the running number never resets).

    Kept in memory and seeded from the database once (a read, so it never waits on another writer); the counter is
    persisted with the claim it numbers (`calls.closing`). A reserved number whose call ends without a claim leaves a
    gap, as on any claims system."""
    async with _claim_locks[org_id]:
        if org_id not in _claim_next:
            from claimvoice.claims.models import Claim

            async with db.sessionmaker()() as session:
                org = await session.get(Organization, org_id)
                seq = (org.settings or {}).get("claimSeq") if org else None
                if seq is None:  # no counter yet: continue after the highest number on file
                    numbers = (
                        await session.execute(select(Claim.claim_number).where(Claim.org_id == org_id))
                    ).scalars()
                    tails = [int(n.rsplit("-", 1)[-1]) for n in numbers if n.rsplit("-", 1)[-1].isdigit()]
                    seq = max(tails, default=1800)
            _claim_next[org_id] = int(seq)
        _claim_next[org_id] += 1
        n = _claim_next[org_id]
    return f"CV-{year % 100:02d}-{n:05d}"


def forget_claim_counter(org_id: str | None = None) -> None:
    """Re-read the counter from the database on next use (after the seed or a test changes it)."""
    if org_id is None:
        _claim_next.clear()
    else:
        _claim_next.pop(org_id, None)


class SqlCallSink:
    """One per organisation (`sink_for`). Holds per-call state while a call is live."""

    def __init__(self, org_id: str) -> None:
        self.org_id = org_id
        self._calls: dict[str, _Live] = {}

    # ------------------------------------------------------------ plumbing

    def _live(self, call_id: str) -> _Live:
        live = self._calls.get(call_id)
        if live is None:
            live = self._calls[call_id] = _Live(call_id, self.org_id)
            live.task = asyncio.get_running_loop().create_task(self._writer(live))
        return live

    def _put(self, call_id: str, op: Op, *, refresh: bool = True) -> None:
        self._live(call_id).queue.put_nowait((op, None, refresh))

    async def flush(self, call_id: str) -> None:
        live = self._calls.get(call_id)
        if live is None:
            return
        done: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        live.queue.put_nowait((None, done, False))
        await done

    async def _writer(self, live: _Live) -> None:
        dirty = False  # a write changed the line since the desk last heard about it
        while True:
            op, done, refresh = await live.queue.get()
            try:
                if op is not None:
                    async with db.sessionmaker()() as session:
                        call = await session.get(Call, live.call_id)
                        if call is not None or getattr(op, "creates", False):
                            await op(session, call)
                            await session.commit()
                            dirty = dirty or refresh
                if dirty and (live.queue.empty() or op is None):
                    dirty = False
                    await self._publish_line(live.call_id)
            except Exception:  # a failed write must never take the call down
                log.exception("sink_write_failed", call_id=live.call_id)
            finally:
                if done is not None and not done.done():
                    done.set_result(None)

    async def _publish_line(self, call_id: str) -> None:
        """`line.updated` for the desk, after the writes it reflects (coalesced while writes are queued)."""
        async with db.sessionmaker()() as session:
            call = await session.get(Call, call_id)
            if call is not None and call.state != "ended":
                line = await views.live_line(session, call, EVENT_LANG, siu=True)
                bus.publish(org_key(self.org_id), "line.updated", line, org_id=self.org_id, call_id=call.id)

    def _elapsed(self, call: Call) -> int:
        """Milliseconds into the call now: the wall clock for a live call, the latest turn for a scripted replay."""
        live = self._calls.get(call.id)
        by_clock = int((clock.now() - call.answered_at).total_seconds() * 1000)
        return max(0, by_clock, live.last_ms if live else 0)

    def _publish_call(self, call_id: str, type_: str, data: Any, *, transient: bool = False) -> None:
        bus.publish(call_key(call_id), type_, data, org_id=self.org_id, call_id=call_id, transient=transient)

    def _event(self, call_id: str, kind: str, label: str, at_ms: int, data: dict[str, Any] | None = None) -> None:
        async def op(session: AsyncSession, call: Call) -> None:
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=call.answered_at + timedelta(milliseconds=at_ms),
                    at_ms=at_ms,
                    kind=kind,
                    label=label,
                    data=data or {},
                )
            )

        self._put(call_id, op, refresh=False)

    # ------------------------------------------------------------ CallSink

    async def call_opened(self, call: CallOpened) -> None:
        live = self._live(call.call_id)
        live.language = call.language

        async def op(session: AsyncSession, row: Call | None) -> None:
            if row is None:
                row = Call(id=call.call_id, org_id=self.org_id, reference=await next_reference(session, self.org_id))
                row.line_number = await next_line_number(session, self.org_id)
                row.answered_at = clock.now()
                session.add(row)
            row.state = "with_line"
            row.mode = call.mode.value
            row.language = call.language
            row.channel = call.channel
            row.caller_phone_e164 = call.caller_phone or row.caller_phone_e164
            row.region = row.region or call.region_hint
            row.scenario = call.scenario or row.scenario
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=row.id,
                    at=row.answered_at,
                    at_ms=0,
                    kind="answered",
                    label="ClaimVoice answered",
                    data={"region": row.region, "language": row.language},
                )
            )
            await session.flush()
            line = await views.live_line(session, row, EVENT_LANG, siu=True)
            bus.publish(org_key(self.org_id), "line.opened", line, org_id=self.org_id, call_id=row.id)

        op.creates = True  # type: ignore[attr-defined]
        live.queue.put_nowait((op, None, False))

    async def consent(self, call_id: str, consent: ConsentRecord) -> None:
        async def op(session: AsyncSession, call: Call) -> None:
            call.consent = {
                "rule": consent.rule,
                "region": consent.region,
                "answer": consent.answer,
                "recording": consent.recording,
                "askedAt": (call.answered_at + timedelta(milliseconds=consent.announced_at_ms)).isoformat(),
                "turnId": consent.turn_id,
            }
            if consent.answer == "refused":
                _add_flag(
                    call, "consent_refused", "The caller declined recording. Notes only.", consent.announced_at_ms
                )
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=call.answered_at + timedelta(milliseconds=consent.announced_at_ms),
                    at_ms=consent.announced_at_ms,
                    kind="consent",
                    label=labels.pick(labels.CONSENT_ANSWERS[consent.answer], EVENT_LANG),
                    data={
                        "rule": consent.rule,
                        "answer": consent.answer,
                        "recording": consent.recording,
                        "region": consent.region,
                        "turnId": consent.turn_id,
                    },
                )
            )

        self._put(call_id, op)

    async def turn(self, call_id: str, turn: TurnRecord) -> None:
        live = self._live(call_id)
        live.turn_ms[turn.turn_id] = turn.at_ms
        live.last_ms = max(live.last_ms, turn.end_ms)
        text_en = getattr(turn, "text_en", None)
        if turn.retained:
            speaker_label = (
                "ClaimVoice"
                if turn.speaker is Speaker.LINE
                else (live.caller_name or "Caller")
                if turn.speaker is Speaker.CALLER
                else (turn.speaker_name or "A person")
            )
            self._publish_call(
                call_id,
                "turn.final",
                w.Turn(
                    id=turn.turn_id,
                    seq=turn.seq,
                    speaker=turn.speaker.value,
                    speaker_label=speaker_label,
                    text=turn.text,
                    text_en=text_en,
                    language=labels.lit(views.lang_of(turn.language)),
                    at_ms=turn.at_ms,
                    end_ms=turn.end_ms,
                    stage=turn.stage,
                    confidence=turn.confidence,
                    interrupted=turn.interrupted,
                    redactions=turn.redactions,
                    flags=[],
                ),
            )

        async def op(session: AsyncSession, call: Call) -> None:
            session.add(
                CallTurn(
                    id=turn.turn_id,
                    org_id=self.org_id,
                    call_id=call_id,
                    seq=turn.seq,
                    speaker=turn.speaker.value,
                    speaker_name=turn.speaker_name,
                    text=turn.text,
                    text_en=text_en,
                    language=turn.language,
                    at_ms=turn.at_ms,
                    end_ms=turn.end_ms,
                    stage=turn.stage,
                    confidence=turn.confidence,
                    interrupted=turn.interrupted,
                    redactions=turn.redactions,
                    retained=turn.retained,
                    flags=["card_number_removed"] if turn.redactions else [],
                )
            )
            call.turn_count = max(call.turn_count, turn.seq)
            if turn.speaker is Speaker.LINE and turn.text.rstrip().endswith("?"):
                call.last_asked = {"text": turn.text, "textEn": text_en}
            if turn.speaker is Speaker.CALLER and turn.language and turn.language != call.language:
                call.language = turn.language

        self._put(call_id, op)

    async def partial(self, call_id: str, speaker: Speaker, text: str) -> None:
        self._publish_call(call_id, "turn.partial", {"speaker": speaker.value, "text": text}, transient=True)

    async def slot(self, call_id: str, slot: SlotRecord) -> None:
        live = self._live(call_id)
        at_ms = live.turn_ms.get(slot.turn_id or "")
        if slot.key == "caller_name" and isinstance(slot.value, str):
            live.caller_name = slot.value

        async def op(session: AsyncSession, call: Call) -> None:
            now = clock.now()
            await session.execute(
                update(CallSlot)
                .where(CallSlot.call_id == call_id, CallSlot.key == slot.key, CallSlot.superseded_at.is_(None))
                .values(superseded_at=now)
            )
            row = CallSlot(
                org_id=self.org_id,
                call_id=call_id,
                key=slot.key,
                value=slot.value,
                display=slot.display,
                confidence=slot.confidence,
                source=slot.source,
                turn_id=slot.turn_id,
                span_start=slot.span[0] if slot.span else None,
                span_end=slot.span[1] if slot.span else None,
                at_ms=at_ms,
                confirmed=slot.confirmed,
                corrects=slot.corrects,
                created_at=now,
            )
            session.add(row)
            _apply_slot(call, slot)
            await session.flush()
            parts = await views.slot_rows(session, call_id)
            required = await views.script_required(session, self.org_id, call.loss_type)
            progress, _ = views.progress_of(parts.current, required)
            out = views.slot_out(row, EVENT_LANG, slot.key in required, parts.history.get(slot.key, ()))
            self._publish_call(call_id, "slot.updated", {"slot": out, "progress": progress})

        self._put(call_id, op)

    async def stage(self, call_id: str, change: StageChange) -> None:
        resume = change.previous if change.stage == "handoff" else None
        self._publish_call(call_id, "stage.changed", views.stage_info(change.stage, EVENT_LANG, resume))

        async def op(session: AsyncSession, call: Call) -> None:
            call.stage = change.stage
            if change.stage == "handoff":
                call.resume_stage = change.previous
                if call.state != "with_person":
                    call.state = "waiting_for_person"
            elif change.stage != "ended":
                call.resume_stage = None
                if change.previous == "handoff":
                    call.state = "with_line"
                elif change.stage in ("read_back", "wrap_up"):
                    call.state = "wrapping_up"
                elif call.state in ("ringing", "waiting_for_person"):
                    call.state = "with_line"
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=call.answered_at + timedelta(milliseconds=change.at_ms),
                    at_ms=change.at_ms,
                    kind="stage",
                    label=views.stage_info(change.stage, EVENT_LANG).label,
                    data={"stage": change.stage, "previous": change.previous, "event": change.event},
                )
            )
            if change.event == "read_back_confirmed":
                session.add(
                    CallEvent(
                        org_id=self.org_id,
                        call_id=call_id,
                        at=call.answered_at + timedelta(milliseconds=change.at_ms),
                        at_ms=change.at_ms,
                        kind="read_back",
                        label="Caller confirmed the read-back",
                        data={"confirmed": True},
                    )
                )

        self._put(call_id, op)

    async def flag(self, call_id: str, flag: CallFlag) -> None:
        kind = flag.kind.value
        self._publish_call(
            call_id,
            "flag.raised",
            views.flag_out(
                {"kind": kind, "detail": flag.detail, "at": clock.now().isoformat(), "turnId": flag.turn_id}, EVENT_LANG
            ),
        )

        async def op(session: AsyncSession, call: Call) -> None:
            _add_flag(call, kind, flag.detail, flag.at_ms, flag.turn_id)
            if kind in ("urgent_safety", "distress"):
                call.mood = {"key": "upset" if kind == "urgent_safety" else "shaken", "detail": None}
            if flag.turn_id:
                turn = await session.get(CallTurn, flag.turn_id)
                if turn is not None and kind not in (turn.flags or []):
                    turn.flags = [*(turn.flags or []), kind]
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=call.answered_at + timedelta(milliseconds=flag.at_ms),
                    at_ms=flag.at_ms,
                    kind="flag",
                    label=labels.pick(labels.FLAGS.get(kind), EVENT_LANG, kind),
                    data={"kind": kind, "detail": flag.detail, "turnId": flag.turn_id},
                )
            )

        self._put(call_id, op)

    async def tool_called(self, call_id: str, record: ToolCallRecord) -> None:
        if record.timed_out:
            from claimvoice.platform.metrics import TOOL_TIMEOUTS

            TOOL_TIMEOUTS.labels(record.tool).inc()
        ok_label, fail_label = TOOL_LABELS.get(record.tool, ("Looked up in {s} s", "A lookup didn't answer in time"))
        label = ok_label.format(s=f"{record.elapsed_ms / 1000:.1f}") if record.ok else fail_label
        self._publish_call(
            call_id,
            "tool.called",
            {"tool": record.tool, "label": label, "elapsedMs": round(record.elapsed_ms), "ok": record.ok},
        )
        self._event(
            call_id,
            "tool",
            label,
            record.at_ms,
            {
                "tool": record.tool,
                "ok": record.ok,
                "timedOut": record.timed_out,
                "elapsedMs": round(record.elapsed_ms, 1),
                "summary": record.summary,
            },
        )

    async def latency(self, call_id: str, sample: TurnLatency) -> None:
        from claimvoice.platform.metrics import TURN_SECONDS

        self._live(call_id).latencies.append(sample.total_ms)
        TURN_SECONDS.observe(sample.total_ms / 1000)

    async def caller_identified(self, call_id: str, policy_id: str, holder_id: str, region: str) -> None:
        async def op(session: AsyncSession, call: Call) -> None:
            holder = await session.get(Policyholder, holder_id)
            call.policy_id, call.holder_id, call.region, call.caller_verified = policy_id, holder_id, region, True
            if holder is not None and not call.caller_name:
                call.caller_name = holder.full_name
                self._live(call_id).caller_name = holder.full_name
            if holder is not None and not call.place:
                call.place = holder.city
            await _match_surge(session, call)
            at_ms = self._elapsed(call)
            now = call.answered_at + timedelta(milliseconds=at_ms)
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=now,
                    at_ms=at_ms,
                    kind="identity",
                    label="Caller and policy confirmed",
                    data={"verified": True, "region": region},
                )
            )

        self._put(call_id, op)

    async def photo_link_sent(self, call_id: str, to_masked: str, link_token: str) -> None:
        self._publish_call(call_id, "notice", {"kind": "photo_link_sent", "text": f"Photo link texted to {to_masked}"})

        async def op(session: AsyncSession, call: Call) -> None:
            at_ms = self._elapsed(call)
            now = call.answered_at + timedelta(milliseconds=at_ms)
            session.add(
                PhotoLink(
                    org_id=self.org_id,
                    call_id=call_id,
                    token_hash=token_digest(link_token),
                    expires_at=now + timedelta(hours=PHOTO_LINK_HOURS),  # business time, like the claim it serves
                )
            )
            body = _sms_body(call_id, link_token)
            session.add(
                SmsMessage(
                    org_id=self.org_id,
                    call_id=call_id,
                    to_e164=call.caller_phone_e164 or "",
                    body=body,
                    status="sent",
                    sent_at=now,
                )
            )
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=now,
                    at_ms=at_ms,
                    kind="photo_link",
                    label=f"Photo link texted to {to_masked}",
                    data={"toMasked": to_masked},
                )
            )

        self._put(call_id, op)

    async def handoff_requested(self, call_id: str, reason: HandoffReason, detail: str) -> HandoffTicket:
        from claimvoice.platform.db import new_id

        handoff_id = new_id()
        code = reason.value
        priority = labels.HANDOFF_PRIORITY.get(code, "normal")

        async def op(session: AsyncSession, call: Call) -> None:
            at_ms = self._elapsed(call)
            now = call.answered_at + timedelta(milliseconds=at_ms)
            summary = await handoff_summary(session, call, detail)
            session.add(
                Handoff(
                    id=handoff_id,
                    org_id=self.org_id,
                    call_id=call_id,
                    reason=code,
                    detail=detail,
                    priority=priority,
                    state="waiting",
                    requested_at=now,
                    summary=summary,
                    actions=_actions_for(code, call.language),
                )
            )
            call.state = "waiting_for_person"
            session.add(
                CallEvent(
                    org_id=self.org_id,
                    call_id=call_id,
                    at=now,
                    at_ms=at_ms,
                    kind="handoff",
                    label=f"Hand-off asked: {labels.pick(labels.HANDOFF_REASONS[code], EVENT_LANG)}",
                    data={"reason": code, "priority": priority, "atMs": at_ms, "state": "requested"},
                )
            )
            await session.flush()
            info = await views.handoff_for(session, call, EVENT_LANG)
            if info is not None:
                bus.publish(org_key(self.org_id), "handoff.requested", info, org_id=self.org_id, call_id=call_id)
                self._publish_call(call_id, "handoff.updated", info)

        self._put(call_id, op)
        waiting = await _waiting_count(self.org_id)
        return HandoffTicket(handoff_id, waiting + 1, 60)

    async def reserve_claim_number(self, call_id: str) -> str:
        number = await allocate_claim_number(self.org_id, clock.today().year)

        async def op(session: AsyncSession, call: Call) -> None:
            call.claim_number = number

        self._put(call_id, op, refresh=False)
        return number

    async def call_closed(self, call_id: str, closing: CallClosing) -> None:
        from claimvoice.calls.closing import close_call

        live = self._live(call_id)
        await self.flush(call_id)
        latencies = sorted(live.latencies)
        p95 = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))] if latencies else None

        async def run() -> None:
            try:
                await close_call(self.org_id, call_id, closing, latency_p95_ms=p95)
            except Exception:
                log.exception("call_close_failed", call_id=call_id)
            finally:
                if live.task is not None:
                    live.task.cancel()
                self._calls.pop(call_id, None)

        live.closing = asyncio.get_running_loop().create_task(run())

    # ------------------------------------------------------------ helpers for tests and shutdown

    async def wait_closed(self, call_id: str) -> None:
        live = self._calls.get(call_id)
        if live is not None and live.closing is not None:
            await live.closing

    async def aclose(self) -> None:
        for live in list(self._calls.values()):
            if live.task is not None:
                live.task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await live.task
        self._calls.clear()


def _add_flag(call: Call, kind: str, detail: str, at_ms: int, turn_id: str | None = None) -> None:
    if any(f.get("kind") == kind and f.get("detail") == detail for f in call.flags or []):
        return
    at = call.answered_at + timedelta(milliseconds=at_ms)
    call.flags = [*(call.flags or []), {"kind": kind, "detail": detail, "at": at.isoformat(), "turnId": turn_id}]


def _apply_slot(call: Call, slot: SlotRecord) -> None:
    if slot.key == "loss_type" and isinstance(slot.value, str):
        call.loss_type = slot.value
    elif slot.key == "loss_place" and slot.display:
        call.place = slot.display
    elif slot.key == "caller_name" and isinstance(slot.value, str):
        call.caller_name = slot.value
    pill = HEARD_PILLS.get(slot.key)
    if pill is None:
        return
    text, tone = pill
    if slot.value is False or slot.value in (None, ""):
        return
    if slot.key == "vehicle_drivable" and slot.value is not False:
        return
    heard = [h for h in (call.heard or []) if h.get("key") != slot.key]
    call.heard = [{"key": slot.key, "text": text or slot.display, "tone": tone}, *heard][:4]


async def _match_surge(session: AsyncSession, call: Call) -> None:
    if call.surge_id or not call.region:
        return
    surge = (
        await session.execute(
            select(Surge).where(Surge.org_id == call.org_id, Surge.region == call.region, Surge.ended_at.is_(None))
        )
    ).scalar_one_or_none()
    if surge is not None and (call.loss_type in (None, surge.loss_type)):
        call.surge_id = surge.id
        _add_flag(call, "surge", f"In the {surge.title} area", 0)


async def _waiting_count(org_id: str) -> int:
    from sqlalchemy import func

    async with db.sessionmaker()() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Handoff)
                    .where(Handoff.org_id == org_id, Handoff.state == "waiting")
                )
            ).scalar_one()
        )


def _actions_for(reason: str, language: str) -> list[str]:
    if reason == "urgent_safety":
        return ["Told the caller to get to safety and call 911", "Stayed on the line"]
    if reason == "caller_asked":
        return ["Told the caller a person is on the way"]
    return []


async def handoff_summary(session: AsyncSession, call: Call, detail: str) -> str:
    """Two lines so nobody asks the caller twice."""
    parts = await views.slot_rows(session, call.id)
    who = call.caller_name or "Unverified caller"
    policy = await session.get(Policy, call.policy_id) if call.policy_id else None
    first = f"{who}" + (f", policy {policy.policy_number}" if policy else ", policy not found yet")
    if call.place:
        first += f", {call.place}"
    loss = labels.loss_type(call.loss_type, "en")
    said = parts.current.get("loss_description")
    brief = in_brief(said.display, call.language or "en") if said else ""
    values = {k: row.value for k, row in parts.current.items()}
    known = facts(values, "en")[1 if values.get("loss_type") else 0 :]  # the loss itself is already named
    second = f"{loss}. {brief}." if loss and brief else (detail or (loss or "Loss not described yet"))
    if known:
        second += " " + known[0][0].upper() + known[0][1:] + "".join(f", {k}" for k in known[1:]) + "."
    return f"{first}.\n{second}"


def _sms_body(call_id: str, token: str) -> str:
    try:
        from claimvoice.tools.sms import get_sms_sender

        sender = get_sms_sender()
        for message in reversed(getattr(sender, "outbox", [])):
            if message.call_id == call_id and token in message.body:
                return str(message.body)
    except Exception:  # the outbox is a convenience; the link below is what matters
        log.debug("sms_outbox_unavailable")
    return f"Larkspur Mutual: send photos of the damage here: {get_settings().web_origin}/p/{token}"


async def next_reference(session: AsyncSession, org_id: str) -> str:
    """CALL-260108-042: the day (org-local) and that day's running number."""

    org = await session.get(Organization, org_id)
    tz = org.timezone if org else "America/Edmonton"
    day = clock.today(tz)
    prefix = f"CALL-{day:%y%m%d}-"
    # The highest number used today, not a count: public demo calls are deleted after they end, so a count would
    # hand out a number that is still taken.
    used = (
        (await session.execute(select(Call.reference).where(Call.org_id == org_id, Call.reference.like(prefix + "%"))))
        .scalars()
        .all()
    )
    n = max((int(r[len(prefix) :]) for r in used if r[len(prefix) :].isdigit()), default=0)
    return f"{prefix}{n + 1:03d}"


async def next_line_number(session: AsyncSession, org_id: str) -> int:
    used = set(
        (
            await session.execute(
                select(Call.line_number).where(
                    Call.org_id == org_id, Call.state != "ended", Call.line_number.is_not(None)
                )
            )
        )
        .scalars()
        .all()
    )
    n = 1
    while n in used:
        n += 1
    return n


_sinks: dict[str, SqlCallSink] = {}


def sink_for(org_id: str) -> SqlCallSink:
    sink = _sinks.get(org_id)
    if sink is None:
        sink = _sinks[org_id] = SqlCallSink(org_id)
    return sink


async def close_all() -> None:
    for sink in list(_sinks.values()):
        await sink.aclose()
    _sinks.clear()
