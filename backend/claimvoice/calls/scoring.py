"""The two scorers the platform runs at hang-up, behind the contract interfaces (docs/API_CONTRACT.md Part 3):
`TriageScorer` (the size and closer-look routing checks, `claimvoice.ml.scorer`) and `CallScorer` (call quality,
`claimvoice.qa.scorer`).

When the trained scorers are not importable (a stripped-down checkout), a rules-only stand-in that follows the same
contract keeps calls closing; it applies the fixed routing rules of Part 6.1 and never decides a claim."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from claimvoice import contracts
from claimvoice.ml.features import FRAUD_FEATURES, SEVERITY_FEATURES
from claimvoice.qa.rubric import GOOD_AT, NEEDS_ATTENTION_AT, RUBRIC

# ---------------------------------------------------------------- feature input


def build_features(
    claim_file: Mapping[str, Any], policy: Mapping[str, Any], call: Mapping[str, Any]
) -> dict[str, float | int | str | bool | None]:
    """The model inputs, through the routing checks' own feature builder when available."""
    try:
        from claimvoice.ml.features import build_features as ml_build  # type: ignore[attr-defined,unused-ignore]
    except ImportError:
        return _basic_features(claim_file, policy, call)
    return dict(ml_build(claim_file, policy, call))


def _days(a: str | date | None, b: str | date | None) -> int | None:
    if not a or not b:
        return None
    da = a if isinstance(a, date) else date.fromisoformat(str(a)[:10])
    db = b if isinstance(b, date) else date.fromisoformat(str(b)[:10])
    return (db - da).days


def _basic_features(
    claim_file: Mapping[str, Any], policy: Mapping[str, Any], call: Mapping[str, Any]
) -> dict[str, Any]:
    f = claim_file
    band = {"under_2k": 1, "2k_10k": 2, "10k_50k": 3, "over_50k": 4}.get(str(f.get("caller_damage_estimate_band")), 0)
    loss_date = f.get("loss_date")
    reported = str(call.get("answered_at") or "")[:10] or None
    hours = (_days(loss_date, reported) or 0) * 24
    out: dict[str, Any] = {
        "line": policy.get("line"),
        "loss_type": f.get("loss_type"),
        "injury_reported": bool(f.get("injury_reported")),
        "other_party_involved": bool(f.get("other_party_involved")),
        "police_report_filed": bool(f.get("police_report_filed")),
        "vehicle_drivable": f.get("vehicle_drivable"),
        "water_still_entering": bool(f.get("water_still_entering")),
        "roof_or_window_opening": bool(f.get("open_to_weather")),
        "rooms_affected": int(f.get("rooms_affected") or 0),
        "caller_damage_estimate_band": band,
        "vehicle_age_years": policy.get("vehicle_age_years"),
        "deductible": policy.get("deductible"),
        "coverage_limit": policy.get("coverage_limit"),
        "surge_event_match": bool(call.get("surge_match")),
        "weather_confirms_loss": call.get("weather_confirms"),
        "photos_promised": bool(f.get("photos_promised")),
        "description_words": len(str(f.get("loss_description") or "").split()),
        "hours_loss_to_report": hours,
        "days_policy_start_to_loss": _days(policy.get("effective_from"), loss_date),
        "days_coverage_change_to_loss": _days(policy.get("coverage_changed_at"), loss_date),
        "prior_claims_36m": int(policy.get("prior_claims_36m") or 0),
        "key_fact_corrections": int(call.get("key_fact_corrections") or 0),
        "weather_contradicts_loss": bool(call.get("weather_contradicts")),
        "theft_without_police_report": f.get("loss_type") == "theft" and not f.get("police_report_filed"),
        "round_number_estimate": bool(call.get("round_number_estimate")),
        "third_party_caller": bool(call.get("third_party_pressure")),
        "photos_declined": bool(call.get("photos_declined")),
        "night_loss_no_witness": bool(call.get("night_loss_no_witness")),
    }
    return {k: out.get(k) for k in dict.fromkeys(SEVERITY_FEATURES + FRAUD_FEATURES)}


# ---------------------------------------------------------------- rules-only stand-ins


