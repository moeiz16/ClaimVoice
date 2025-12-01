"""§1.12 audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from claimvoice.schemas.base import Model


class AuditEntry(Model):
    id: str
    seq: int
    at: datetime
    actor_label: str
    action: str
    action_label: str  # "Took over a call", "Changed the routing of a claim"
    target_type: str | None
    target_id: str | None
    target_label: str | None  # "Call CV-260108-0042", "Claim LM-26-000412"
    summary: str
    details: dict[str, Any]


class ChainStatus(Model):
    ok: bool
    checked: int
    first_broken_seq: int | None
    reason: str | None
    checked_at: datetime
