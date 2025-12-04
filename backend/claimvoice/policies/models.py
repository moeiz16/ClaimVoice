"""Policyholders, policies, coverages and insured items (docs/API_CONTRACT.md Part 2)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claimvoice import clock
from claimvoice.platform.db import ID, Base, new_id


class Policyholder(Base):
    """A person who holds policies. Date of birth is only used for identity checks and fairness age bands."""

    __tablename__ = "policyholders"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone_e164: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    date_of_birth: Mapped[date] = mapped_column()
    postal_code: Mapped[str] = mapped_column(String(12))
    city: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(8))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    customer_since: Mapped[date] = mapped_column()
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)

    policies: Mapped[list[Policy]] = relationship(back_populates="holder")


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("org_id", "policy_number", name="uq_policies_org_number"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    policy_number: Mapped[str] = mapped_column(String(24))
    holder_id: Mapped[str] = mapped_column(ID, ForeignKey("policyholders.id", ondelete="CASCADE"), index=True)
    line: Mapped[str] = mapped_column(String(16))  # auto | property
    product: Mapped[str] = mapped_column(String(40))  # auto_plus | home_comprehensive | home_standard | condo
    region: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | lapsed | cancelled
    effective_from: Mapped[date] = mapped_column()
    effective_to: Mapped[date] = mapped_column()
    premium: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    coverage_changed_at: Mapped[date | None] = mapped_column(default=None)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)

    holder: Mapped[Policyholder] = relationship(back_populates="policies")
    coverages: Mapped[list[Coverage]] = relationship(cascade="all, delete-orphan", order_by="Coverage.position")
    items: Mapped[list[InsuredItem]] = relationship(cascade="all, delete-orphan")


class Coverage(Base):
    __tablename__ = "coverages"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    policy_id: Mapped[str] = mapped_column(ID, ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    key: Mapped[str] = mapped_column(String(40))
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    limit: Mapped[float | None] = mapped_column(Float, default=None)
    deductible: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)


class InsuredItem(Base):
    __tablename__ = "insured_items"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    policy_id: Mapped[str] = mapped_column(ID, ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # vehicle | property
    label: Mapped[str] = mapped_column(String(160))
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=clock.now)