def _num(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


class RulesTriage:
    """Fixed rules only (Part 6.1); probabilities are rough and labelled as such in `model_versions`."""

    def score(self, item: contracts.TriageInput) -> contracts.RoutingDecision:
        f = item.features
        signs: list[contracts.Reason] = []

        def sign(key: str, en: str, fr: str, source: str = "policy") -> None:
            signs.append(contracts.Reason(key, {"en": en, "fr": fr}, "raises", 0.3, None, source))

        days_start = f.get("days_policy_start_to_loss")
        if isinstance(days_start, int) and 0 <= days_start <= 30:
            sign(
                "days_policy_start_to_loss",
                f"Policy started {days_start} days before the loss",
                f"Police en vigueur {days_start} jours avant le sinistre",
            )
        days_change = f.get("days_coverage_change_to_loss")
        if isinstance(days_change, int) and 0 <= days_change <= 45:
            sign(
                "days_coverage_change_to_loss",
                "Coverage was raised shortly before the loss",
                "Couverture augmentée peu avant le sinistre",
            )
        if f.get("third_party_caller"):
            sign(
                "third_party_caller",
                "Someone else pushed for a fast payment",
                "Un tiers a insisté pour un paiement rapide",
                "call",
            )
        if _num(f.get("prior_claims_36m")) >= 3:
            sign(
                "prior_claims_36m",
                "Three or more claims in 36 months",
                "Trois réclamations ou plus en 36 mois",
                "claim_history",
            )
        if f.get("theft_without_police_report"):
            sign("theft_without_police_report", "Theft with no police report", "Vol sans rapport de police", "call")
        fraud = min(0.95, 0.03 + 0.2 * len(signs))
        size = 0.15
        reasons: list[contracts.Reason] = []
        rules: list[str] = []
        if f.get("injury_reported"):
            size += 0.4
            reasons.append(
                contracts.Reason(
                    "injury_reported",
                    {"en": "A possible injury was reported", "fr": "Une blessure possible a été signalée"},
                    "raises",
                    0.5,
                    "injury_reported",
                    "call",
                )
            )
        if f.get("water_still_entering") or f.get("roof_or_window_opening"):
            size += 0.3
            reasons.append(
                contracts.Reason(
                    "roof_or_window_opening",
                    {"en": "The home is open to the weather", "fr": "Le logement est exposé aux intempéries"},
                    "raises",
                    0.3,
                    "open_to_weather",
                    "call",
                )
            )
        if _num(f.get("caller_damage_estimate_band")) >= 3:
            size += 0.25
        size = min(size, 0.95)
        if not reasons:
            reasons.append(
                contracts.Reason(
                    "loss_type",
                    {"en": "A common, simple loss", "fr": "Un sinistre simple et courant"},
                    "lowers",
                    0.4,
                    "loss_type",
                    "call",
                )
            )
        route = "fast_track"
        if size >= 0.5:
            route = "adjuster"
        if f.get("injury_reported"):
            rules.append("A possible injury is never fast-tracked")
            route = "adjuster" if route == "fast_track" else route
        siu = fraud >= 0.35 and len(signs) >= 2
        if siu:
            route = "special_investigation"
        band = "large" if size >= 0.7 else "moderate" if size >= 0.4 else "small"
        return contracts.RoutingDecision(
            route=route,
            severity_probability=size,
            severity_band=band,
            fraud_score=fraud,
            fraud_band="high" if fraud >= 0.5 else "elevated" if fraud >= 0.2 else "low",
            siu_referral=siu,
            reasons=reasons[:3],
            fraud_indicators=signs,
            rules_applied=rules,
            model_versions={"size": "rules", "closer_look": "rules"},
            settle_low={"small": 1500, "moderate": 4000, "large": 12000}[band],
            settle_high={"small": 4000, "moderate": 9000, "large": 40000}[band],
            currency=str(f.get("currency") or "CAD"),
        )


class RulesQa:
    """Rubric rules only, for checkouts without the quality scorer."""

    def score(
        self,
        turns: Sequence[contracts.TurnRecord],
        events: Sequence[Mapping[str, Any]],
        slots: Mapping[str, contracts.SlotRecord],
    ) -> contracts.QaResult:
        kinds = [e.get("kind") for e in events]
        items = []
        for r in RUBRIC:
            passed: bool | None = True
            if r.key == "consent_first":
                passed = "consent" in kinds
            elif r.key == "identity_verified":
                passed = "policy_number" in slots
            elif r.key == "safety_check":
                passed = "injury_reported" in slots
            elif r.key == "no_card_numbers":
                passed = all("[card number removed]" in t.text or not re.search(r"\d{13,19}", t.text) for t in turns)
            items.append(contracts.QaItemResult(r.key, passed, r.points if passed else 0, r.points, [], "", "rule"))
        score = sum(i.points for i in items)
        failed_critical = any(i.passed is False and next(r for r in RUBRIC if r.key == i.key).critical for i in items)
        band = (
            "failed"
            if failed_critical or score < NEEDS_ATTENTION_AT
            else "good"
            if score >= GOOD_AT
            else "needs_attention"
        )
        return contracts.QaResult(score, band, items, band != "good", "rules-1")


# ---------------------------------------------------------------- access


@lru_cache(maxsize=1)
def triage_scorer() -> contracts.TriageScorer:
    try:
        from claimvoice.ml.scorer import get_triage_scorer
    except ImportError:
        return RulesTriage()
    return get_triage_scorer()


@lru_cache(maxsize=1)
def call_scorer() -> contracts.CallScorer:
    try:
        from claimvoice.qa.scorer import get_call_scorer
    except ImportError:
        return RulesQa()
    return get_call_scorer()


def iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None
