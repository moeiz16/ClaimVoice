"""Scripts per loss type (versioned) and recording-consent rules per state or province. Hand-off rules, languages,
retention and the privacy officer are small and live in `organizations.settings` (`settings.service`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from claimvoice import clock
from claimvoice.platform.db import ID, Base, new_id


class ScriptVersion(Base):
    """The latest version per loss type is the active script; a live call keeps the version it started with."""

    __tablename__ = "scripts"
    __table_args__ = (UniqueConstraint("org_id", "loss_type", "version", name="uq_scripts_org_loss_version"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    loss_type: Mapped[str] = mapped_column(String(20))
    line: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer)
    questions: Mapped[list[Any]] = mapped_column(default=list)  # ScriptQuestion dicts (camelCase), incl. surgeOnly
    updated_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class ConsentRuleRow(Base):
    __tablename__ = "consent_rules"
    __table_args__ = (UniqueConstraint("org_id", "region", name="uq_consent_rules_org_region"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    region: Mapped[str] = mapped_column(String(8))
    rule: Mapped[str] = mapped_column(String(12))  # one_party | all_party
    announcement: Mapped[dict[str, Any]] = mapped_column(default=dict)  # {en, fr}
    basis: Mapped[str] = mapped_column(String(240))
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id", ondelete="SET NULL"), default=None)
    updated_at: Mapped[datetime] = mapped_column(default=clock.now)
    note: Mapped[str | None] = mapped_column(Text, default=None)
