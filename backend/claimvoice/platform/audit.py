"""Hash-chained audit trail. Each organisation has its own chain: event n stores sha256(prev_hash + canonical(event)).
Tampering with any stored field, or deleting/reordering a row, breaks verification from that point on.

This module holds the pure functions (hashing and verification). The writer (`record(...)`, which takes the next
`seq` under a lock and inserts the row in the caller's transaction) belongs to the platform services."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

GENESIS = "0" * 64
HASHED_FIELDS = (
    "org_id",
    "seq",
    "at",
    "actor_user_id",
    "actor_label",
    "action",
    "target_type",
    "target_id",
    "summary",
    "details",
)


def canonical(event: Mapping[str, Any]) -> str:
    """Stable JSON for hashing: fixed field set, sorted keys, UTC ISO timestamps, no whitespace."""
    doc: dict[str, Any] = {}
    for key in HASHED_FIELDS:
        value = event.get(key)
        if isinstance(value, datetime):
            value = value.isoformat(timespec="microseconds")
        doc[key] = value
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def chain_hash(prev_hash: str, event: Mapping[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical(event)).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ChainCheck:
    ok: bool
    checked: int
    first_broken_seq: int | None = None
    reason: str | None = None


def verify(events: Iterable[Mapping[str, Any]]) -> ChainCheck:
    """Verify one organisation's chain, given its events in `seq` order (each with prev_hash and hash)."""
    prev = GENESIS
    expected_seq = 1
    checked = 0
    for ev in events:
        seq = int(ev["seq"])
        if seq != expected_seq:
            return ChainCheck(False, checked, seq, f"expected entry {expected_seq}, found {seq}")
        if ev["prev_hash"] != prev:
            return ChainCheck(False, checked, seq, "link to the previous entry does not match")
        if chain_hash(prev, ev) != ev["hash"]:
            return ChainCheck(False, checked, seq, "entry content was changed after it was written")
        prev = ev["hash"]
        expected_seq += 1
        checked += 1
    return ChainCheck(True, checked)
