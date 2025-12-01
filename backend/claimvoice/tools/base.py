"""Tool runner: every mid-call tool has a budget; a timeout or error returns a fallback, never stalls the turn."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")

# Budgets in milliseconds (docs/ARCHITECTURE.md latency budget). The line says a filler ("One moment while I pull up
# your policy") when a tool is expected to take longer than 300 ms.
BUDGETS_MS: dict[str, int] = {
    "policy_lookup": 300,
    "identity_check": 200,
    "coverage_check": 300,
    "photo_link_sms": 600,
    "weather_lookup": 400,
}


@dataclass(frozen=True, slots=True)
class ToolTiming:
    tool: str
    ok: bool
    elapsed_ms: float
    budget_ms: int
    timed_out: bool
    error: str | None = None


async def run_tool[T](
    name: str, call: Callable[[], Awaitable[T]], *, fallback: T, budget_ms: int | None = None
) -> tuple[T, ToolTiming]:
    budget = budget_ms if budget_ms is not None else BUDGETS_MS.get(name, 500)
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(call(), timeout=budget / 1000)
        timing = ToolTiming(name, True, (time.perf_counter() - started) * 1000, budget, False)
        return result, timing
    except TimeoutError:
        return fallback, ToolTiming(name, False, (time.perf_counter() - started) * 1000, budget, True, "timeout")
    except Exception as exc:  # a tool failure must never end the call
        err = type(exc).__name__
        return fallback, ToolTiming(name, False, (time.perf_counter() - started) * 1000, budget, False, err)


def summarize(timings: list[ToolTiming]) -> dict[str, Any]:
    return {
        "calls": len(timings),
        "timeouts": sum(t.timed_out for t in timings),
        "maxMs": round(max((t.elapsed_ms for t in timings), default=0.0), 1),
    }
