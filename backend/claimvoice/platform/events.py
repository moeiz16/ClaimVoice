"""In-process event bus and Server-Sent Events framing (docs/API_CONTRACT.md §1.8).

Two kinds of stream: the organisation's line desk (`org:{org_id}`) and one call (`call:{call_id}`). Each stream has
its own increasing integer ids and keeps the last five minutes of events, so a client that reconnects with
`Last-Event-ID` gets what it missed; an older gap (or ids from before a restart) gets `event: resync` and reloads the
snapshot. Transient events (live captions) carry no id and are never replayed.

Events are filtered per subscriber: without `siu:read`, closer-look signals and fraud fields are removed."""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import AsyncIterator, Collection
from dataclasses import dataclass, field
from typing import Any

import msgspec

from claimvoice import clock

REPLAY_SECONDS = 300.0
PING_SECONDS = 15.0
RETRY_MS = 3000  # always an integer: browsers ignore a non-numeric retry field
_QUEUE_MAX = 1000
_KEEP_MAX = 5000


@dataclass(slots=True)
class Event:
    id: int | None
    type: str
    envelope: dict[str, Any]
    at: float = 0.0  # monotonic


@dataclass
class _Stream:
    next_id: int = 1
    recent: deque[Event] = field(default_factory=lambda: deque(maxlen=_KEEP_MAX))
    subs: set[asyncio.Queue[Event]] = field(default_factory=set)


def to_data(value: Any) -> Any:
    """msgspec structs and dataclasses to JSON-ready builtins (camelCase keys, ISO datetimes)."""
    return msgspec.to_builtins(value)


class EventBus:
    def __init__(self) -> None:
        self._streams: dict[str, _Stream] = {}

    def _stream(self, key: str) -> _Stream:
        stream = self._streams.get(key)
        if stream is None:
            stream = self._streams[key] = _Stream()
        return stream

    def last_id(self, key: str) -> int:
        stream = self._streams.get(key)
        return 0 if stream is None else stream.next_id - 1

    def publish(
        self,
        key: str,
        type_: str,
        data: Any,
        *,
        org_id: str,
        call_id: str | None = None,
        transient: bool = False,
    ) -> int | None:
        stream = self._stream(key)
        envelope = {
            "type": type_,
            "at": clock.now().isoformat(timespec="seconds"),
            "orgId": org_id,
            "callId": call_id,
            "data": to_data(data),
        }
        event_id = None
        if not transient:
            event_id = stream.next_id
            stream.next_id += 1
        event = Event(event_id, type_, envelope, time.monotonic())
        if not transient:
            stream.recent.append(event)
            cutoff = event.at - REPLAY_SECONDS
            while stream.recent and stream.recent[0].at < cutoff:
                stream.recent.popleft()
        for q in list(stream.subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # a stalled client; it will resync on reconnect
                stream.subs.discard(q)
        return event_id

    def subscribe(self, key: str, last_event_id: int | None) -> tuple[asyncio.Queue[Event], list[Event], bool]:
        """Returns (queue, replay, resync). Subscribe and replay happen atomically (no await in between)."""
        stream = self._stream(key)
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAX)
        stream.subs.add(q)
        replay: list[Event] = []
        resync = False
        if last_event_id is not None:
            newest = stream.next_id - 1
            cutoff = time.monotonic() - REPLAY_SECONDS
            kept = [e for e in stream.recent if e.at >= cutoff]
            oldest = kept[0].id if kept else stream.next_id
            if last_event_id > newest or (last_event_id < newest and (oldest or 0) > last_event_id + 1):
                resync = True
            else:
                replay = [e for e in kept if (e.id or 0) > last_event_id]
        return q, replay, resync

    def unsubscribe(self, key: str, q: asyncio.Queue[Event]) -> None:
        stream = self._streams.get(key)
        if stream is not None:
            stream.subs.discard(q)

    def subscribers(self) -> int:
        return sum(len(s.subs) for s in self._streams.values())

    def reset(self) -> None:
        self._streams.clear()


bus = EventBus()


def org_key(org_id: str) -> str:
    return f"org:{org_id}"


def call_key(call_id: str) -> str:
    return f"call:{call_id}"


# ---------------------------------------------------------------- permission filtering

_SIU_FIELDS_NULL = ("fraud", "signs")


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in _SIU_FIELDS_NULL:
                out[k] = None
            elif k == "siuOpen":
                out[k] = False
            elif k == "flags" and isinstance(v, list):
                out[k] = [_strip(f) for f in v if not (isinstance(f, dict) and f.get("kind") == "siu_signal")]
                out[k] = [f for f in out[k] if f != "siu_signal"]
            else:
                out[k] = _strip(v)
        return out
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def visible(event: Event, permissions: Collection[str]) -> dict[str, Any] | None:
    """The envelope this subscriber may see, or None to skip the event."""
    if "siu:read" in permissions:
        return event.envelope
    data = event.envelope.get("data")
    if event.type == "flag.raised" and isinstance(data, dict) and data.get("kind") == "siu_signal":
        return None
    return {**event.envelope, "data": _strip(data)}


# ---------------------------------------------------------------- SSE framing


def frame(type_: str, envelope: dict[str, Any] | None, event_id: int | None = None) -> bytes:
    lines = []
    if event_id is not None:
        lines.append(f"id: {int(event_id)}")
    lines.append(f"event: {type_}")
    payload = json.dumps(envelope if envelope is not None else {}, separators=(",", ":"), ensure_ascii=False)
    lines.append(f"data: {payload}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")


def retry_frame(ms: int = RETRY_MS) -> bytes:
    return f"retry: {int(ms)}\n\n".encode()


async def sse(
    key: str,
    *,
    org_id: str,
    permissions: Collection[str],
    last_event_id: int | None,
    ping_seconds: float = PING_SECONDS,
    close_when_idle: float | None = None,
) -> AsyncIterator[bytes]:
    """The SSE body. `close_when_idle` ends the stream after that many idle seconds (tests only)."""
    q, replay, resync = bus.subscribe(key, last_event_id)
    try:
        yield retry_frame()
        if resync:
            yield frame("resync", {"type": "resync", "at": clock.header_value(), "orgId": org_id, "data": {}})
        for event in replay:
            env = visible(event, permissions)
            if env is not None:
                yield frame(event.type, env, event.id)
        while True:
            timeout = close_when_idle if close_when_idle is not None else ping_seconds
            try:
                event = await asyncio.wait_for(q.get(), timeout=timeout)
            except TimeoutError:
                if close_when_idle is not None:
                    return
                yield frame("ping", {})
                continue
            env = visible(event, permissions)
            if env is not None:
                yield frame(event.type, env, event.id)
    finally:
        bus.unsubscribe(key, q)


def parse_last_event_id(value: str | None) -> int | None:
    if not value:
        return None
    try:
        n = int(value.strip())
    except ValueError:
        return None
    return n if n >= 0 else None
