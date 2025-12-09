"""Fixtures for the platform and API tests: a freshly seeded Larkspur Mutual per module, and clients signed in by
role (demo sign-in, cookie + CSRF), each with its own cookie jar."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
from litestar.testing import AsyncTestClient


def demo_clock() -> None:
    """The demo moment: Thursday 8 January 2026, 7:42 a.m. Calgary time (from now on, in this process)."""
    from claimvoice import clock

    clock.install("2026-01-08", "07:42", tz="America/Edmonton")


@pytest.fixture(autouse=True)
def _demo_moment() -> None:
    demo_clock()


@pytest.fixture(scope="module")
def seeded(migrated_db: str) -> str:
    """Seed once per module (about 2 s), so tests in other modules start from the same story."""
    from claimvoice.calls import runtime
    from claimvoice.calls.sink import forget_claim_counter
    from claimvoice.platform import db
    from claimvoice.platform.events import bus
    from claimvoice.seed import run

    async def go() -> None:
        await run()
        await db.dispose()

    demo_clock()
    runtime.use_runtime(None, disabled=True)
    forget_claim_counter()
    bus.reset()
    asyncio.run(go())
    return migrated_db


class Api:
    """A signed-in browser: cookies, the CSRF header on unsafe methods, JSON helpers."""

    def __init__(self, client: AsyncTestClient[Any]) -> None:
        self.c = client
        self.csrf = ""

    async def start(self) -> Api:
        await self.c.get("/api/v1/auth/csrf")
        self.csrf = self.c.cookies.get("cv_csrf") or ""
        return self

    def _h(self, headers: dict[str, str] | None) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf, **(headers or {})}

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.c.get(path, **kw)

    async def post(self, path: str, json: Any = None, headers: dict[str, str] | None = None, **kw: Any) -> Any:
        return await self.c.post(path, json=json, headers=self._h(headers), **kw)

    async def put(self, path: str, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        return await self.c.put(path, json=json, headers=self._h(headers))

    async def patch(self, path: str, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        return await self.c.patch(path, json=json, headers=self._h(headers))

    async def delete(self, path: str, headers: dict[str, str] | None = None) -> Any:
        return await self.c.delete(path, headers=self._h(headers))

    async def demo(self, role: str) -> Any:
        res = await self.post("/api/v1/auth/demo", {"role": role})
        assert res.status_code == 200, res.text
        return res.json()

    async def j(self, path: str) -> Any:
        res = await self.get(path)
        assert res.status_code == 200, (path, res.status_code, res.text[:300])
        return res.json()


@pytest.fixture
async def api_factory(seeded: str) -> AsyncIterator[Callable[..., Awaitable[Api]]]:
    """`await api_factory("supervisor")` -> a client signed in as that role (or anonymous with role=None)."""
    from claimvoice.api.app import create_app
    from claimvoice.platform import db

    opened: list[AsyncTestClient[Any]] = []

    async def make(role: str | None = None, *, rate_limits: bool = False) -> Api:
        client = AsyncTestClient(app=create_app(background=False, sse_close_when_idle=0.3, rate_limits=rate_limits))
        await client.__aenter__()
        opened.append(client)
        api = await Api(client).start()
        if role:
            await api.demo(role)
        return api

    yield make
    for client in opened:
        await client.__aexit__(None, None, None)
    await db.dispose()


@pytest.fixture
async def sup(api_factory: Callable[..., Awaitable[Api]]) -> Api:
    return await api_factory("supervisor")


@pytest.fixture
async def anon(api_factory: Callable[..., Awaitable[Api]]) -> Api:
    return await api_factory(None)
