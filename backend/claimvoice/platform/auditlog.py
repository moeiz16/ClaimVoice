"""The audit writer: appends one entry to an organisation's hash chain (`platform.audit` holds the pure hashing).

Entries are written after the action they describe has been committed, in their own short transaction, under a
per-organisation lock, so concurrent requests in this process can never fork the chain. (Several API processes would
need a database lock instead; see docs/ARCHITECTURE.md "Deployment shape".)"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.platform import audit
from claimvoice.platform.models import AuditEvent

_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

SYSTEM = "ClaimVoice"


@dataclass(frozen=True, slots=True)
class Entry:
    action: str
    summary: str
    actor_user_id: str | None = None
    actor_label: str = SYSTEM
    target_type: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    ip: str | None = None
    at: datetime | None = None


def _row(org_id: str | None, seq: int, prev: str, entry: Entry) -> AuditEvent:
    details = dict(entry.details)
    if entry.target_label:
        details["targetLabel"] = entry.target_label
    doc: dict[str, Any] = {
        "org_id": org_id,
        "seq": seq,
        "at": entry.at or clock.now(),
        "actor_user_id": entry.actor_user_id,
        "actor_label": entry.actor_label,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "summary": entry.summary,
        "details": details,
    }
    return AuditEvent(**doc, ip=entry.ip, prev_hash=prev, hash=audit.chain_hash(prev, doc))


async def _tail(session: AsyncSession, org_id: str | None) -> tuple[int, str]:
    cond = AuditEvent.org_id == org_id if org_id else AuditEvent.org_id.is_(None)
    last = (
        await session.execute(
            select(AuditEvent.seq, AuditEvent.hash).where(cond).order_by(AuditEvent.seq.desc()).limit(1)
        )
    ).first()
    return (int(last[0]), str(last[1])) if last else (0, audit.GENESIS)


async def record_many(org_id: str | None, entries: Sequence[Entry]) -> list[AuditEvent]:
    """Append entries in order, in one transaction (the seed uses this for the back-dated trail)."""
    from claimvoice.platform import db

    if not entries:
        return []
    async with _locks[org_id or "-"], db.sessionmaker()() as session:
        seq, prev = await _tail(session, org_id)
        rows = []
        for entry in entries:
            seq += 1
            row = _row(org_id, seq, prev, entry)
            prev = row.hash
            session.add(row)
            rows.append(row)
        await session.commit()
        return rows


async def record(org_id: str | None, entry: Entry) -> AuditEvent:
    return (await record_many(org_id, [entry]))[0]


async def verify_org(session: AsyncSession, org_id: str) -> audit.ChainCheck:
    rows = (
        (await session.execute(select(AuditEvent).where(AuditEvent.org_id == org_id).order_by(AuditEvent.seq)))
        .scalars()
        .all()
    )
    return audit.verify(
        {
            "org_id": r.org_id,
            "seq": r.seq,
            "at": r.at,
            "actor_user_id": r.actor_user_id,
            "actor_label": r.actor_label,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "summary": r.summary,
            "details": r.details,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
        }
        for r in rows
    )
