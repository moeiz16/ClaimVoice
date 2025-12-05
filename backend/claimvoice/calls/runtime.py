"""Where the platform meets the voice runtime: getting the `LineRuntime` (`voice.lines.get_line_manager()`), adopting
the seeded live demo lines at start-up, and the supervisor actions (listen, whisper, take over, say, hand back, hang
up, hand off) that the HTTP handlers call after permission checks.

Each action is recorded by the platform (timeline, audit, SSE) and then passed to the runtime through `LineControl`.
When the runtime does not hold the call (the API restarted while a seeded line was on the desk, or the runtime is not
installed), the platform still records the action so the desk stays truthful, and writes a person's typed words as a
person turn itself."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import func, select

from claimvoice import clock, contracts
from claimvoice.calls.models import Call, CallEvent, CallTurn
from claimvoice.calls.sink import close_all, sink_for
from claimvoice.platform import db
from claimvoice.platform.models import Organization
from claimvoice.policies.directory import get_directory
from claimvoice.settings.playbook import get_playbook

log = structlog.get_logger("claimvoice.runtime")
SAMPLE_SCENARIOS = ("calgary-windstorm", "denver-rear-end", "montreal-basement")

_override: contracts.LineRuntime | None = None
_disabled = False


def line_runtime() -> contracts.LineRuntime | None:
    if _override is not None:
        return _override
    if _disabled:
        return None
    try:
        from claimvoice.voice.lines import get_line_manager
    except ImportError:
        return None
    return get_line_manager()


def use_runtime(runtime: contracts.LineRuntime | None, *, disabled: bool = False) -> None:
    """Tests: plug in a fake runtime, or run with none."""
    global _override, _disabled
    _override, _disabled = runtime, disabled


def holds(call_id: str) -> bool:
    rt = line_runtime()
    try:
        return rt is not None and rt.is_live(call_id)
    except Exception:
        return False


def at_ms(call: Call) -> int:
    return max(0, int((clock.now() - call.answered_at).total_seconds() * 1000))


async def adopt_sample_lines() -> int:
    """Hand the seeded live lines to the runtime so the scripted callers carry on. Returns how many were adopted."""
    rt = line_runtime()
    if rt is None or not hasattr(rt, "adopt_sample_line"):
        return 0
    adopted = 0
    async with db.sessionmaker()() as session:
        rows = (
            (
                await session.execute(
                    select(Call)
                    .join(Organization, Organization.id == Call.org_id)
                    .where(Organization.is_sample.is_(True), Call.state != "ended", Call.scenario.in_(SAMPLE_SCENARIOS))
                )
            )
            .scalars()
            .all()
        )
        for call in rows:
            caller_turns = (
                await session.execute(
                    select(func.count())
                    .select_from(CallTurn)
                    .where(CallTurn.call_id == call.id, CallTurn.speaker == "caller")
                )
            ).scalar_one()
            try:
                await rt.adopt_sample_line(
                    call.id,
                    org_id=call.org_id,
                    scenario=call.scenario or "",
                    resume_after_turn=int(caller_turns),
                    sink=sink_for(call.org_id),
                    policies=get_directory(),
                    playbook=get_playbook(),
                )
                adopted += 1
            except Exception:
                log.exception("adopt_failed", call_id=call.id)
    return adopted


async def shutdown() -> None:
    rt = line_runtime()
    stop = getattr(rt, "shutdown", None) if rt is not None else None
    if stop is not None:
        try:
            await stop()
        except Exception:
            log.exception("runtime_shutdown_failed")
    await close_all()


async def platform_person_turn(call_id: str, text: str, *, user_id: str, name: str) -> str:
    """A person's typed words on a call the runtime does not hold: stored as a person turn."""
    from claimvoice.calls import views
    from claimvoice.platform.db import new_id
    from claimvoice.platform.events import bus, call_key

    turn_id = new_id()
    async with db.sessionmaker()() as session:
        call = await session.get(Call, call_id)
        assert call is not None
        seq = int(
            (await session.execute(select(func.max(CallTurn.seq)).where(CallTurn.call_id == call_id))).scalar_one() or 0
        )
        start = at_ms(call)
        row = CallTurn(
            id=turn_id,
            org_id=call.org_id,
            call_id=call_id,
            seq=seq + 1,
            speaker="person",
            speaker_name=name,
            text=text,
            language=call.language,
            at_ms=start,
            end_ms=start + max(800, 60 * len(text)),
            stage=call.stage,
            retained=(call.consent or {}).get("answer") != "refused",
        )
        session.add(row)
        call.turn_count = seq + 1
        await session.commit()
        bus.publish(
            call_key(call_id), "turn.final", views.turn_out(row, call, "en"), org_id=call.org_id, call_id=call_id
        )
    return turn_id


async def record_event(
    call: Call, kind: str, label: str, *, actor_id: str | None, actor: str | None, data: dict[str, Any] | None = None
) -> CallEvent:
    async with db.sessionmaker()() as session:
        ev = CallEvent(
            org_id=call.org_id,
            call_id=call.id,
            at=clock.now(),
            at_ms=at_ms(call),
            kind=kind,
            label=label,
            actor_user_id=actor_id,
            actor_label=actor,
            data=data or {},
        )
        session.add(ev)
        await session.commit()
        return ev
