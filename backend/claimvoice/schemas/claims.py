"""§1.7 claims: claim file, transcript, recording, photos, routing decision with reasons, SIU referral."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from claimvoice.schemas.base import Lang, Model, PersonRef
from claimvoice.schemas.calls import ClaimFile, Flag

Route = Literal["fast_track", "adjuster", "special_investigation"]
ClaimStatus = Literal["new", "assigned", "in_review", "waiting_on_customer", "closed"]


class RouteSummary(Model):
    route: Route
    label: str  # "Fast-track", "Adjuster", "Closer look"
    decided_by: Literal["model", "person"]
    top_reason: str


class ClaimSummary(Model):
    id: str
    claim_number: str  # "CV-26-01842"
    status: ClaimStatus
    status_label: str
    line: Literal["auto", "property"]
    loss_type: str
    loss_type_label: str
    loss_date: date | None
    loss_place: str | None  # "Saddle Ridge, Calgary"
    holder_name: str
    policy_number: str
    region_label: str
    language: Lang
    reported_at: datetime
    route: RouteSummary | None
    urgent_safety: bool
    siu_open: bool  # visible only with siu:read; false otherwise
    photos: int
    assigned_to: PersonRef | None
    surge_label: str | None  # "Chinook windstorm, Calgary"
    is_sample: bool


class Claim(ClaimSummary):
    call_id: str | None
    policy_id: str
    holder_id: str
    description: str  # the caller's account, summarised in the call's language
    description_en: str | None
    in_short: InShort
    flags: list[Flag]
    file: ClaimFile
    next_steps: list[str]
    recording_available: bool


class SummaryLink(Model):
    """A phrase of the written summary that links to where it was heard."""

    start: int
    end: int
    turn_id: str
    at_seconds: float | None


class InShort(Model):
    text: str  # the written summary ("In short")
    links: list[SummaryLink]
    checked_by: PersonRef | None  # "checked by Lena at 5:40"
    checked_at: datetime | None


class ClaimUpdateIn(Model):
    status: ClaimStatus | None = None


class AssignIn(Model):
    user_id: str | None  # null unassigns


class SlotEditIn(Model):
    key: str
    value: str | float | int | bool | None
    note: str  # why it changed; required


class FileEditIn(Model):
    slots: list[SlotEditIn]


class Moment(Model):
    """A pin on the recording: consent, policy found, safety, a closer-look sign, photos, read-back, claim number."""

    kind: Literal["consent", "policy", "safety", "sign", "photos", "read_back", "claim_number", "handoff", "whisper"]
    label: str
    at_seconds: float
    turn_id: str | None


class RecordingSegment(Model):
    """Speaker turns on the recording timeline (from the transcript)."""

    turn_id: str
    speaker: Literal["caller", "line", "person", "system"]
    start_seconds: float
    end_seconds: float
    paused: bool  # recording paused here (card number) — silence in the audio


class Recording(Model):
    available: bool
    reason: str | None  # when unavailable: "Caller did not consent to recording", "Removed after 90 days"
    audio_url: str | None  # GET, supports Range; audio/ogg (Opus) or audio/wav
    duration_seconds: float | None
    peaks: list[float] | None  # ~800 normalised peaks for wavesurfer.js, so the waveform draws before audio loads
    segments: list[RecordingSegment]
    moments: list[Moment]
    hushes: list[tuple[float, float]]  # [start, end] seconds where a card number was cut (hatched on the waveform)
    retained_until: date | None


class Photo(Model):
    id: str
    url: str  # GET image (EXIF location removed on upload)
    thumbnail_url: str
    caption: str | None
    received_at: datetime
    source: Literal["text_link", "uploaded_by_staff"]
    width: int
    height: int


class Reason(Model):
    feature: str
    text: str  # plain words in the viewer's language
    direction: Literal["raises", "lowers"]
    weight: float  # share of the explanation, 0..1
    turn_id: str | None  # the moment it was heard, when it came from the call
    at_seconds: float | None


class SettleRange(Model):
    low: float
    high: float
    currency: Literal["CAD", "USD"]


class ScoreBand(Model):
    probability: float  # calibrated; the UI shows it as "about 7 in 10", never as a decimal
    band: str  # size: "small" | "moderate" | "large"; closer look: "low" | "elevated" | "high"
    label: str  # "Likely size: Moderate"
    detail: str | None  # "Claims like this usually settle at $4,000 to $9,000"
    settle_range: SettleRange | None  # size check only


class RouteOverride(Model):
    route: Route
    reason: str
    by: PersonRef
    at: datetime


class RoutingDecision(Model):
    claim_id: str
    route: Route  # effective route (override wins)
    route_label: str
    model_route: Route
    decided_at: datetime
    severity: ScoreBand
    fraud: ScoreBand | None  # null without siu:read
    reasons: list[Reason]  # top 3 ("Why an adjuster, not fast-track"), each linked to a moment when heard
    signs: list[SiuIndicator] | None  # siu:read only: "Signs worth a closer look"
    signs_checked: int  # "3 of the 14 we check"
    accepted_by: PersonRef | None  # "Accept route"
    accepted_at: datetime | None
    rules_applied: list[str]  # "Injury reported: never fast-tracked"
    model_versions: dict[str, str]
    override: RouteOverride | None
    # "For a person to review. A sign is never a reason to deny a claim on its own, and nothing here was decided
    # automatically."
    statement: str


class RouteOverrideIn(Model):
    route: Route
    reason: str


class SiuIndicator(Model):
    """A sign worth a closer look. Never a reason to deny a claim on its own."""

    key: str
    label: str  # "Reported 9 days after the loss"
    evidence: str  # where it came from, plain words
    source: Literal["call", "policy", "claim_history", "weather"]
    source_label: str  # "▸ 2:41", "from the policy", "claim history", "weather records"
    turn_id: str | None
    at_seconds: float | None
    weight: float


class SiuReferral(Model):
    id: str
    claim_id: str
    claim_number: str
    status: Literal["open", "investigating", "closed_no_concern", "returned_to_adjuster"]
    status_label: str
    opened_at: datetime
    score: float
    indicators: list[SiuIndicator]
    decided_by: PersonRef | None
    decided_at: datetime | None
    note: str | None
    statement: str  # "A referral is a request for review. It is not a finding of fraud and never denies a claim."


class SiuDecisionIn(Model):
    decision: Literal["investigate", "close_no_concern", "return_to_adjuster"]
    note: str
