"""Litestar application factory. Run: `uvicorn claimvoice.api.app:app --port 8040` (make api)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from litestar import Litestar, Response, get
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from claimvoice import __version__, clock
from claimvoice.api.context import DEPENDENCIES
from claimvoice.api.middleware import add_response_headers, guard_middleware
from claimvoice.config import get_settings
from claimvoice.platform import db
from claimvoice.platform.errors import EXCEPTION_HANDLERS
from claimvoice.platform.ratelimit import RateLimiter


@get("/health", include_in_schema=False)
async def health() -> dict[str, Any]:
    """Liveness + database reachability. Never needs a session."""
    database = "ok"
    try:
        async with db.sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # health must answer even when the database is down
        database = "unavailable"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "version": __version__,
        "database": database,
        "now": clock.header_value(),
        "demoClock": clock.is_shifted(),
    }


@get("/metrics", include_in_schema=False)
async def metrics() -> Response[bytes]:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    from claimvoice.calls import runtime
    from claimvoice.settings import retention

    clock.install_from_settings()
    db.get_engine()
    background = []
    if app.state.get("background", True):
        await runtime.adopt_sample_lines()
        background.append(retention.start_daily())
    try:
        yield
    finally:
        for task in background:
            task.cancel()
        await runtime.shutdown()
        await db.dispose()


def create_app(
    *, background: bool = True, sse_close_when_idle: float | None = None, rate_limits: bool = True
) -> Litestar:
    """`background=False` skips adopting the sample lines and the daily retention job (tests);
    `sse_close_when_idle` ends SSE streams after that many idle seconds (tests)."""
    from claimvoice.api.routes import ROUTERS

    settings = get_settings()
    route_handlers: list[Any] = [health, metrics, *ROUTERS]
    state = State(
        {
            "limiter": RateLimiter()
            if rate_limits
            else RateLimiter(limits=dict.fromkeys(("auth", "public", "public_call", "api"), (10 ** 9, 60.0))),
            "background": background,
            "sse_close_when_idle": sse_close_when_idle,
        }
    )
    return Litestar(
        route_handlers=route_handlers,
        dependencies=DEPENDENCIES,
        middleware=[guard_middleware],
        state=state,
        lifespan=[lifespan],
        before_send=[add_response_headers],
        exception_handlers=EXCEPTION_HANDLERS,
        cors_config=CORSConfig(allow_origins=[settings.web_origin], allow_credentials=True),
        request_max_body_size=20 * 1024 * 1024,  # photo uploads; JSON bodies are capped per route
        openapi_config=None,
    )


app = create_app()
