"""§1.8 the supervisor switchboard: snapshot + SSE events (org stream and per-call stream)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from claimvoice.schemas.base import Model
from claimvoice.schemas.calls import Flag, HandoffInfo, LiveLine, Slot, StageInfo, Turn
from claimvoice.schemas.claims import ClaimSummary


class Surge(Model):
    id: str
    kind: Literal["hail", "flood", "wind", "winter_storm", "rainfall", "wildfire"]
    kind_label: str
    title: str  # "Hail in Calgary"
    region: str
    region_label: str
    area_label: str  # "Calgary (northeast)"
    started_at: datetime
    ended_at: datetime | None
    active: bool
    source: str  # "Environment and Climate Change Canada alert (bundled snapshot)"
    calls_last_hour: int
    usual_calls_per_hour: float
    multiplier: float  # calls_last_hour / usual
    policies_in_area: int
    claims_so_far: int
    guidance: str  # "Hail-only vehicle claims with photos go to fast track."


class TodayStats(Model):
    calls_answered: int
    answered_first_ring_share: float  # 0..1
    median_handle_seconds: int
    handoffs: int
    claims_created: int
    average_qa_score: float | None
    surge_calls: int


class SwitchboardSnapshot(Model):
    lines: list[LiveLine]
    handoff_tray: list[HandoffInfo]  # waiting first, urgent first
    surge: Surge | None
    recent_claims: list[ClaimSummary]  # last 8
    today: TodayStats
    last_event_id: int  # resume the stream from here


# SSE: `id: <int>`, `event: <type>`, `data: <Envelope JSON>`. Types and their `data` payloads:
SWITCHBOARD_EVENTS: dict[str, str] = {
    "line.opened": "LiveLine",
    "line.updated": "LiveLine",
    "line.closed": "LineClosed",
    "handoff.requested": "HandoffInfo",
    "handoff.updated": "HandoffInfo",
    "surge.started": "Surge",
    "surge.updated": "Surge",
    "surge.ended": "Surge",
    "claim.created": "ClaimSummary",
    "claim.routed": "ClaimSummary",
    "qa.flagged": "QaQueueItem",
    "stats.updated": "TodayStats",
    "ping": "{}",
}

CALL_EVENTS: dict[str, str] = {
    "turn.partial": "{speaker, text}",
    "turn.final": "Turn",
    "slot.updated": "{slot: Slot, progress}",
    "stage.changed": "StageInfo",
    "flag.raised": "Flag",
    "handoff.updated": "HandoffInfo",
    "whisper.sent": "{id, text, by, at}",
    "listener.changed": "{listeners}",
    "tool.called": "{tool, label, elapsedMs, ok}",
    "call.ended": "{reason, claimId, claimNumber}",
    "ping": "{}",
}


class Envelope(Model):
    type: str
    at: datetime
    org_id: str
    call_id: str | None
    data: dict[str, Any]


class LineClosed(Model):
    call_id: str
    outcome: Literal["claim_created", "handed_off", "abandoned", "no_claim"]
    outcome_label: str
    claim_id: str | None
    claim_number: str | None


class TurnPartial(Model):
    speaker: Literal["caller"]
    text: str


class SlotUpdated(Model):
    slot: Slot
    progress: float


__all__ = [
    "Envelope",
    "Flag",
    "LineClosed",
    "SlotUpdated",
    "StageInfo",
    "Surge",
    "SwitchboardSnapshot",
    "TodayStats",
    "Turn",
    "TurnPartial",
]
