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
    label: str  # "Fast track", "Adjuster review", "Special investigations review"
    decided_by: Literal["model", "person"]
    top_reason: str


class ClaimSummary(Model):
    id: str
    claim_number: str  # "LM-26-000412"
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
    surge_label: str | None  # "Calgary hail"
    is_sample: bool


class Claim(ClaimSummary):
    call_id: str | None
    policy_id: str
    holder_id: str
    description: str  # the caller's account, summarised in the call's language
    description_en: str | None
    flags: list[Flag]
    file: ClaimFile
    next_steps: list[str]
    recording_available: bool


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


class ScoreBand(Model):
    probability: float  # calibrated
    band: str  # severity: "low" | "medium" | "high"; fraud: "low" | "elevated" | "high"
    label: str  # "High chance of a large or complex loss"


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
    reasons: list[Reason]  # top 3-5
    rules_applied: list[str]  # "Injury reported: never fast-tracked"
    model_versions: dict[str, str]
    override: RouteOverride | None
    statement: str  # "Routing decides who looks at the claim first. It never approves or denies a claim."


class RouteOverrideIn(Model):
    route: Route
    reason: str


class SiuIndicator(Model):
    key: str
    label: str  # "Reported 41 days after the loss"
    evidence: str  # where it came from, plain words
    turn_id: str | None
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
