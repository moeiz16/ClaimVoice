"""§1.10 routing checks: the size check (severity) and the closer-look check (fraud indicators), their fact sheets,
the four questions a regulator asks, fairness, drift and two sign-offs per version.

Check keys: `size` (decides fast-track or adjuster) and `closer_look` (should special investigations look; never
denies). Technical metrics are kept for the fact sheet's "for the technical reviewer" fold."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from claimvoice.schemas.base import Model, PersonRef

CheckKey = Literal["size", "closer_look"]
Stage = Literal["in_use", "candidate", "retired"]
Status = Literal["healthy", "watch", "act"]  # "Working as expected ✓" / "Watch: storm week ◷" / "Act ⚠"


class MetricSet(Model):
    auc: float
    pr_auc: float
    brier: float
    ece: float  # expected calibration error (10 bins)
    recall_at_threshold: float | None = None
    precision_at_threshold: float | None = None
    threshold: float | None = None


class GateResult(Model):
    key: str  # "beats_baseline", "calibrated", "fair", "reasons_stable", "inputs_stable"
    label: str  # "Fair across groups"
    passed: bool
    value: float
    limit: float


class SignOff(Model):
    side: Literal["claims", "model_risk"]  # claims: a claims supervisor; model_risk: compliance
    side_label: str  # "Claims", "Model risk"
    by: PersonRef | None
    at: datetime | None
    note: str | None
    state: Literal["signed", "waiting"]


class CheckVersion(Model):
    version: int
    stage: Stage
    algorithm: str  # fold only: "Gradient-boosted trees (XGBoost)"
    in_use_since: date | None
    trained_on: str  # "4,820 synthetic claim calls + French motor claim costs (freMTPL2)"
    metrics: MetricSet  # fold only
    gates: list[GateResult]
    gates_passed: bool
    sign_offs: list[SignOff]  # always two: claims and model_risk


class Check(Model):
    """A wide card on the Routing checks page."""

    key: CheckKey
    name: str  # "Size check" / "Closer-look check"
    question: str  # "How big is this claim likely to be?"
    decides: str  # "Decides fast-track or adjuster." / "Asks special investigations to look. Never denies."
    in_use: CheckVersion
    candidate: CheckVersion | None
    status: Status
    status_label: str
    signed_by: PersonRef | None  # last sign-off on the version in use


class Bar(Model):
    label: str  # "Size check", "Old rule of thumb"
    value: float  # frequency 0..1, shown "96 in 100"
    ours: bool  # orchid; comparison bars are faint grey


class Dot(Model):
    dimension: Literal["region", "language", "age_band"]
    group: str
    label: str  # "Québec", "French", "65 and over"
    rate: float
    count: int
    within_band: bool


class WeekColumn(Model):
    label: str  # "Week of 5 Jan"
    psi: float
    status: Literal["stable", "watch", "act"]  # < 0.10, 0.10-0.25, > 0.25


class CompareRow(Model):
    key: Literal["right", "investigators_agreed", "fair", "reasons_same"]
    label: str  # "Fast-track right"
    in_use: str  # "96 in 100"
    candidate: str
    better: bool | None


class Question(Model):
    """One of the four questions, answered in a sentence with one chart under it."""

    key: Literal["right", "fair", "like_learned", "replace"]
    question: str  # "How often is it right?"
    answer: str  # plain sentence; **double asterisks** mark the emphasised phrase
    foot: str
    bars: list[Bar] | None = None  # right
    dots: list[Dot] | None = None  # fair
    overall_rate: float | None = None  # fair: the overall line
    band: float | None = None  # fair: allowed band around it (±0.015 = ±1.5 points)
    weeks: list[WeekColumn] | None = None  # like_learned (8 weeks; watch 0.10, act 0.25)
    compare: list[CompareRow] | None = None  # replace
    sign_offs: list[SignOff] | None = None  # replace


class RoutingChecks(Model):
    """GET /routing-checks: the whole page."""

    caption: str  # "Two checks run when a call ends. A person can change any route. Reviewed monthly; ..."
    checks: list[Check]
    questions: list[Question]
    never: list[str]  # "denies a claim", "uses age, gender, language or postcode to route", ...


class FactSection(Model):
    key: Literal[
        "for", "not_for", "looks_at", "never_looks_at", "tested", "limits", "fairness", "sign_offs", "technical"
    ]
    title: str
    body: list[str]  # paragraphs / bullet lines, plain words


class CurvePoint(Model):
    x: float
    y: float


class CalibrationBin(Model):
    predicted: float
    observed: float
    count: int


class Technical(Model):
    """The fact sheet's fold for technical reviewers."""

    test: MetricSet
    baseline: MetricSet  # logistic regression
    random_forest: MetricSet | None
    roc: list[CurvePoint]
    pr: list[CurvePoint]
    calibration: list[CalibrationBin]
    split: str  # "Time split: trained on losses before 1 Oct 2025, tested on Oct-Dec 2025"
    features: list[str]  # plain names


class FactSheet(Model):
    """GET /routing-checks/{check}: the model card in plain language."""

    key: CheckKey
    name: str
    version: int
    sections: list[FactSection]
    technical: Technical
    versions: list[CheckVersion]


class FairnessRow(Model):
    dimension: Literal["region", "language", "age_band"]
    group: str
    label: str
    count: int
    flagged_rate: float
    true_positive_rate: float | None
    false_positive_rate: float | None
    gap: float  # vs the overall rate, absolute
    within_band: bool


class Fairness(Model):
    key: CheckKey
    version: int
    overall_rate: float
    band: float
    passed: bool
    rows: list[FairnessRow]
    note: str  # "Age, language and region are never used to route a claim. We use them only here, to check fairness."


class SignOffIn(Model):
    version: int
    note: str  # the sign-off statement recorded in the audit trail
