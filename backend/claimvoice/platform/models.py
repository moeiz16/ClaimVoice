"""Core platform tables (migration 0001). Domain tables (policies, calls, claims, QA, models, settings) are added in
later migrations; docs/API_CONTRACT.md Part 2 lists them. Every tenant-owned row carries `org_id`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claimvoice import clock
from claimvoice.platform.db import ID, Base, new_id


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Edmonton")
    # Regions the insurer writes business in: ISO 3166-2 codes such as "CA-AB", "CA-QC", "US-CO".
    regions: Mapped[list[Any]] = mapped_column(default=list)
    languages: Mapped[list[Any]] = mapped_column(default=lambda: ["en"])
    # Small org-wide settings (hand-off rules, retention, privacy officer). Scripts and consent rules get own tables.
    settings: Mapped[dict[str, Any]] = mapped_column(default=dict)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)

    memberships: Mapped[list[Membership]] = relationship(back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-case
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")  # "en" | "fr"
    avatar_color: Mapped[str] = mapped_column(String(16), default="slate")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)

    memberships: Mapped[list[Membership]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # claimvoice.platform.permissions.Role
    title: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)

    org: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Session(Base):
    """Server-side session. The cookie holds a random token; only its HMAC is stored. Expiry uses the real clock."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active_org_id: Mapped[str | None] = mapped_column(ID, ForeignKey("organizations.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=clock.real_now)
    last_seen_at: Mapped[datetime] = mapped_column(default=clock.real_now)
    expires_at: Mapped[datetime] = mapped_column()
    absolute_expires_at: Mapped[datetime] = mapped_column()
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(300), default=None)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=clock.now)
    expires_at: Mapped[datetime] = mapped_column()  # real clock (security timer)
    accepted_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class AuditEvent(Base):
    """Append-only, hash-chained per organisation (claimvoice.platform.audit). Never updated or deleted, including by
    retention jobs: retention removes recordings and transcripts, and writes an audit event saying so."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("org_id", "seq", name="uq_audit_events_org_seq"),
        Index("ix_audit_events_org_at", "org_id", "at"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str | None] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(default=clock.now)
    actor_user_id: Mapped[str | None] = mapped_column(ID, default=None)
    actor_label: Mapped[str] = mapped_column(String(160))  # "Dana Whitford" or "ClaimVoice line" or "System"
    action: Mapped[str] = mapped_column(String(64))  # e.g. "call.takeover", "claim.route_override"
    target_type: Mapped[str | None] = mapped_column(String(40), default=None)
    target_id: Mapped[str | None] = mapped_column(String(64), default=None)
    summary: Mapped[str] = mapped_column(Text)  # plain words, shown as-is in the audit view
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
