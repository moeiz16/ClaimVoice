"""The daily retention job (docs/API_CONTRACT.md Part 2, ADR 0005): removes recordings, transcripts and photos past
each organisation's retention, keeps the claim file (it is the claim), clears finished landing-page demo calls, and
writes `retention.purged` to the activity log. Runs in the API process once a day; `purge()` is callable directly."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from sqlalchemy import delete, select

from claimvoice import clock
from claimvoice.calls.models import Call, CallTurn, Whisper
from claimvoice.claims.models import ClaimPhoto
from claimvoice.config import get_settings
from claimvoice.platform import auditlog, db
from claimvoice.platform.models import Organization
from claimvoice.settings import service

log = structlog.get_logger("claimvoice.retention")
YEAR = timedelta(days=365)
PUBLIC_DEMO_KEEP = timedelta(minutes=10)


@dataclass
class Purged:
    recordings: int = 0
    transcripts: int = 0
    turns: int = 0
    photos: int = 0
    demo_calls: int = 0
    orgs: dict[str, dict[str, int]] = field(default_factory=dict)


def _unlink(rel: str | None, base: str) -> None:
    if not rel:
        return
    root = get_settings().recordings_dir if base == "recordings" else get_settings().uploads_dir
    path = (root / rel).resolve()
    if root.resolve() in path.parents:
        with contextlib.suppress(OSError):
            path.unlink()


async def purge(*, now: datetime | None = None) -> Purged:
    now = now or clock.now()
    total = Purged()
    async with db.sessionmaker()() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        for org in orgs:
            r = service.section(org, "retention")
            rec_cut = now - YEAR * int(r["recordingsYears"])
            tr_cut = now - YEAR * int(r["transcriptsYears"])
            ph_cut = now - YEAR * int(r["photosYears"])
            counts = {"recordings": 0, "transcripts": 0, "turns": 0, "photos": 0, "demoCalls": 0}
            old = (
                (
                    await session.execute(
                        select(Call).where(
                            Call.org_id == org.id, Call.state == "ended", Call.ended_at < max(rec_cut, tr_cut)
                        )
                    )
                )
                .scalars()
                .all()
            )
            for call in old:
                assert call.ended_at is not None
                consent = dict(call.consent or {})
                if call.ended_at < rec_cut and not consent.get("purgedAt"):
                    _unlink(call.recording_path, "recordings")
                    _unlink(f"sample/{call.id}.wav", "recordings")
                    call.recording_path = None
                    consent["purgedAt"] = now.isoformat()
                    call.consent = consent
                    counts["recordings"] += 1
                if call.ended_at < tr_cut:
                    gone = await session.execute(delete(CallTurn).where(CallTurn.call_id == call.id))
                    await session.execute(delete(Whisper).where(Whisper.call_id == call.id))
                    if getattr(gone, "rowcount", 0):
                        counts["transcripts"] += 1
                        counts["turns"] += int(getattr(gone, "rowcount", 0))
            photos = (
                (
                    await session.execute(
                        select(ClaimPhoto).where(ClaimPhoto.org_id == org.id, ClaimPhoto.received_at < ph_cut)
                    )
                )
                .scalars()
                .all()
            )
            for p in photos:
                _unlink(p.path, "uploads")
                _unlink(p.thumbnail_path, "uploads")
                await session.delete(p)
                counts["photos"] += 1
            demo = (
                (
                    await session.execute(
                        select(Call).where(
                            Call.org_id == org.id,
                            Call.is_public_demo.is_(True),
                            Call.state == "ended",
                            Call.ended_at < now - PUBLIC_DEMO_KEEP,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for call in demo:
                await session.delete(call)
                counts["demoCalls"] += 1
            r["lastPurgeAt"] = now.isoformat()
            service.put_section(org, "retention", r)
            await session.commit()
            total.recordings += counts["recordings"]
            total.transcripts += counts["transcripts"]
            total.turns += counts["turns"]
            total.photos += counts["photos"]
            total.demo_calls += counts["demoCalls"]
            total.orgs[org.id] = counts
            if counts["recordings"] or counts["transcripts"] or counts["photos"]:
                await auditlog.record(
                    org.id,
                    auditlog.Entry(
                        action="retention.purged",
                        summary=(
                            f"Retention removed {counts['recordings']} recording(s), {counts['transcripts']} "
                            f"transcript(s) and {counts['photos']} photo(s) past their keep period; claim files "
                            "are kept."
                        ),
                        target_type="retention",
                        target_id="daily",
                        target_label="Retention",
                        details=counts,
                        at=now,
                    ),
                )
    return total


def start_daily() -> asyncio.Task[None]:
    async def loop() -> None:
        while True:
            try:
                await purge()
            except Exception:
                log.exception("retention_failed")
            await asyncio.sleep(24 * 3600)

    return asyncio.get_running_loop().create_task(loop())
