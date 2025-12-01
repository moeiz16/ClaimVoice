"""§1.10 models: registry, cards, metrics, fairness, drift, champion/challenger."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from claimvoice.schemas.base import Model, PersonRef

ModelKey = Literal["severity", "fraud"]
Stage = Literal["champion", "challenger", "archived"]


class MetricSet(Model):
    auc: float
    pr_auc: float
    brier: float
    ece: float  # expected calibration error (10 bins)
    recall_at_threshold: float | None = None
    precision_at_threshold: float | None = None
    threshold: float | None = None


class GateResult(Model):
    key: str  # "beats_baseline_pr_auc", "ece_max", "fairness_gap_max", "shap_stability_min", "psi_max"
    label: str
    passed: bool
    value: float
    limit: float


class ModelVersionSummary(Model):
    version: str
    stage: Stage
    algorithm: str  # "Gradient-boosted trees (XGBoost)", "Logistic regression (baseline)", "Random forest"
    metrics: MetricSet
    gates_passed: bool
    trained_on: str  # "4,820 synthetic intake records + freMTPL2 severity" (no run timestamps)
    promoted_by: PersonRef | None
    promoted_at: datetime | None


class ModelInfo(Model):
    key: ModelKey
    name: str  # "Claim routing (severity and complexity)" / "Fraud indicators for special investigations"
    purpose: str
    champion: ModelVersionSummary
    challenger: ModelVersionSummary | None
    baseline: MetricSet
    status: Literal["healthy", "watch", "action_needed"]
    status_label: str


class CurvePoint(Model):
    x: float
    y: float


class CalibrationBin(Model):
    predicted: float
    observed: float
    count: int


class ModelMetrics(Model):
    key: ModelKey
    version: str
    test: MetricSet
    baseline: MetricSet
    random_forest: MetricSet | None
    roc: list[CurvePoint]
    pr: list[CurvePoint]
    calibration: list[CalibrationBin]
    split: str  # "Time split: trained on losses before 1 Oct 2025, tested on Oct-Dec 2025"
    gates: list[GateResult]


class CardSection(Model):
    key: Literal[
        "intended_use",
        "not_for",
        "data",
        "features",
        "excluded",
        "metrics",
        "fairness",
        "limitations",
        "oversight",
        "versions",
    ]
    title: str
    body: list[str]  # paragraphs / bullet lines, plain words


class ModelCard(Model):
    key: ModelKey
    version: str
    title: str
    sections: list[CardSection]


class FairnessRow(Model):
    dimension: Literal["region", "language", "age_band"]
    group: str
    label: str  # "Quebec", "French", "65 and over"
    count: int
    flagged_rate: float  # share routed to adjuster/SIU (severity) or referred (fraud)
    true_positive_rate: float | None
    false_positive_rate: float | None
    gap: float  # vs the reference group, absolute
    within_limit: bool


class Fairness(Model):
    key: ModelKey
    version: str
    max_gap: float
    passed: bool
    rows: list[FairnessRow]
    note: str  # "Groups are used only for this test; they are never model inputs."


class DriftRow(Model):
    feature: str
    label: str
    psi: float
    status: Literal["stable", "watch", "drifted"]  # < 0.1, 0.1-0.25, > 0.25


class PerformancePoint(Model):
    period_label: str  # "Week of 5 Jan"
    claims: int
    auc: float | None  # null until outcomes are known
    flagged_rate: float


class Drift(Model):
    key: ModelKey
    version: str
    reference_label: str
    current_label: str
    score_psi: float
    features: list[DriftRow]
    performance: list[PerformancePoint]


class Comparison(Model):
    key: ModelKey
    champion: ModelVersionSummary
    challenger: ModelVersionSummary | None
    gates: list[GateResult]
    can_promote: bool


class PromoteIn(Model):
    version: str
    note: str  # required: the sign-off statement recorded in the audit trail
