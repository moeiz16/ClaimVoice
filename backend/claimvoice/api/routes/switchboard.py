"""§1.8 the line desk: snapshot, org-wide SSE stream and the surge controls."""

from __future__ import annotations

from litestar import Router, get, post
from litestar.response import Stream
from sqlalchemy import select

from claimvoice import clock
from claimvoice.api.context import Ctx
from claimvoice.api.routes.stream import sse_response
from claimvoice.calls import desk
from claimvoice.calls.models import Surge
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.events import bus, org_key
from claimvoice.schemas.switchboard import StandbyIn, SurgeQuestionsIn, SwitchboardSnapshot
from claimvoice.schemas.switchboard import Surge as SurgeOut


@get("/switchboard")
async def switchboard(ctx: Ctx) -> SwitchboardSnapshot:
    ctx.require("lines:read")
    return await desk.snapshot(ctx.db, ctx.org, ctx.lang, siu=ctx.siu)


@get("/switchboard/stream")
async def switchboard_stream(ctx: Ctx) -> Stream:
    ctx.require("lines:read")
    return await sse_response(ctx, org_key(ctx.org_id))


@get("/surges")
async def list_surges(ctx: Ctx) -> list[SurgeOut]:
    ctx.require("lines:read")
    rows = (
        (await ctx.db.execute(select(Surge).where(Surge.org_id == ctx.org_id).order_by(Surge.started_at.desc())))
        .scalars()
        .all()
    )
    rows = sorted(rows, key=lambda s: s.ended_at is not None)
    return [await desk.surge_out(ctx.db, s, ctx.lang, ctx.org.timezone) for s in rows]


@get("/surges/{surge_id:str}")
async def get_surge(ctx: Ctx, surge_id: str) -> SurgeOut:
    ctx.require("lines:read")
    return await desk.surge_out(ctx.db, await ctx.get(Surge, surge_id), ctx.lang, ctx.org.timezone)


async def _publish(ctx: Ctx, surge: Surge) -> SurgeOut:
    bus.publish(
        org_key(ctx.org_id),
        "surge.updated",
        await desk.surge_out(ctx.db, surge, "en", ctx.org.timezone),
        org_id=ctx.org_id,
    )
    return await desk.surge_out(ctx.db, surge, ctx.lang, ctx.org.timezone)


@post("/surges/{surge_id:str}/standby", status_code=200)
async def call_standby(ctx: Ctx, surge_id: str, data: StandbyIn | None = None) -> SurgeOut:
    ctx.require("lines:manage")
    surge = await ctx.get(Surge, surge_id)
    if surge.ended_at is not None:
        raise ProblemError(409, "already_decided", "The surge has ended", "There's no surge to staff any more.")
    if surge.standby_called_at is None:
        surge.standby_called_at = clock.now()
        await ctx.db.commit()
        note = (data.note if data else None) or None
        await ctx.audit(
            "surge.standby_called",
            f"{ctx.user.full_name} brought in the standby team ({surge.standby_available}) for the {surge.title}.",
            target_type="surge",
            target_id=surge.id,
            target_label=surge.title,
            details={"note": note},
        )
    return await _publish(ctx, surge)


@post("/surges/{surge_id:str}/questions", status_code=200)
async def surge_questions(ctx: Ctx, surge_id: str, data: SurgeQuestionsIn) -> SurgeOut:
    ctx.require("lines:manage")
    surge = await ctx.get(Surge, surge_id)
    if surge.surge_questions_on != data.on:
        surge.surge_questions_on = data.on
        await ctx.db.commit()
        state = "on" if data.on else "off"
        await ctx.audit(
            "surge.questions",
            f"{ctx.user.full_name} switched the {surge.loss_type} surge questions {state}.",
            target_type="surge",
            target_id=surge.id,
            target_label=surge.title,
            details={"on": data.on},
        )
    return await _publish(ctx, surge)


ROUTER = Router(
    path="/api/v1",
    route_handlers=[switchboard, switchboard_stream, list_surges, get_surge, call_standby, surge_questions],
)
