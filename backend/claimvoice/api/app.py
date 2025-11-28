"""Litestar application factory. Run: `uvicorn claimvoice.api.app:app --port 8040` (make api)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from litestar import Litestar, Response, get
from litestar.config.cors import CORSConfig
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from claimvoice import __version__, clock
from claimvoice.api.middleware import add_response_headers
from claimvoice.config import get_settings
from claimvoice.platform import db
from claimvoice.platform.errors import EXCEPTION_HANDLERS


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
async def lifespan(_app: Litestar) -> AsyncIterator[None]:
    clock.install_from_settings()
    db.get_engine()
    try:
        yield
    finally:
        await db.dispose()


def create_app() -> Litestar:
    settings = get_settings()
    route_handlers: list[Any] = [health, metrics]
    # Contract routers register here as they land, e.g.:
    #   from claimvoice.api.routes import auth, orgs, calls, voice, claims, switchboard, qa, models, settings, audit
    #   route_handlers += [auth.ROUTER, ...]
    return Litestar(
        route_handlers=route_handlers,
        lifespan=[lifespan],
        before_send=[add_response_headers],
        exception_handlers=EXCEPTION_HANDLERS,
        cors_config=CORSConfig(allow_origins=[settings.web_origin], allow_credentials=True),
        request_max_body_size=20 * 1024 * 1024,  # photo uploads; JSON bodies are capped per route
        openapi_config=None,
    )


app = create_app()
