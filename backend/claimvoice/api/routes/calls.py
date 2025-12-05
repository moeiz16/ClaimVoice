"""§1.6 calls: live lines, starting a browser call, call detail, transcript, live claim file, timeline, texts,
recordings, and the supervisor's line controls (listen, whisper, take over, say, hand back, hang up, hand off).
Part 4 signalling (WebRTC offer, trickle ICE, WebSocket fallback) uses the caller token."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from litestar import Request, Response, Router, WebSocket, delete, get, patch, post, websocket
from litestar.params import Parameter
from litestar.response import Stream
from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock, reference
from claimvoice.api import labels
from claimvoice.api.context import Ctx, not_found, paged
from claimvoice.api.routes.stream import sse_response
from claimvoice.calls import audio, runtime, views
from claimvoice.calls.models import Call, CallTurn, Handoff, SmsMessage, Whisper
from claimvoice.calls.sink import next_line_number, next_reference, sink_for
from claimvoice.config import get_settings
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.events import bus, call_key, org_key
from claimvoice.platform.models import Membership, Organization, User
from claimvoice.platform.security import new_token, token_digest, tokens_match
from claimvoice.policies.directory import get_directory
from claimvoice.schemas import calls as w
from claimvoice.schemas.base import Page
from claimvoice.settings import service as settings_service
from claimvoice.settings.playbook import get_playbook

STAFF_MAX_SECONDS = 30 * 60
DEMO_MAX_SECONDS = 6 * 60
MAX_PUBLIC_DEMO_LINES = 4


def _not_live() -> ProblemError:
    return ProblemError(409, "call_not_live", "The call has ended", "This call is no longer on the line.")


async def _call(ctx: Ctx, call_id: str) -> Call:
    return await ctx.get(Call, call_id)


async def _live_call(ctx: Ctx, call_id: str) -> Call:
    call = await _call(ctx, call_id)
    if call.state == "ended":
        raise _not_live()
    return call


async def _publish_line(db: AsyncSession, call: Call) -> None:
    await db.refresh(call)
    if call.state != "ended":
        line = await views.live_line(db, call, "en", siu=True)
        bus.publish(org_key(call.org_id), "line.updated", line, org_id=call.org_id, call_id=call.id)


def _publish_listeners(call: Call) -> None:
    bus.publish(
        call_key(call.id),
        "listener.changed",
        {"listeners": list(call.listeners)},
        org_id=call.org_id,
        call_id=call.id,
    )


def _who(ctx: Ctx) -> str:
    return ctx.user.full_name


def _line_name(call: Call) -> str:
    who = call.caller_name or "unverified caller"
    return f"Line {call.line_number} ({who})" if call.line_number else f"{call.reference} ({who})"


# ---------------------------------------------------------------- reading


@get("/calls/live")
async def live_calls(ctx: Ctx, region: str | None = None) -> list[w.LiveLine]:
    ctx.require("lines:read")
    stmt = select(Call).where(Call.org_id == ctx.org_id, Call.state != "ended")
    if region:
        stmt = stmt.where(Call.region == region)
    rows = (await ctx.db.execute(stmt.order_by(Call.line_number, Call.answered_at))).scalars().all()
    return [await views.live_line(ctx.db, c, ctx.lang, siu=ctx.siu) for c in rows]


def _parse_time(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProblemError(400, "bad_request", "Bad request", f"{field} must be an ISO date or time.") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@get("/calls")
async def list_calls(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    status: str = "all",
    from_: str | None = Parameter(query="from", default=None),
    to: str | None = None,
    language: str | None = None,
    loss_type: str | None = Parameter(query="lossType", default=None),
    flag: str | None = None,
    outcome: str | None = None,
    q: str | None = None,
) -> Page[w.CallSummary]:
    ctx.require("calls:read")
    stmt: Select[Any] = select(Call).where(Call.org_id == ctx.org_id)
    if status == "live":
        stmt = stmt.where(Call.state != "ended")
    elif status == "ended":
        stmt = stmt.where(Call.state == "ended")
    start = _parse_time(from_, "from")
    end = _parse_time(to, "to")
    if start:
        stmt = stmt.where(Call.answered_at >= start)
    if end:
        stmt = stmt.where(Call.answered_at <= end)
    if language:
        stmt = stmt.where(Call.language == language)
    if loss_type:
        stmt = stmt.where(Call.loss_type == loss_type)
    if outcome:
        stmt = stmt.where(Call.outcome == outcome)
    if flag and (flag != "siu_signal" or ctx.siu):
        stmt = stmt.where(cast(Call.flags, String).like(f'%"kind": "{flag}"%'))
    if q:
        from claimvoice.claims.models import Claim

        like = f"%{q.strip()}%"
        claim_calls = select(Claim.call_id).where(Claim.org_id == ctx.org_id, Claim.claim_number.ilike(like))
        stmt = stmt.where(or_(Call.reference.ilike(like), Call.caller_name.ilike(like), Call.id.in_(claim_calls)))
    stmt = stmt.order_by(Call.answered_at.desc())

    async def mapper(rows: Any) -> list[w.CallSummary]:
        ids = [c.id for c in rows]
        claims = await views.claims_for_calls(ctx.db, ids)
        qa = await views.qa_scores_for(ctx.db, ids)
        return [views.summary_out(c, ctx.lang, siu=ctx.siu, claim=claims.get(c.id), qa=qa.get(c.id)) for c in rows]

    return await paged(ctx.db, stmt, page, page_size, mapper)


@get("/calls/{call_id:str}")
async def get_call(ctx: Ctx, call_id: str) -> w.CallDetail:
    ctx.require("calls:read")
    return await views.detail(ctx.db, await _call(ctx, call_id), ctx.lang, siu=ctx.siu)


@get("/calls/{call_id:str}/transcript")
async def get_transcript(ctx: Ctx, call_id: str) -> w.Transcript:
    ctx.require("calls:read")
    return await views.transcript(ctx.db, await _call(ctx, call_id), ctx.lang)


@get("/calls/{call_id:str}/claim-file")
async def get_claim_file(ctx: Ctx, call_id: str) -> w.ClaimFile:
    ctx.require("calls:read")
    call = await _call(ctx, call_id)
    claim = (await views.claims_for_calls(ctx.db, [call.id])).get(call.id)
    return await views.claim_file(ctx.db, call, ctx.lang, claim_id=claim[0] if claim else None)


@get("/calls/{call_id:str}/timeline")
async def get_timeline(ctx: Ctx, call_id: str) -> list[w.CallEvent]:
    ctx.require("calls:read")
    return await views.timeline(ctx.db, await _call(ctx, call_id))


@get("/calls/{call_id:str}/messages")
async def get_messages(ctx: Ctx, call_id: str) -> list[w.SmsMessage]:
    ctx.require("calls:read")
    call = await _call(ctx, call_id)
    rows = (
        (await ctx.db.execute(select(SmsMessage).where(SmsMessage.call_id == call.id).order_by(SmsMessage.sent_at)))
        .scalars()
        .all()
    )
    show_body = ctx.org.is_sample  # the sample org shows the photo link so the demo can open it
    return [
        w.SmsMessage(
            id=m.id,
            to_masked=labels.mask_phone(m.to_e164) or "•••",
            body=m.body if show_body else m.body.split("http")[0].strip() + " [link]",
            sent_at=m.sent_at,
            status=labels.lit(m.status),
        )
        for m in rows
    ]


@get("/calls/{call_id:str}/stream")
async def call_stream(ctx: Ctx, call_id: str) -> Stream:
    ctx.require("calls:read")
    call = await _call(ctx, call_id)
    return await sse_response(ctx, call_key(call.id))


async def recording_for(ctx: Ctx, call: Call) -> Any:
    years = int(settings_service.section(ctx.org, "retention")["recordingsYears"])
    url = f"/api/v1/calls/{call.id}/recording/audio"
    return await views.recording(
        ctx.db, call, ctx.lang, audio_url=url, retained_until=views.retained_until(call, years)
    )


@get("/calls/{call_id:str}/recording")
async def call_recording(ctx: Ctx, call_id: str) -> Any:
    ctx.require("recordings:read")
    return await recording_for(ctx, await _call(ctx, call_id))


async def audio_for(ctx: Ctx, call: Call, target: tuple[str, str, str]) -> Response[bytes]:
    rec = await recording_for(ctx, call)
    if not rec.available:
        raise not_found()
    path = audio.recording_file(call)
    if path is None:
        turns = (
            (await ctx.db.execute(select(CallTurn).where(CallTurn.call_id == call.id, CallTurn.retained.is_(True))))
            .scalars()
            .all()
        )
        path = await asyncio.to_thread(audio.render_placeholder, call, turns, rec.duration_seconds or 1.0)
    range_header = ctx.request.headers.get("range")
    if not range_header or range_header.strip() in ("bytes=0-", "bytes=0-1"):
        kind, ident, label = target
        await ctx.audit(
            "recording.played",
            f"{ctx.user.full_name} played the recording of {label}.",
            target_type=kind,
            target_id=ident,
            target_label=label,
        )
    return audio.ranged(path, range_header)


@get("/calls/{call_id:str}/recording/audio")
async def call_audio(ctx: Ctx, call_id: str) -> Response[bytes]:
    ctx.require("recordings:read")
    call = await _call(ctx, call_id)
    return await audio_for(ctx, call, ("call", call.id, call.reference))


# ---------------------------------------------------------------- starting a call


def _ice_servers() -> list[w.IceServer]:
    urls = [u.strip() for u in get_settings().voice_ice_servers.split(",") if u.strip()]
    return [w.IceServer(urls=[u]) for u in urls]


def _connect(call: Call, token: str, max_seconds: int) -> w.ConnectInfo:
    port = get_settings().api_port
    return w.ConnectInfo(
        call_id=call.id,
        caller_token=token,
        offer_url=f"/api/v1/calls/{call.id}/webrtc/offer",
        ice_url=f"/api/v1/calls/{call.id}/webrtc/ice",
        websocket_url=f"ws://localhost:{port}/api/v1/calls/{call.id}/ws?token={token}",
        data_channel_label="claimvoice",
        ice_servers=_ice_servers(),
        max_seconds=max_seconds,
    )


async def _start(
    db: AsyncSession, org: Organization, data: w.StartCallIn, *, user_id: str | None, public: bool, lang: str
) -> w.StartCallOut:
    if data.scenario and data.scenario not in reference.DEMO_SCENARIOS:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "scenario", "message": "Choose one of the sample callers."}],
        )
    if data.region and data.region not in reference.REGIONS:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "region", "message": "Choose a state or province from the list."}],
        )
    if data.caller_phone and not (data.caller_phone.startswith("+") and 8 <= len(data.caller_phone) <= 16):
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "callerPhone", "message": "Use an international number like +14035550142."}],
        )
    region = data.region or (org.regions[0] if org.regions else "CA-AB")
    language = data.language if data.language in ("en", "fr") else ("fr" if region == "CA-QC" else "en")
    token = new_token()
    max_seconds = DEMO_MAX_SECONDS if public else STAFF_MAX_SECONDS
    call = Call(
        org_id=org.id,
        reference=await next_reference(db, org.id),
        line_number=await next_line_number(db, org.id),
        mode=data.mode,
        channel="demo_line" if public else "browser",
        language=language,
        state="ringing",
        stage="greeting",
        answered_at=clock.now(),
        caller_phone_e164=data.caller_phone,
        region=region,
        scenario=data.scenario,
        is_sample=org.is_sample,
        is_public_demo=public,
        consent={
            "rule": reference.REGIONS.get(region, {}).get("consent", "all_party"),
            "region": region,
            "answer": "pending",
            "recording": False,
        },
        caller_token_hash=token_digest(token),
        started_by=user_id,
    )
    db.add(call)
    await db.commit()
    rt = runtime.line_runtime()
    if rt is not None:
        try:
            await rt.prepare(
                call.id,
                org_id=org.id,
                mode=data.mode,
                language=data.language,
                region=region,
                scenario=data.scenario,
                caller_phone=data.caller_phone,
                sink=sink_for(org.id),
                policies=get_directory(),
                playbook=get_playbook(),
                max_seconds=max_seconds,
            )
        except Exception as exc:
            call.state, call.ended_at, call.outcome, call.line_number = "ended", clock.now(), "no_claim", None
            await db.commit()
            raise ProblemError(
                503,
                "unavailable",
                "The line isn't available",
                "Please try again in a moment.",
                headers={"Retry-After": "10"},
            ) from exc
    line = await views.live_line(db, call, "en", siu=True)
    bus.publish(org_key(org.id), "line.opened", line, org_id=org.id, call_id=call.id)
    return w.StartCallOut(
        call=await views.detail(db, call, lang, siu=False), connect=_connect(call, token, max_seconds)
    )


@post("/calls", status_code=201)
async def start_call(ctx: Ctx, data: w.StartCallIn) -> w.StartCallOut:
    ctx.require("calls:start")
    return await _start(ctx.db, ctx.org, data, user_id=ctx.user.id, public=False, lang=ctx.lang)


@post("/demo/calls", status_code=201)
async def start_demo_call(
    request: Request[Any, Any, Any], db_session: AsyncSession, data: w.StartCallIn
) -> w.StartCallOut:
    from claimvoice.api.context import client_ip, request_language
    from claimvoice.seed.plan import ORG

    org = (
        await db_session.execute(
            select(Organization).where(Organization.slug == ORG["slug"], Organization.is_sample.is_(True))
        )
    ).scalar_one_or_none()
    if org is None:
        raise ProblemError(404, "not_found", "Not found", "The demo line isn't set up.")
    limiter = request.app.state.limiter
    allowed, retry = limiter.hit("public_call", client_ip(request) or "unknown")
    if not allowed:
        raise ProblemError(
            429,
            "rate_limited",
            "Too many calls",
            "Please wait a few minutes before calling again.",
            headers={"Retry-After": str(retry)},
        )
    busy = (
        await db_session.execute(
            select(func.count())
            .select_from(Call)
            .where(Call.org_id == org.id, Call.is_public_demo.is_(True), Call.state != "ended")
        )
    ).scalar_one()
    if busy >= MAX_PUBLIC_DEMO_LINES:
        raise ProblemError(
            503, "line_busy", "All demo lines are busy", "Please try again in a minute.", headers={"Retry-After": "60"}
        )
    return await _start(db_session, org, data, user_id=None, public=True, lang=request_language(request))


# ---------------------------------------------------------------- caller leg (bearer caller token)


async def _caller_call(
    request: Request[Any, Any, Any] | WebSocket[Any, Any, Any], db: AsyncSession, call_id: str, token: str | None = None
) -> Call:
    if token is None:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    call = await db.get(Call, call_id)
    if (
        call is None
        or not token
        or not call.caller_token_hash
        or not tokens_match(call.caller_token_hash, token_digest(token))
    ):
        raise ProblemError(401, "invalid_call_token", "Not allowed", "This call link is not valid.")
    if call.state == "ended":
        raise _not_live()
    return call


def _runtime_or_503() -> Any:
    rt = runtime.line_runtime()
    if rt is None:
        raise ProblemError(
            503,
            "unavailable",
            "The line isn't available",
            "Please try again in a moment.",
            headers={"Retry-After": "10"},
        )
    return rt


@post("/calls/{call_id:str}/webrtc/offer", status_code=200)
async def webrtc_offer(
    request: Request[Any, Any, Any], db_session: AsyncSession, call_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    call = await _caller_call(request, db_session, call_id)
    if not isinstance(data.get("sdp"), str) or data.get("type") != "offer":
        raise ProblemError(
            422, "validation_error", "Validation failed", errors=[{"field": "sdp", "message": "Send an SDP offer."}]
        )
    rt = _runtime_or_503()
    answer = await rt.answer_offer(call.id, data["sdp"], "offer", data.get("pcId"), bool(data.get("restartPc")))
    return dict(answer)


@patch("/calls/{call_id:str}/webrtc/ice", status_code=204)
async def webrtc_ice(
    request: Request[Any, Any, Any], db_session: AsyncSession, call_id: str, data: dict[str, Any]
) -> None:
    call = await _caller_call(request, db_session, call_id)
    candidates = data.get("candidates")
    if not isinstance(data.get("pcId"), str) or not isinstance(candidates, list):
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "candidates", "message": "Send pcId and a list of candidates."}],
        )
    rt = _runtime_or_503()
    await rt.add_ice(call.id, data["pcId"], candidates)


_ws_holders: set[str] = set()


@websocket("/calls/{call_id:str}/ws")
async def call_ws(socket: WebSocket[Any, Any, Any], db_session: AsyncSession, call_id: str) -> None:
    await socket.accept()
    token = socket.query_params.get("token")
    try:
        call = await _caller_call(socket, db_session, call_id, token or "")
    except ProblemError as exc:
        await socket.close(code=4401 if exc.status == 401 else 4404)
        return
    if call.id in _ws_holders:
        await socket.close(code=4409)
        return
    rt = runtime.line_runtime()
    if rt is None:
        await socket.close(code=4404)
        return
    _ws_holders.add(call.id)
    try:
        await rt.run_websocket(call.id, socket)
    finally:
        _ws_holders.discard(call.id)


# ---------------------------------------------------------------- line controls


def _listeners_without(call: Call, user_id: str) -> list[dict[str, Any]]:
    return [x for x in call.listeners or [] if x.get("userId") != user_id]


async def _event(call: Call, kind: str, label: str, ctx: Ctx, data: dict[str, Any] | None = None) -> None:
    await runtime.record_event(call, kind, label, actor_id=ctx.user.id, actor=_who(ctx), data=data)


@post("/calls/{call_id:str}/listen", status_code=200)
async def listen(ctx: Ctx, call_id: str) -> w.ListenOut:
    ctx.require("calls:listen")
    call = await _live_call(ctx, call_id)
    already = any(x.get("userId") == ctx.user.id for x in call.listeners or [])
    if not already:
        call.listeners = [
            *_listeners_without(call, ctx.user.id),
            {"userId": ctx.user.id, "name": _who(ctx), "mode": "listening"},
        ]
        await ctx.db.commit()
        await _event(call, "listen", f"{_who(ctx)} started listening", ctx)
        await ctx.audit(
            "call.listen",
            f"{_who(ctx)} listened to {_line_name(call)}.",
            target_type="call",
            target_id=call.id,
            target_label=_line_name(call),
        )
        _publish_listeners(call)
        await _publish_line(ctx.db, call)
    if runtime.holds(call.id):
        nudge = getattr(runtime.line_runtime(), "nudge", None)
        if nudge is not None:
            await nudge(call.id)
    return w.ListenOut(mode="transcript", connect=None)


@delete("/calls/{call_id:str}/listen", status_code=204)
async def stop_listening(ctx: Ctx, call_id: str) -> None:
    ctx.require("calls:listen")
    call = await _call(ctx, call_id)
    if any(x.get("userId") == ctx.user.id and x.get("mode") == "listening" for x in call.listeners or []):
        call.listeners = _listeners_without(call, ctx.user.id)
        await ctx.db.commit()
        _publish_listeners(call)
        await _publish_line(ctx.db, call)


@post("/calls/{call_id:str}/whisper", status_code=202)
async def whisper(ctx: Ctx, call_id: str, data: w.WhisperIn) -> w.WhisperOut:
    ctx.require("calls:whisper")
    call = await _live_call(ctx, call_id)
    text = " ".join(data.text.split())
    if not text or len(text) > 280:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "text", "message": "Write a note of up to 280 characters."}],
        )
    row = Whisper(
        org_id=ctx.org_id,
        call_id=call.id,
        author_id=ctx.user.id,
        author_name=_who(ctx),
        text=text,
        at=clock.now(),
        at_ms=runtime.at_ms(call),
    )
    ctx.db.add(row)
    await ctx.db.commit()
    await _event(call, "whisper", f"{_who(ctx)} whispered to ClaimVoice", ctx, {"text": text})
    await ctx.audit(
        "call.whisper",
        f"{_who(ctx)} whispered to the line on {_line_name(call)}.",
        target_type="call",
        target_id=call.id,
        target_label=_line_name(call),
        details={"text": text},
    )
    bus.publish(
        call_key(call.id),
        "whisper.sent",
        {"id": row.id, "text": text, "by": _who(ctx), "at": row.at.isoformat()},
        org_id=ctx.org_id,
        call_id=call.id,
    )
    if runtime.holds(call.id):
        rt = runtime.line_runtime()
        assert rt is not None
        await rt.whisper(call.id, text, from_name=_who(ctx))
    return w.WhisperOut(id=row.id, at=row.at)


async def _take(ctx: Ctx, call: Call) -> None:
    """Make the current user the person on the call (take-over or accepted hand-off)."""
    other = next(
        (x for x in call.listeners or [] if x.get("mode") == "took_over" and x.get("userId") != ctx.user.id), None
    )
    if other is not None:
        raise ProblemError(
            409, "already_taken", "Someone else has this call", f"{other['name']} is already on the call."
        )
    call.listeners = [
        *_listeners_without(call, ctx.user.id),
        {"userId": ctx.user.id, "name": _who(ctx), "mode": "took_over"},
    ]
    call.state = "with_person"
    if call.stage != "handoff":
        call.resume_stage = call.stage
        call.stage = "handoff"
    await ctx.db.commit()
    if runtime.holds(call.id):
        rt = runtime.line_runtime()
        assert rt is not None
        await rt.take_over(call.id, user_id=ctx.user.id, name=_who(ctx))


@post("/calls/{call_id:str}/takeover", status_code=200)
async def takeover(ctx: Ctx, call_id: str) -> w.TakeoverOut:
    ctx.require("calls:takeover")
    call = await _live_call(ctx, call_id)
    await _take(ctx, call)
    await _event(call, "takeover", f"{_who(ctx)} took over the call", ctx, {"state": "accepted"})
    await ctx.audit(
        "call.takeover",
        f"{_who(ctx)} took over {_line_name(call)}.",
        target_type="call",
        target_id=call.id,
        target_label=_line_name(call),
    )
    _publish_listeners(call)
    await _publish_line(ctx.db, call)
    return w.TakeoverOut(call=await views.detail(ctx.db, call, ctx.lang, siu=ctx.siu), connect=None)


def _require_on_call(ctx: Ctx, call: Call) -> None:
    if not any(x.get("userId") == ctx.user.id and x.get("mode") == "took_over" for x in call.listeners or []):
        raise ProblemError(
            409,
            "not_taken_over",
            "Take over the call first",
            "Only the person on the call can speak to the caller or hand the call back.",
        )


@post("/calls/{call_id:str}/say", status_code=202)
async def say(ctx: Ctx, call_id: str, data: w.SayIn) -> dict[str, str]:
    ctx.require("calls:takeover")
    call = await _live_call(ctx, call_id)
    _require_on_call(ctx, call)
    text = " ".join(data.text.split())
    if not text or len(text) > 500:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "text", "message": "Write up to 500 characters."}],
        )
    if runtime.holds(call.id):
        rt = runtime.line_runtime()
        assert rt is not None
        turn_id = await rt.say_as_person(call.id, text, user_id=ctx.user.id, name=_who(ctx))
    else:
        turn_id = await runtime.platform_person_turn(call.id, text, user_id=ctx.user.id, name=_who(ctx))
    return {"turnId": turn_id}


@post("/calls/{call_id:str}/return", status_code=200)
async def hand_back(ctx: Ctx, call_id: str) -> w.CallDetail:
    ctx.require("calls:takeover")
    call = await _live_call(ctx, call_id)
    _require_on_call(ctx, call)
    call.listeners = [
        *_listeners_without(call, ctx.user.id),
        {"userId": ctx.user.id, "name": _who(ctx), "mode": "listening"},
    ]
    call.state = "with_line"
    if call.stage == "handoff":
        call.stage = call.resume_stage or "loss_details"
        call.resume_stage = None
    handoff = await views.current_handoff(ctx.db, call)
    if handoff is not None:
        handoff.state, handoff.resolved_at = "returned_to_line", clock.now()
    await ctx.db.commit()
    if runtime.holds(call.id):
        rt = runtime.line_runtime()
        assert rt is not None
        await rt.hand_back(call.id, user_id=ctx.user.id)
    await _event(call, "returned", f"{_who(ctx)} handed the call back to ClaimVoice", ctx)
    await ctx.audit(
        "call.returned",
        f"{_who(ctx)} handed {_line_name(call)} back to ClaimVoice.",
        target_type="call",
        target_id=call.id,
        target_label=_line_name(call),
    )
    _publish_listeners(call)
    await _publish_line(ctx.db, call)
    return await views.detail(ctx.db, call, ctx.lang, siu=ctx.siu)


async def _hang_up(db: AsyncSession, call: Call, reason: str, by_user_id: str | None) -> None:
    from claimvoice.calls.closing import close_call

    if runtime.holds(call.id):
        rt = runtime.line_runtime()
        assert rt is not None
        await rt.hang_up(call.id, reason=reason, by_user_id=by_user_id)
        sink = sink_for(call.org_id)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(sink.wait_closed(call.id), timeout=3)
    else:
        await close_call(call.org_id, call.id, None, reason="ended_by_person" if by_user_id else "caller_hung_up")
    await db.refresh(call)


@post("/calls/{call_id:str}/hangup", status_code=200)
async def hangup(
    request: Request[Any, Any, Any], db_session: AsyncSession, call_id: str, data: w.HangupIn
) -> w.CallDetail:
    from claimvoice.api.context import provide_ctx

    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        call = await _caller_call(request, db_session, call_id)
        await _hang_up(db_session, call, data.reason, None)
        return await views.detail(db_session, call, "en", siu=False)
    ctx = await provide_ctx(request, db_session)
    ctx.require("calls:hangup")
    call = await _live_call(ctx, call_id)
    label = _line_name(call)
    await _hang_up(ctx.db, call, data.reason, ctx.user.id)
    await ctx.audit(
        "call.hangup",
        f"{_who(ctx)} ended {label}.",
        target_type="call",
        target_id=call.id,
        target_label=label,
        details={"reason": data.reason, "note": data.note},
    )
    return await views.detail(ctx.db, call, ctx.lang, siu=ctx.siu)


@post("/calls/{call_id:str}/handoff", status_code=200)
async def handoff(ctx: Ctx, call_id: str, data: w.HandoffIn) -> w.HandoffInfo:
    ctx.require("calls:handoff")
    call = await _live_call(ctx, call_id)
    reason = " ".join(data.reason.split())
    if not reason or len(reason) > 200:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "reason", "message": "Give a one-line reason."}],
        )
    if data.to_user_id:
        member = (
            await ctx.db.execute(
                select(Membership).where(Membership.org_id == ctx.org_id, Membership.user_id == data.to_user_id)
            )
        ).scalar_one_or_none()
        if member is None:
            raise ProblemError(
                422,
                "validation_error",
                "Validation failed",
                errors=[{"field": "toUserId", "message": "Choose someone in your organisation."}],
            )
    from claimvoice.calls.sink import handoff_summary

    h = Handoff(
        org_id=ctx.org_id,
        call_id=call.id,
        reason="supervisor",
        detail=reason,
        priority="normal",
        state="waiting",
        requested_at=clock.now(),
        summary=await handoff_summary(ctx.db, call, reason),
        actions=[],
        to_user_id=data.to_user_id,
        team=None if data.to_user_id else (data.team or "intake"),
    )
    ctx.db.add(h)
    call.listeners = _listeners_without(call, ctx.user.id)
    call.state = "waiting_for_person"
    await ctx.db.commit()
    await _event(
        call,
        "handoff",
        f"{_who(ctx)} handed the call off: {reason}",
        ctx,
        {"reason": "supervisor", "priority": "normal", "state": "waiting"},
    )
    people = await views.users_by_id(ctx.db, [h.to_user_id])
    info = views.handoff_out(h, call, ctx.lang, people)
    bus.publish(
        org_key(ctx.org_id),
        "handoff.requested",
        views.handoff_out(h, call, "en", people),
        org_id=ctx.org_id,
        call_id=call.id,
    )
    await _publish_line(ctx.db, call)
    return info


@post("/calls/{call_id:str}/handoff/accept", status_code=200)
async def accept_handoff(ctx: Ctx, call_id: str) -> w.HandoffAcceptOut:
    ctx.require("calls:handoff")
    call = await _live_call(ctx, call_id)
    h = (
        await ctx.db.execute(
            select(Handoff).where(Handoff.call_id == call.id).order_by(Handoff.requested_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if h is None:
        raise not_found()
    if h.state not in ("waiting", "callback_offered"):
        who = await ctx.db.get(User, h.accepted_by) if h.accepted_by else None
        raise ProblemError(
            409,
            "already_taken",
            "Someone else took this call",
            f"{who.full_name if who else 'Someone'} already accepted it.",
        )
    h.state, h.accepted_by, h.accepted_at = "accepted", ctx.user.id, clock.now()
    await ctx.db.commit()
    await _take(ctx, call)
    await _event(
        call,
        "handoff",
        f"{_who(ctx)} accepted the hand-off",
        ctx,
        {"reason": h.reason, "priority": h.priority, "state": "accepted"},
    )
    await ctx.audit(
        "call.handoff_accepted",
        f"{_who(ctx)} took the hand-off on {_line_name(call)}.",
        target_type="call",
        target_id=call.id,
        target_label=_line_name(call),
    )
    people = await views.users_by_id(ctx.db, [h.accepted_by, h.to_user_id])
    bus.publish(
        org_key(ctx.org_id),
        "handoff.updated",
        views.handoff_out(h, call, "en", people),
        org_id=ctx.org_id,
        call_id=call.id,
    )
    bus.publish(
        call_key(call.id),
        "handoff.updated",
        views.handoff_out(h, call, "en", people),
        org_id=ctx.org_id,
        call_id=call.id,
    )
    _publish_listeners(call)
    await _publish_line(ctx.db, call)
    return w.HandoffAcceptOut(
        handoff=views.handoff_out(h, call, ctx.lang, people), listen=w.ListenOut(mode="transcript", connect=None)
    )


ROUTER = Router(
    path="/api/v1",
    route_handlers=[
        live_calls,
        list_calls,
        get_call,
        get_transcript,
        get_claim_file,
        get_timeline,
        get_messages,
        call_stream,
        call_recording,
        call_audio,
        start_call,
        start_demo_call,
        webrtc_offer,
        webrtc_ice,
        call_ws,
        listen,
        stop_listening,
        whisper,
        takeover,
        say,
        hand_back,
        hangup,
        handoff,
        accept_handoff,
    ],
)
