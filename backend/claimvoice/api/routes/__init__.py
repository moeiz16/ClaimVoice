"""Route modules, one per contract area. Each exposes `ROUTER: litestar.Router`; `ROUTERS` registers them all."""

from __future__ import annotations

from typing import Any


def _routers() -> list[Any]:
    from claimvoice.api.routes import audit, auth, calls, checks, claims, orgs, policies, qa, settings, switchboard

    return [m.ROUTER for m in (auth, orgs, policies, calls, claims, switchboard, qa, checks, settings, audit)]


ROUTERS = _routers()
