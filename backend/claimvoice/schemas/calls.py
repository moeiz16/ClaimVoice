"""§1.6 calls: live lines, starting a browser call, transcript, live claim file, hand-off and supervisor actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from claimvoice.schemas.base import Lang, Model, PersonRef, TextSpan

CallMode = Literal["voice", "browser_speech", "typed"]
LineState = Literal["ringing", "with_line", "waiting_for_person", "with_person", "wrapping_up", "ended"]
Speaker = Literal["caller", "line", "person", "system", "whisper"]  # whisper rows are staff-only
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
    step: int  # 1..7 on the script track; hand-off and ended keep the step they interrupted
    step_label: str  # "What happened"
    steps: int  # 7
    next_label: str | None  # "Photos next"


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
    caller_label: str  # "Martine Gagnon" or "Unverified caller"
    line_label: str  # "Line 4"
    place: str | None  # "Airdrie"
    loss_type_label: str | None
    language: Lang
    summary: str  # two lines, so nobody asks the caller twice
    actions_taken: list[str]  # what ClaimVoice already did ("Told him to leave the house and call 911")
    to: PersonRef | None  # a named person, when the hand-off was addressed to someone
    team: Literal["intake", "adjusters", "siu"] | None


class LastAsked(Model):
    text: str  # the line's last question, in the call's language
    text_en: str | None  # English under it for French calls


class Mood(Model):
    """One plain word per line, from what the caller says and how the conversation goes; never a score."""

    key: Literal["calm", "unsettled", "shaken", "upset"]
    label: str  # "Sounds shaken"
    detail: str | None  # "speaking slower", "repeating questions"


class HeardPill(Model):
    """A fact heard on the call, for the strip ("Roof shingles torn off"); caution = amber (e.g. "Sore neck")."""

    key: str
    text: str
    tone: Literal["normal", "caution"]


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
    mood: Mood
    handoff: HandoffInfo | None
    listeners: list[Listener]
    in_surge: bool
    last_asked: LastAsked | None
    place: str | None  # "Saddle Ridge, Calgary"
    heard: list[HeardPill]  # most recent first, at most 4
    claim_file_progress: float  # 0..1 share of required fields filled
    is_sample: bool


class CallSummary(Model):
    id: str
    reference: str  # "CALL-260108-042"
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
    line_label: str | None  # "Line 1" while live
    place: str | None  # "Saddle Ridge, Calgary"
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
    speaker_label: str  # "Caller", "ClaimVoice", "Renée Kowalchuk (supervisor)", "Whisper, ClaimVoice only"
    text: str  # redacted
    text_en: str | None  # English line under French turns for staff; null on English calls
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
    source_label: str  # source chip: "▸ 1:52", "from the policy", "looked up", "edited by Lena Ortiz"
    span: TextSpan | None  # link into the transcript (null for policy_record and tool values)
    heard_at_seconds: float | None  # where it was said on the recording (the ▸ moment)
    changed_at_seconds: float | None  # set when the caller corrected it ("Changed at 3:12")
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
        "identity",
        "stage",
        "tool",
        "flag",
        "handoff",
        "listen",
        "whisper",
        "takeover",
        "returned",
        "photo_link",
        "read_back",
        "notice",
        "ended",
    ]
    label: str  # plain words: "Policy found in 0.2 s", "Renée Kowalchuk started listening"
    actor: str | None
    data: dict[str, Any]


class StartCallIn(Model):
    mode: CallMode = "browser_speech"
    language: Lang | Literal["auto"] = "auto"
    caller_phone: str | None = None  # demo only: where the photo link is "texted" (fake SMS)
    region: str | None = None  # demo picker: "CA-AB" | "US-CO" | "CA-QC" | "US-CA" ...
    scenario: str | None = None  # scripted demo caller ("calgary-windstorm", "denver-rear-end", "montreal-basement")


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
    reason: str  # one line, shown in the tray
    to_user_id: str | None = None  # a person, or
    team: Literal["intake", "adjusters", "siu"] | None = None  # a team (default intake)


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


class TakeoverOut(Model):
    call: CallDetail
    connect: ConnectInfo | None  # send-receive leg: the person's microphone reaches the caller; null = typed only


class SmsMessage(Model):
    id: str
    to_masked: str
    body: str  # the demo org shows the photo link here, so the demo can open it
    sent_at: datetime
    status: Literal["queued", "sent", "failed"]


class HandoffAcceptOut(Model):
    """POST /calls/{id}/handoff/accept: the hand-off, now yours, and the leg to join the caller."""

    handoff: HandoffInfo
    listen: ListenOut
