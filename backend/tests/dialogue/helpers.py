"""Drive the dialogue engine with a few caller lines (no YAML file needed)."""

from __future__ import annotations

from typing import Any

from claimvoice.contracts import MemoryCallSink
from claimvoice.dialogue.simulate import SimResult, parse_caller, run_scenario


async def call(
    lines: list[str | dict[str, Any]],
    *,
    region: str = "CA-AB",
    phone: str | None = "+14035550142",
    mode: str = "browser_speech",
    sink: MemoryCallSink | None = None,
    hang_up: bool = True,
    **kw: Any,
) -> tuple[SimResult, MemoryCallSink]:
    sink = sink or MemoryCallSink()
    turns = [t if isinstance(t, dict) else {"text": t} for t in lines]
    caller = parse_caller({"key": "test", "region": region, "caller_phone": phone, "mode": mode, "turns": turns})
    result = await run_scenario(caller, sink, hang_up_after=hang_up, **kw)
    return result, sink


GORD_START = [
    "Hi, the wind last night tore up my house.",
    "Yes, that's fine.",
    "Sure, it's LM-AB-204118.",
    "March third, 1971.",
]
