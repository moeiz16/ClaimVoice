"""SSE responses for the line desk and per-call streams (framing in `platform.events`)."""

from __future__ import annotations

from litestar.response import Stream

from claimvoice.api.context import Ctx
from claimvoice.platform.events import parse_last_event_id, sse

SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


async def sse_response(ctx: Ctx, key: str) -> Stream:
    """Resume from `Last-Event-ID` (header, or `?lastEventId=` for clients that cannot set headers)."""
    last = parse_last_event_id(ctx.request.headers.get("last-event-id") or ctx.request.query_params.get("lastEventId"))
    idle = ctx.request.app.state.get("sse_close_when_idle")
    await ctx.db.close()  # nothing below reads the database; don't hold a connection for the life of the stream
    body = sse(key, org_id=ctx.org_id, permissions=ctx.perms, last_event_id=last, close_when_idle=idle)
    return Stream(body, media_type="text/event-stream", headers=SSE_HEADERS)
