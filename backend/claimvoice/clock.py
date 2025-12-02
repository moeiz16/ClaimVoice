"""Demo clock: one switch for "now" across the API, the voice runtime, the seed and the models.

`CLAIMVOICE_DEMO_TODAY=2026-01-08` (the default in `.env.example`) shifts the server's idea of today to that date, so
seeded calls, claims, the Calgary hail surge, "received 4 minutes ago" and every displayed date read as of that day
(walkthroughs and portfolio screenshots). The shift is a whole number of days (demo date minus the real date when the
process starts), so separate processes that read the same setting agree and the time of day still advances normally.
`CLAIMVOICE_DEMO_TODAY=off` means real time.

`CLAIMVOICE_DEMO_TIME=07:42` also pins the time of day: at the anchor moment the clock reads demo date + demo time in
`CLAIMVOICE_DEMO_TZ` (default America/Edmonton, Larkspur Mutual's head office) and then runs normally. The anchor
(real instant <-> demo instant) is shared through `data/demo-clock.json`: `seed`/`reset` write a fresh one and every
other process reads it, so they all agree. An anchor older than 12 hours, or one for another demo moment, is replaced.

Rules:
* Business code calls `clock.now()` / `clock.today()`, never `datetime.now()` / `date.today()`.
* Security timers (session idle/absolute expiry, rate limits, photo-link token expiry, cookie max-age) use
  `clock.real_now()`; they must not move with the demo date.
* Every API response carries `X-ClaimVoice-Now` (= `now()`), so the web app never trusts the browser clock.
* Audio and latency timing inside a call uses `time.perf_counter()` (monotonic), never this module.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

_offset = timedelta(0)
_installed = False

ANCHOR_MAX_AGE = timedelta(hours=12)


def real_now() -> datetime:
    """Wall-clock UTC time, never shifted."""
    return datetime.now(UTC)


def now() -> datetime:
    """Current UTC time (shifted when the demo clock is installed)."""
    return real_now() + _offset


def today(tz: tzinfo | str | None = None) -> date:
    """Today's date, in UTC unless a zone is given (a tzinfo or an IANA name such as "America/Edmonton")."""
    current = now()
    if isinstance(tz, str):
        tz = ZoneInfo(tz)
    return (current.astimezone(tz) if tz else current).date()


def offset() -> timedelta:
    return _offset


def is_shifted() -> bool:
    return _offset != timedelta(0)


def header_value() -> str:
    """The `X-ClaimVoice-Now` header: ISO-8601 UTC with seconds."""
    return now().isoformat(timespec="seconds")


def _read_anchor(path: Path, target: datetime) -> datetime | None:
    """The real instant at which the demo clock read `target`, when the anchor file is for this target and fresh."""
    try:
        doc = json.loads(path.read_text())
        if datetime.fromisoformat(doc["demoAt"]) != target:
            return None
        real_at = datetime.fromisoformat(doc["realAt"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return real_at if timedelta(0) <= real_now() - real_at <= ANCHOR_MAX_AGE else None


def _write_anchor(path: Path, target: datetime, real_at: datetime) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"demoAt": target.isoformat(), "realAt": real_at.isoformat()}))
        tmp.replace(path)
    except OSError:  # read-only checkout: this process still runs on its own anchor
        pass


def install(
    demo_today: date | str | None,
    demo_time: time | str | None = None,
    *,
    tz: str = "America/Edmonton",
    anchor_file: Path | None = None,
    fresh: bool = False,
) -> timedelta:
    """Shift `now()` so that `today()` is `demo_today` (and, with `demo_time`, so that the clock read that time of
    day in `tz` at the shared anchor moment). Idempotent; returns the offset applied."""
    global _offset, _installed
    if not demo_today:
        return timedelta(0)
    target_day = date.fromisoformat(demo_today) if isinstance(demo_today, str) else demo_today
    if not demo_time:
        _offset = timedelta(days=(target_day - real_now().date()).days)
    else:
        at = time.fromisoformat(demo_time) if isinstance(demo_time, str) else demo_time
        target = datetime.combine(target_day, at.replace(tzinfo=None), ZoneInfo(tz)).astimezone(UTC)
        real_at = None if fresh or anchor_file is None else _read_anchor(anchor_file, target)
        if real_at is None:
            real_at = real_now()
            if anchor_file is not None:
                _write_anchor(anchor_file, target, real_at)
        _offset = target - real_at
    _installed = True
    return _offset


def install_from_settings(*, fresh: bool = False) -> timedelta:
    """Called once at process start (API lifespan, CLI). `fresh` (seed and reset) starts a new shared anchor when the
    time of day is pinned."""
    from claimvoice.config import get_settings

    s = get_settings()
    return install(
        s.demo_today,
        s.claimvoice_demo_time,
        tz=s.claimvoice_demo_tz,
        anchor_file=s.data_dir / "demo-clock.json",
        fresh=fresh,
    )


def uninstall() -> None:
    """Back to real time (tests)."""
    global _offset, _installed
    _offset, _installed = timedelta(0), False


@contextmanager
def travel(moment: datetime) -> Iterator[None]:
    """Run business code as if `now()` were `moment` (the seed writes historical calls at their back-dated times).
    Restores the previous offset afterwards. Not for request handling: the offset is process-wide."""
    global _offset
    previous = _offset
    _offset = moment - real_now()
    try:
        yield
    finally:
        _offset = previous
