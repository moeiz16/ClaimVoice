"""§1.6 calls: live lines, starting a browser call, transcript, live claim file, hand-off and supervisor actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from claimvoice.schemas.base import Lang, Model, PersonRef, TextSpan

CallMode = Literal["voice", "browser_speech", "typed"]
LineState = Literal["ringing", "with_line", "waiting_for_person", "with_person", "wrapping_up", "ended"]
Speaker = Literal["caller", "line", "person", "system"]
Sentiment = Literal["calm", "stressed", "distressed"]
FlagKind = Literal[
    "urgent_safety",
    "distress",
    "card_number_removed",
    "low_confidence",
    "siu_signal",
    "consent_refused",
    "surge",
    "language_switched",
]


class Flag(Model):
    kind: FlagKind
    label: str  # "Urgent safety", "Card number removed"
    detail: str  # plain words, e.g. "Caller smells gas near the furnace"
    severity: Literal["info", "warning", "critical"]
    at: datetime
    turn_id: str | None = None


class StageInfo(Model):
    key: str  # dialogue Stage value
    label: str
    index: int  # 0-based position in the script; hand-off and ended keep the index they interrupted
    count: int  # number of scripted stages (10)


class Listener(Model):
    user_id: str
    name: str
    mode: Literal["listening", "took_over"]


class HandoffInfo(Model):
    id: str
    call_id: str
    reason: Literal[
        "caller_asked",
        "urgent_safety",
        "distress",
        "low_confidence",
        "identity_unverified",
        "tool_failed",
        "consent_refused",
        "supervisor",
    ]
    reason_label: str  # "Caller asked for a person"
    detail: str
    priority: Literal["urgent", "high", "normal"]
    state: Literal["waiting", "accepted", "completed", "returned_to_line", "callback_offered"]
    requested_at: datetime
    waiting_seconds: int
    accepted_by: PersonRef | None
    accepted_at: datetime | None
    caller_label: str  # "Amélie Tremblay" or "Unverified caller"
    loss_type_label: str | None
    language: Lang


class LastLine(Model):
    speaker: Speaker
    text: str  # redacted, at most 140 characters


class LiveLine(Model):
    """One row of the switchboard. The client derives the duration from `answeredAt` and X-ClaimVoice-Now."""

    call_id: str
    line_label: str  # "Line 3"
    state: LineState
    state_label: str
    stage: StageInfo
    mode: CallMode
    language: Lang
    caller_label: str
    caller_verified: bool
    caller_phone_masked: str | None
    region: str | None
    region_label: str | None
    loss_type: str | None
    loss_type_label: str | None
    answered_at: datetime
    flags: list[Flag]
    sentiment: Sentiment
    handoff: HandoffInfo | None
    listeners: list[Listener]
    in_surge: bool
    last_line: LastLine | None
    claim_file_progress: float  # 0..1 share of required fields filled
    is_sample: bool


class CallSummary(Model):
    id: str
    reference: str  # "CV-260108-0042"
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    state: LineState
    state_label: str
    mode: CallMode
    language: Lang
    caller_label: str
    region_label: str | None
    loss_type_label: str | None
    outcome: Literal["claim_created", "handed_off", "abandoned", "no_claim", "in_progress"]
    outcome_label: str
    claim_id: str | None
    claim_number: str | None
    flags: list[Flag]
    qa_score: float | None
    is_sample: bool


class Consent(Model):
    rule: Literal["one_party", "all_party"]
    rule_label: str  # "All-party consent (California)"
    region: str
    answer: Literal["given", "refused", "not_required", "pending"]
    answer_label: str
    recording: bool
    asked_at: datetime | None
    turn_id: str | None


class CallDetail(CallSummary):
    stage: StageInfo
    stages: list[StageInfo]  # the scripted path, for the progress rail
    consent: Consent
    policy_id: str | None
    policy_number: str | None
    holder_id: str | None
    handoff: HandoffInfo | None
    listeners: list[Listener]
    summary: str | None  # in the call's language
    summary_en: str | None
    recording_available: bool
    surge_id: str | None


class Turn(Model):
    id: str
    seq: int
    speaker: Speaker
    speaker_label: str  # "Caller", "ClaimVoice", "Dana Whitford (supervisor)"
    text: str  # redacted
    language: Lang
    at_ms: int  # offset from answer, for recording sync
    end_ms: int
    stage: str
    confidence: float | None
    interrupted: bool
    redactions: int
    flags: list[FlagKind]


class Transcript(Model):
    call_id: str
    language: Lang
    retained: bool  # False when consent was refused: turns is empty and `notice` explains
    notice: str | None
    turns: list[Turn]


class SlotHistory(Model):
    value: Any
    display: str
    source: Literal["heard", "policy_record", "tool", "person"]
    changed_by: str | None  # person name for edits after the call
    at: datetime
    span: TextSpan | None
    note: str | None


class Slot(Model):
    key: str
    label: str
    value: Any
    display: str  # how it reads ("Tuesday 6 January, about 4 pm")
    confidence: float | None
    confidence_label: Literal["sure", "likely", "check"] | None  # ≥0.85 / ≥0.6 / below
    source: Literal["heard", "policy_record", "tool", "person"]
    source_label: str  # "Heard on the call", "From the policy", "Looked up", "Edited by Dana Whitford"
    span: TextSpan | None  # link into the transcript (null for policy_record and tool values)
    confirmed: bool  # confirmed by the caller at read-back
    required: bool
    history: list[SlotHistory]


class ClaimFileSection(Model):
    key: Literal["caller", "policy", "loss", "details", "safety", "photos", "coverage", "next_steps"]
    label: str
    slots: list[Slot]


class ClaimFile(Model):
    call_id: str
    claim_id: str | None
    loss_type: str | None
    loss_type_label: str | None
    progress: float  # required fields filled, 0..1
    missing: list[str]  # labels of required fields still empty
    sections: list[ClaimFileSection]


class CallEvent(Model):
    id: str
    at: datetime
    at_ms: int
    kind: Literal[
        "answered",
        "consent",
        "stage",
        "tool",
        "flag",
        "handoff",
        "listen",
        "whisper",
        "takeover",
        "returned",
        "photo_link",
        "notice",
        "ended",
    ]
    label: str  # plain words: "Policy found in 0.2 s", "Dana Whitford started listening"
    actor: str | None
    data: dict[str, Any]


class StartCallIn(Model):
    mode: CallMode = "browser_speech"
    language: Lang | Literal["auto"] = "auto"
    caller_phone: str | None = None  # demo only: where the photo link is "texted" (fake SMS)
    region: str | None = None  # demo picker: "CA-AB" | "US-CO" | "CA-QC" | "US-CA" ...
    scenario: str | None = None  # scripted demo caller ("calgary-hail", "denver-rear-end", "montreal-basement")


class IceServer(Model):
    urls: list[str]
    username: str | None = None
    credential: str | None = None


class ConnectInfo(Model):
    call_id: str
    caller_token: str  # bearer for this call's caller-leg endpoints; expires when the call ends (max 30 min)
    offer_url: str  # POST: SDP offer -> answer
    ice_url: str  # PATCH: trickle ICE candidates
    websocket_url: str  # fallback transport (same JSON messages; binary frames = PCM16 16 kHz mono)
    data_channel_label: str  # "claimvoice"
    ice_servers: list[IceServer]
    max_seconds: int


class StartCallOut(Model):
    call: CallDetail
    connect: ConnectInfo


class HandoffIn(Model):
    note: str | None = None


class WhisperIn(Model):
    text: str  # ≤ 280 characters; never spoken to the caller


class WhisperOut(Model):
    id: str
    at: datetime


class SayIn(Model):
    text: str  # typed take-over: spoken to the caller as the person


class HangupIn(Model):
    reason: Literal["completed", "caller_request", "duplicate", "prank_or_test", "transferred", "other"]
    note: str | None = None


class ListenOut(Model):
    mode: Literal["audio", "transcript"]  # transcript when the call carries no server audio (browser_speech/typed)
    connect: ConnectInfo | None  # audio: a receive-only WebRTC leg


class SmsMessage(Model):
    id: str
    to_masked: str
    body: str  # the demo org shows the photo link here, so the demo can open it
    sent_at: datetime
    status: Literal["queued", "sent", "failed"]
