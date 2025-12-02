"""§1.9 call quality: review queue, scores, reviewer verdicts, scorer agreement."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from claimvoice.schemas.base import Lang, Model, PersonRef

Band = Literal["good", "needs_attention", "failed"]


class RubricItemInfo(Model):
    key: str
    label: str
    description: str
    points: float
    critical: bool


class Evidence(Model):
    turn_id: str
    quote: str  # redacted, ≤ 160 characters


class Bead(Model):
    """One of the six headline rubric beads: Consent first · Identity checked · Required details (9/10) · Kind words ·
    No card numbers · Right hand-off."""

    key: str
    label: str
    passed: bool | None
    detail: str | None  # "9/10"


class Focus(Model):
    """Where the review opens: "Jumped to 4:10, where the hand-off came 40 seconds late"."""

    at_seconds: float
    text: str


class QaItem(Model):
    key: str
    label: str
    passed: bool | None  # null = not applicable
    points: float
    max_points: float
    critical: bool
    method: Literal["rule", "language_check"]
    note: str
    evidence: list[Evidence]
    at_seconds: float | None  # where the bead pins on the recording
    reviewer_verdict: Literal["agree", "disagree"] | None
    reviewer_note: str | None


class QaScore(Model):
    call_id: str
    claim_number: str | None
    score: float  # 0..100
    band: Band
    band_label: str
    status: Literal["needs_review", "reviewed", "auto_passed"]
    items: list[QaItem]
    beads: list[Bead]
    focus: Focus | None
    scored_at: datetime
    scorer_version: str
    reviewed_by: PersonRef | None
    reviewed_at: datetime | None
    review_note: str | None


class QaQueueItem(Model):
    call_id: str
    reference: str
    claim_number: str | None
    started_at: datetime
    duration_seconds: int
    language: Lang
    loss_type_label: str | None
    score: float
    band: Band
    band_label: str
    failed_items: list[str]  # labels
    beads: list[Bead]
    caller_label: str
    line_label: str | None
    reviewer: PersonRef | None
    status: Literal["needs_review", "reviewed", "auto_passed"]
    reason_queued: str  # "Critical item failed: safety check" / "Random 10% sample"


class ReviewItemIn(Model):
    key: str
    verdict: Literal["agree", "disagree"]
    note: str | None = None


class ReviewIn(Model):
    items: list[ReviewItemIn]
    note: str | None = None
    coaching_note: str | None = None  # sent to the script owner


class AgreementRow(Model):
    key: str
    label: str
    reviewed: int
    agreement: float  # 0..1


class Agreement(Model):
    reviewed_calls: int
    overall: float
    cohen_kappa: float | None
    by_item: list[AgreementRow]
