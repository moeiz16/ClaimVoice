"""`TriageScorer` (docs/API_CONTRACT.md Part 3 and Part 6): the two routing checks at hang-up.

Loads the committed boosters and calibration (`ml/artifacts/`), scores a frozen `TriageInput`, applies the fixed
rules (which always win), and explains the result in plain words from exact TreeSHAP contributions. Pure and fast
(about a millisecond): the platform calls it inline when a call closes. Never an automatic denial: a closer-look
referral is a request for a person to review.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any

import numpy as np

from claimvoice.contracts import Reason, RoutingDecision, TriageInput
from claimvoice.ml.features import (
    FEATURE_SLOT,
    FEATURE_SOURCE,
    FRAUD_FEATURES,
    SEVERITY_FEATURES,
    SIGNS,
    sign_text,
    signs_present,
)
from claimvoice.ml.reasons import top_reasons
from claimvoice.ml.registry import ARTIFACTS, IN_USE, load_models, load_registry
from claimvoice.ml.routing import RULE_TEXT, decide

ROUTE_LABELS = {"fast_track": "Fast-track", "adjuster": "Adjuster", "special_investigation": "Closer look"}


@dataclass
class _Check:
    key: str
    version: int
    features: tuple[str, ...]
    booster: Any
    cal_x: np.ndarray
    cal_y: np.ndarray
    threshold: float
    settle: Mapping[str, Mapping[str, list[float]]]

    def raw_and_contribs(self, values: Mapping[str, float]) -> tuple[float, np.ndarray]:
        import xgboost as xgb

        row = np.array([[float(values.get(f, 0.0) or 0.0) for f in self.features]], dtype=float)
        d = xgb.DMatrix(row, feature_names=list(self.features))
        raw = float(self.booster.predict(d)[0])
        contribs = np.asarray(self.booster.predict(d, pred_contribs=True))[0]
        return raw, contribs

    def calibrate(self, raw: float) -> float:
        return float(np.interp(raw, self.cal_x, self.cal_y))


def _load_check(key: str, version: int) -> _Check:
    import xgboost as xgb

    entry = load_models()[key][str(version)]
    booster = xgb.Booster()
    booster.load_model(str(ARTIFACTS / entry["booster"]))
    booster.set_param({"nthread": 1})
    return _Check(
        key,
        version,
        tuple(entry["features"]),
        booster,
        np.asarray(entry["calibration"]["x"], dtype=float),
        np.asarray(entry["calibration"]["y"], dtype=float),
        float(entry["threshold"]),
        entry.get("settle", {}),
    )


def _fast_track_paused(check: str) -> bool:
    try:
        weeks = load_registry()["checks"][check]["drift"]["weeks"]
    except (KeyError, FileNotFoundError):
        return False
    return bool(weeks) and weeks[-1]["status"] == "act"


class XgbTriageScorer:
    """The size check and the closer-look check, with the routing rules."""

    def __init__(self, versions: Mapping[str, int] | None = None) -> None:
        versions = dict(versions or {"size": IN_USE, "closer_look": IN_USE})
        self.size = _load_check("size", versions["size"])
        self.closer = _load_check("closer_look", versions["closer_look"])
        self.paused = _fast_track_paused("size")

    def probabilities(self, features: Mapping[str, float]) -> tuple[float, float]:
        return (
            self.size.calibrate(self.size.raw_and_contribs(features)[0]),
            self.closer.calibrate(self.closer.raw_and_contribs(features)[0]),
        )

    def score(self, item: TriageInput) -> RoutingDecision:
        f = {
            k: (float(v) if isinstance(v, int | float | bool) else 0.0)
            for k, v in item.features.items()
            if v is not None
        }
        for key in (*SEVERITY_FEATURES, *FRAUD_FEATURES):
            f.setdefault(key, 0.0)
        raw_s, contrib_s = self.size.raw_and_contribs(f)
        raw_f, contrib_f = self.closer.raw_and_contribs(f)
        p_size, p_fraud = self.size.calibrate(raw_s), self.closer.calibrate(raw_f)
        urgent = bool(item.features.get("urgent_safety"))
        result = decide(
            f,
            p_size,
            p_fraud,
            size_threshold=self.size.threshold,
            fraud_threshold=self.closer.threshold,
            urgent_safety=urgent,
            fast_track_paused=self.paused,
        )
        # reasons: the strongest pushes in the direction of the route
        if result.route == "special_investigation":
            contrib = dict(zip(self.closer.features, contrib_f[:-1], strict=True))
            picked = top_reasons(contrib, f, k=3, direction="raises")
        else:
            contrib = dict(zip(self.size.features, contrib_s[:-1], strict=True))
            direction = "lowers" if result.route == "fast_track" else "raises"
            picked = top_reasons(contrib, f, k=3, direction=direction)
            if len(picked) < 3:
                more = [r for r in top_reasons(contrib, f, k=6) if r[0] not in {p[0] for p in picked}]
                picked += more[: 3 - len(picked)]
        total = sum(abs(c) for c in contrib.values()) or 1.0
        reasons = [
            Reason(
                feature,
                {"en": en, "fr": fr},
                "raises" if c > 0 else "lowers",
                round(abs(c) / total, 4),
                FEATURE_SLOT.get(feature),
                FEATURE_SOURCE.get(feature, "call"),
            )
            for feature, c, en, fr in picked
        ]
        fraud_contrib = dict(zip(self.closer.features, contrib_f[:-1], strict=True))
        ftotal = sum(abs(c) for c in fraud_contrib.values()) or 1.0
        signs = [
            Reason(
                s.key,
                {"en": sign_text(s, f, "en"), "fr": sign_text(s, f, "fr")},
                "raises",
                round(abs(fraud_contrib.get(s.feature, 0.0)) / ftotal, 4),
                FEATURE_SLOT.get(s.feature),
                FEATURE_SOURCE.get(s.feature, "call"),
            )
            for s in signs_present(f)
        ]
        band = "small" if p_size < 0.2 else ("moderate" if p_size < 0.5 else "large")
        loss_type = next(
            (t for t in ("collision", "hail", "wind", "water", "fire", "theft") if f.get(f"loss_{t}")), item.loss_type
        )
        lo, hi = self.size.settle.get(loss_type, {}).get(band, [0.0, 0.0])
        t_f = self.closer.threshold
        fraud_band = "high" if p_fraud >= t_f else ("elevated" if p_fraud >= t_f / 2 else "low")
        currency = str(
            item.features.get("currency") or ("USD" if str(item.features.get("region", "")).startswith("US") else "CAD")
        )
        return RoutingDecision(
            route=result.route,
            severity_probability=round(p_size, 4),
            severity_band=band,
            fraud_score=round(p_fraud, 4),
            fraud_band=fraud_band,
            siu_referral=result.siu_referral,
            reasons=tuple(reasons),
            fraud_indicators=tuple(signs),
            rules_applied=tuple(RULE_TEXT[r]["en"] for r in result.rules),
            model_versions={"size": str(self.size.version), "closer_look": str(self.closer.version)},
            settle_low=float(lo),
            settle_high=float(hi),
            currency=currency if currency in ("CAD", "USD") else "CAD",
            signs_checked=len(SIGNS),
            thresholds={"size": self.size.threshold, "closer_look": self.closer.threshold},
        )


@cache
def get_triage_scorer(size_version: int = IN_USE, closer_version: int = IN_USE) -> XgbTriageScorer:
    """The process-wide scorer for the versions in use (the platform passes others after a promotion)."""
    return XgbTriageScorer({"size": size_version, "closer_look": closer_version})


def route_label(route: str) -> str:
    return ROUTE_LABELS.get(route, route)
