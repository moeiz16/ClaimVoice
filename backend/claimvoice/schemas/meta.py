"""§1.13 reference data for labels and pickers (GET /meta)."""

from __future__ import annotations

from claimvoice.schemas.base import Labeled, Model


class LossTypeInfo(Model):
    key: str
    label: str
    line: str


class RegionInfo(Model):
    code: str
    label: str
    country: str
    consent_rule: str


class Meta(Model):
    product: str
    version: str
    languages: list[Labeled]
    loss_types: list[LossTypeInfo]
    regions: list[RegionInfo]
    stages: list[Labeled]
    routes: list[Labeled]
    roles: list[Labeled]
    demo_scenarios: list[Labeled]
