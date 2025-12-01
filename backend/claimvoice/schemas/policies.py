"""§1.5 policies and policyholders."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from claimvoice.schemas.base import Lang, Model

Line = Literal["auto", "property"]


class Coverage(Model):
    key: str  # "collision", "comprehensive", "liability", "sewer_backup", "overland_water", "dwelling", ...
    label: str
    included: bool
    limit: float | None
    deductible: float | None
    currency: Literal["CAD", "USD"]


class InsuredItem(Model):
    id: str
    kind: Literal["vehicle", "property"]
    label: str  # "2021 Toyota RAV4" / "Detached home, 14 Saddleback Rd NE"
    details: dict[str, Any]  # vehicle: year, make, model, vinLast6, plate; property: address, type, yearBuilt


class PolicySummary(Model):
    id: str
    policy_number: str
    holder_id: str
    holder_name: str
    line: Line
    line_label: str  # "Auto" / "Home"
    product_label: str  # "Auto Plus", "Homeowners Comprehensive"
    region: str
    region_label: str
    status: Literal["active", "lapsed", "cancelled"]
    status_label: str
    effective_from: date
    effective_to: date
    open_claims: int


class Policy(PolicySummary):
    coverages: list[Coverage]
    insured_items: list[InsuredItem]
    premium: float
    currency: Literal["CAD", "USD"]
    coverage_changed_at: date | None
    recent_claims: list[dict[str, Any]]  # ClaimSummary (claims.py), kept loose here to avoid a cycle
    is_sample: bool


class PolicyholderSummary(Model):
    id: str
    full_name: str
    phone_masked: str
    email_masked: str | None
    city: str
    region: str
    region_label: str
    preferred_language: Lang
    policies: int
    claims_36m: int


class Policyholder(PolicyholderSummary):
    postal_code_masked: str  # "T3J •••"
    customer_since: date
    policy_list: list[PolicySummary]
    claims: list[dict[str, Any]]  # ClaimSummary
    created_at: datetime
