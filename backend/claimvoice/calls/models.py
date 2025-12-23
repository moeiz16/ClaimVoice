"""Calls and everything heard on them: turns (including staff-only whisper rows), claim-file values with their
transcript spans, the timeline, hand-offs, texts, photo links, quality scores and surges (docs/API_CONTRACT.md Part 2).

Rows are written only by the platform: `SqlCallSink` while a call is live, the closing task at hang-up, the HTTP
handlers for supervisor actions and the seed."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from claimvoice import clock
from claimvoice.platform.db import ID, Base, new_id


class Surge(Base):
    """A catastrophe event that raises call volume in an area (the line desk's surge ribbon)."""

    __tablename__ = "surges"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # hail | flood | wind | winter_storm | rainfall | wildfire
    loss_type: Mapped[str] = mapped_column(String(20))  # the script whose surge questions switch on
    region: Mapped[str] = mapped_column(String(8))
    area_label: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160))
    headline: Mapped[str] = mapped_column(String(240))
    alert_id: Mapped[str | None] = mapped_column(String(80), default=None)
    source: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column()
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    usual_calls_per_hour: Mapped[float] = mapped_column(Float, default=4.0)
    surge_questions_on: Mapped[bool] = mapped_column(Boolean, default=False)
    standby_available: Mapped[int] = mapped_column(Integer, default=0)
    standby_called_at: Mapped[datetime | None] = mapped_column(default=None)
    wait_for_person_seconds: Mapped[int] = mapped_column(Integer, default=60)
    guidance: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        UniqueConstraint("org_id", "reference", name="uq_calls_org_reference"),
        Index("ix_calls_org_state", "org_id", "state"),
        Index("ix_calls_org_answered", "org_id", "answered_at"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    reference: Mapped[str] = mapped_column(String(24))  # CALL-260108-042
    line_number: Mapped[int | None] = mapped_column(Integer, default=None)  # "Line 3" while live
    mode: Mapped[str] = mapped_column(String(16), default="browser_speech")
    channel: Mapped[str] = mapped_column(String(16), default="browser")  # browser | demo_line | test | phone
    language: Mapped[str] = mapped_column(String(5), default="en")
    state: Mapped[str] = mapped_column(String(24), default="ringing")
    stage: Mapped[str] = mapped_column(String(24), default="greeting")
    stage_index: Mapped[int] = mapped_column(Integer, default=0)
    resume_stage: Mapped[str | None] = mapped_column(String(24), default=None)
    answered_at: Mapped[datetime] = mapped_column(default=clock.now)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    end_reason: Mapped[str | None] = mapped_column(String(32), default=None)
    caller_phone_e164: Mapped[str | None] = mapped_column(String(20), default=None)
    caller_name: Mapped[str | None] = mapped_column(String(160), default=None)
    caller_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    region: Mapped[str | None] = mapped_column(String(8), default=None)
    place: Mapped[str | None] = mapped_column(String(120), default=None)
    loss_type: Mapped[str | None] = mapped_column(String(20), default=None)
    policy_id: Mapped[str | None] = mapped_column(ID, ForeignKey("policies.id", ondelete="SET NULL"), default=None)
    holder_id: Mapped[str | None] = mapped_column(ID, ForeignKey("policyholders.id", ondelete="SET NULL"), default=None)
    consent: Mapped[dict[str, Any]] = mapped_column(default=dict)
    recording_path: Mapped[str | None] = mapped_column(String(200), default=None)
    recording_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    summary_en: Mapped[str | None] = mapped_column(Text, default=None)
    outcome: Mapped[str] = mapped_column(String(20), default="in_progress")
    surge_id: Mapped[str | None] = mapped_column(ID, ForeignKey("surges.id", ondelete="SET NULL"), default=None)
    scenario: Mapped[str | None] = mapped_column(String(40), default=None)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public_demo: Mapped[bool] = mapped_column(Boolean, default=False)  # landing-page call: nothing kept
    latency_p95_ms: Mapped[float | None] = mapped_column(Float, default=None)
    # Live view state, kept on the row so the line desk is one query: flags, mood, heard pills, last question,
    # listeners and the actions the line already took.
    flags: Mapped[list[Any]] = mapped_column(default=list)
    mood: Mapped[dict[str, Any]] = mapped_column(default=dict)
    heard: Mapped[list[Any]] = mapped_column(default=list)
    last_asked: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    listeners: Mapped[list[Any]] = mapped_column(default=list)
    caller_token_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    started_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    claim_number: Mapped[str | None] = mapped_column(String(20), default=None)  # reserved before wrap-up speaks it
    # Call-level facts for the routing checks that are not claim-file values (a third party pushing for payment,
    # whether weather records match the loss). Never personal data.
    facts: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class CallTurn(Base):
    """One final turn. `id` is the voice runtime's turn id. Whisper rows (speaker `whisper`) are staff-only."""

    __tablename__ = "call_turns"
    __table_args__ = (Index("ix_call_turns_call_seq", "call_id", "seq"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(10))  # caller | line | person | system | whisper
    speaker_name: Mapped[str | None] = mapped_column(String(160), default=None)
    text: Mapped[str] = mapped_column(Text)  # already redacted
    text_en: Mapped[str | None] = mapped_column(Text, default=None)  # English line under French turns (staff view)
    language: Mapped[str] = mapped_column(String(5), default="en")
    at_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    redactions: Mapped[int] = mapped_column(Integer, default=0)
    retained: Mapped[bool] = mapped_column(Boolean, default=True)
    flags: Mapped[list[Any]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class CallSlot(Base):
    """A claim-file value. The current value per key is the latest row with `superseded_at` empty."""

    __tablename__ = "call_slots"
    __table_args__ = (Index("ix_call_slots_call_key", "call_id", "key"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(40))
    value: Mapped[Any] = mapped_column(JSON, default=None)
    display: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    source: Mapped[str] = mapped_column(String(16))  # heard | policy_record | tool | person
    turn_id: Mapped[str | None] = mapped_column(ID, default=None)  # no FK: purged turns leave the value
    span_start: Mapped[int | None] = mapped_column(Integer, default=None)
    span_end: Mapped[int | None] = mapped_column(Integer, default=None)
    at_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    corrects: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_at: Mapped[datetime | None] = mapped_column(default=None)
    changed_by: Mapped[str | None] = mapped_column(String(160), default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class CallEvent(Base):
    """The call timeline (answered, consent, stage, tool, flag, hand-off, listen, whisper, take-over, ...)."""

    __tablename__ = "call_events"
    __table_args__ = (Index("ix_call_events_call_at", "call_id", "at_ms"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"))
    at: Mapped[datetime] = mapped_column(default=clock.now)
    at_ms: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(240))
    actor_user_id: Mapped[str | None] = mapped_column(ID, default=None)
    actor_label: Mapped[str | None] = mapped_column(String(160), default=None)
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Handoff(Base):
    __tablename__ = "handoffs"
    __table_args__ = (Index("ix_handoffs_org_state", "org_id", "state"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(24))
    detail: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(8))  # urgent | high | normal
    state: Mapped[str] = mapped_column(String(20), default="waiting")
    requested_at: Mapped[datetime] = mapped_column(default=clock.now)
    accepted_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    accepted_at: Mapped[datetime | None] = mapped_column(default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
    summary: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[list[Any]] = mapped_column(default=list)
    to_user_id: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    team: Mapped[str | None] = mapped_column(String(16), default=None)


class Whisper(Base):
    """A typed note from a supervisor that the line acts on at its next turn. The caller never hears it."""

    __tablename__ = "whispers"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    author_name: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(String(280))
    at: Mapped[datetime] = mapped_column(default=clock.now)
    at_ms: Mapped[int] = mapped_column(Integer, default=0)
    acted_on_turn_id: Mapped[str | None] = mapped_column(ID, default=None)


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    to_e164: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="sent")
    sent_at: Mapped[datetime] = mapped_column(default=clock.now)
    provider_id: Mapped[str | None] = mapped_column(String(64), default=None)


class PhotoLink(Base):
    """A texted link for the caller to send photos (`/p/{token}`); only the token's HMAC is stored."""

    __tablename__ = "photo_links"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ID, ForeignKey("claims.id", ondelete="SET NULL"), default=None)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column()  # business time (72 h after the text), like the claim
    max_photos: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class QaScoreRow(Base):
    __tablename__ = "qa_scores"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(ID, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(16))  # needs_review | reviewed | auto_passed
    reason_queued: Mapped[str | None] = mapped_column(String(200), default=None)
    items: Mapped[list[Any]] = mapped_column(default=list)
    beads: Mapped[list[Any]] = mapped_column(default=list)
    focus: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    scorer_version: Mapped[str] = mapped_column(String(40))
    scored_at: Mapped[datetime] = mapped_column(default=clock.now)
    reviewed_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    review: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    coaching_note: Mapped[str | None] = mapped_column(Text, default=None)
