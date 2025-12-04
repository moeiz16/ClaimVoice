"""Claims, their photos, routing decisions, closer-look referrals, and the routing-check registry with its sign-offs
(docs/API_CONTRACT.md Part 2)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from claimvoice import clock
from claimvoice.platform.db import ID, Base, new_id


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("org_id", "claim_number", name="uq_claims_org_number"),
        Index("ix_claims_org_reported", "org_id", "reported_at"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    claim_number: Mapped[str] = mapped_column(String(20))  # CV-26-01842
    call_id: Mapped[str | None] = mapped_column(ID, ForeignKey("calls.id", ondelete="SET NULL"), default=None)
    policy_id: Mapped[str] = mapped_column(ID, ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    holder_id: Mapped[str] = mapped_column(ID, ForeignKey("policyholders.id", ondelete="CASCADE"), index=True)
    line: Mapped[str] = mapped_column(String(16))
    loss_type: Mapped[str] = mapped_column(String(20))
    loss_date: Mapped[date | None] = mapped_column(default=None)
    loss_place: Mapped[str | None] = mapped_column(String(120), default=None)
    description: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(24), default="new")
    assigned_to: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    urgent_safety: Mapped[bool] = mapped_column(Boolean, default=False)
    surge_id: Mapped[str | None] = mapped_column(ID, ForeignKey("surges.id", ondelete="SET NULL"), default=None)
    language: Mapped[str] = mapped_column(String(5), default="en")
    reported_at: Mapped[datetime] = mapped_column(default=clock.now)
    in_short: Mapped[dict[str, Any]] = mapped_column(default=dict)  # {text, links[], checkedBy, checkedAt}
    next_steps: Mapped[list[Any]] = mapped_column(default=list)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class ClaimPhoto(Base):
    __tablename__ = "claim_photos"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    # Photos texted during the call arrive before the claim exists; the claim adopts them at hang-up.
    claim_id: Mapped[str | None] = mapped_column(ID, ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str | None] = mapped_column(ID, ForeignKey("calls.id", ondelete="SET NULL"), index=True)
    path: Mapped[str] = mapped_column(String(200))  # relative to UPLOADS_DIR
    thumbnail_path: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(40), default="image/jpeg")
    caption: Mapped[str | None] = mapped_column(String(280), default=None)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="text_link")
    received_at: Mapped[datetime] = mapped_column(default=clock.now)


class RoutingDecisionRow(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(ID, ForeignKey("claims.id", ondelete="CASCADE"), unique=True)
    route: Mapped[str] = mapped_column(String(24))  # effective route (override wins)
    model_route: Mapped[str] = mapped_column(String(24))
    decided_at: Mapped[datetime] = mapped_column(default=clock.now)
    accepted_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    accepted_at: Mapped[datetime | None] = mapped_column(default=None)
    settle_low: Mapped[float] = mapped_column(Float, default=0)
    settle_high: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    severity_probability: Mapped[float] = mapped_column(Float)
    severity_band: Mapped[str] = mapped_column(String(12))  # small | moderate | large
    fraud_score: Mapped[float] = mapped_column(Float)
    fraud_band: Mapped[str] = mapped_column(String(12))  # low | elevated | high
    signs_checked: Mapped[int] = mapped_column(Integer, default=14)
    reasons: Mapped[list[Any]] = mapped_column(default=list)
    fraud_indicators: Mapped[list[Any]] = mapped_column(default=list)
    rules_applied: Mapped[list[Any]] = mapped_column(default=list)
    model_versions: Mapped[dict[str, Any]] = mapped_column(default=dict)
    features: Mapped[dict[str, Any]] = mapped_column(default=dict)  # input snapshot (drift and audit)
    fairness_groups: Mapped[dict[str, Any]] = mapped_column(default=dict)  # testing only, never a model input
    override_route: Mapped[str | None] = mapped_column(String(24), default=None)
    override_reason: Mapped[str | None] = mapped_column(Text, default=None)
    override_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    override_at: Mapped[datetime | None] = mapped_column(default=None)


class SiuReferral(Base):
    """A request for review by special investigations. Never a finding of fraud and never a denial."""

    __tablename__ = "siu_referrals"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(ID, ForeignKey("claims.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="open")
    score: Mapped[float] = mapped_column(Float)
    indicators: Mapped[list[Any]] = mapped_column(default=list)
    opened_at: Mapped[datetime] = mapped_column(default=clock.now)
    decided_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)


class ModelVersion(Base):
    """The routing-check registry mirror the API reads (trained runs live in MLflow)."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("org_id", "check_key", "version", name="uq_model_versions_org_check_version"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    check_key: Mapped[str] = mapped_column(String(16))  # size | closer_look
    version: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(12))  # in_use | candidate | retired
    algorithm: Mapped[str] = mapped_column(String(80))
    trained_on: Mapped[str] = mapped_column(String(240), default="")
    metrics: Mapped[dict[str, Any]] = mapped_column(default=dict)
    gates: Mapped[list[Any]] = mapped_column(default=list)
    fact_sheet: Mapped[dict[str, Any]] = mapped_column(default=dict)  # sections, technical, fairness, drift
    trained_by: Mapped[str | None] = mapped_column(String(160), default=None)
    in_use_since: Mapped[date | None] = mapped_column(default=None)
    retired_at: Mapped[datetime | None] = mapped_column(default=None)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class CheckSignoff(Base):
    __tablename__ = "check_signoffs"
    __table_args__ = (UniqueConstraint("model_version_id", "side", name="uq_check_signoffs_version_side"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    model_version_id: Mapped[str] = mapped_column(ID, ForeignKey("model_versions.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String(12))  # claims | model_risk
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id", ondelete="CASCADE"))
    note: Mapped[str] = mapped_column(Text, default="")
    signed_at: Mapped[datetime] = mapped_column(default=clock.now)
