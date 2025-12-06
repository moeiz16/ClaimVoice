"""Feature contract for the routing checks (docs/API_CONTRACT.md §6.2). Training, scoring, drift and the seed all
import this module, so a feature means the same thing everywhere.

`build_features(claim_file, policy, call)` turns what the platform holds at hang-up into the model inputs:
* `claim_file`: {slot_key: value} for the current claim-file values;
* `policy`: {policy_number, line, product, region, status, effective_from, effective_to, coverage_changed_at,
  currency, deductible, coverage_limit, prior_claims_36m, vehicle_age_years};
* `call`: {answered_at, language, region, surge_match, urgent_safety, key_fact_corrections, photos_declined, flags,
  facts}, where `facts` is what the dialogue engine knows that the claim file doesn't (`CallEngine.call_facts()`).

Never inputs: region, language, age band (fairness testing only), postal code, date of birth, names, and anything
derived from the caller's voice (stress, accent, pitch, speech rate).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

# Never model inputs. Used only to compute fairness gaps (eval and the fairness endpoint).
PROTECTED_FOR_TESTING_ONLY: tuple[str, ...] = ("region", "language", "age_band")

# Explicitly excluded from every model, with the reason recorded in the fact sheet.
EXCLUDED: dict[str, str] = {
    "voice_features": "No voice stress, accent, speech-rate or pitch features: unreliable and discriminatory.",
    "postal_code": "Proxy for protected characteristics; region-level effects are tested for, not learned.",
    "date_of_birth": "Age is used only to form age bands for fairness testing.",
    "caller_name": "Identity is not evidence.",
    "language": "The caller's language is tested for fairness, never used to route.",
    "region": "Where the caller lives is tested for fairness, never used to route.",
}

LOSS_TYPES: tuple[str, ...] = ("collision", "hail", "wind", "water", "fire", "theft")

SEVERITY_FEATURES: tuple[str, ...] = (
    "is_auto",
    "loss_collision",
    "loss_hail",
    "loss_wind",
    "loss_water",
    "loss_fire",
    "loss_theft",
    "injury_reported",
    "other_party_involved",
    "police_report_filed",
    "vehicle_not_drivable",
    "airbags_deployed",
    "water_still_entering",
    "roof_or_window_opening",  # the building is open to the weather right now (roof hole, smashed skylight)
    "roof_or_window_damage",
    "siding_or_fence_damage",
    "home_not_livable",
    "rooms_affected",
    "damage_area_count",
    "caller_damage_estimate_band",  # 0 none given, 1 < $2k, 2 $2-10k, 3 $10-50k, 4 > $50k
    "vehicle_age_years",
    "deductible",
    "coverage_limit_log",
    "surge_event_match",
    "weather_confirms_loss",
    "photos_promised",
    "description_words",
    "hours_loss_to_report",
)

FRAUD_FEATURES: tuple[str, ...] = (
    "is_auto",
    "loss_collision",
    "loss_wind",
    "loss_water",
    "loss_theft",
    "loss_fire",
    "days_policy_start_to_loss",
    "days_coverage_change_to_loss",
    "hours_loss_to_report",
    "prior_claims_36m",
    "key_fact_corrections",  # corrections to date, place or sequence of events during the call
    "weather_contradicts_loss",  # e.g. storm damage reported where no storm was recorded
    "police_report_filed",
    "theft_without_police_report",
    "round_number_estimate",
    "third_party_pressure",  # a caller who isn't the policyholder pushing for a fast payment
    "caller_damage_estimate_band",
    "photos_declined",
    "night_loss_no_witness",
    "policy_not_in_force",
)

ROUTES: tuple[str, ...] = ("fast_track", "adjuster", "special_investigation")

# Plain-words labels for features (fact sheets, "what it looks at").
FEATURE_LABELS: dict[str, str] = {
    "is_auto": "Auto or home policy",
    "loss_collision": "A collision",
    "loss_hail": "Hail",
    "loss_wind": "Wind",
    "loss_water": "Water",
    "loss_fire": "Fire or smoke",
    "loss_theft": "Theft or break-in",
    "injury_reported": "Someone hurt",
    "other_party_involved": "Another party involved",
    "police_report_filed": "Police report",
    "vehicle_not_drivable": "Vehicle can't be driven",
    "airbags_deployed": "Airbags went off",
    "water_still_entering": "Water still coming in",
    "roof_or_window_opening": "Home open to the weather",
    "roof_or_window_damage": "Roof, window or skylight damage",
    "siding_or_fence_damage": "Siding or fence damage",
    "home_not_livable": "Home can't be lived in",
    "rooms_affected": "Rooms affected",
    "damage_area_count": "How many parts are damaged",
    "caller_damage_estimate_band": "Caller's own estimate",
    "vehicle_age_years": "Age of the vehicle",
    "deductible": "Deductible",
    "coverage_limit_log": "Coverage limit",
    "surge_event_match": "Matches an active storm",
    "weather_confirms_loss": "Weather records confirm it",
    "photos_promised": "Photos coming",
    "description_words": "How much the caller described",
    "hours_loss_to_report": "Time from loss to call",
    "days_policy_start_to_loss": "Time since the policy started",
    "days_coverage_change_to_loss": "Time since coverage last changed",
    "prior_claims_36m": "Claims in the last 3 years",
    "key_fact_corrections": "Changes to when, where or what happened",
    "weather_contradicts_loss": "Weather records don't show the storm",
    "theft_without_police_report": "Theft not reported to police",
    "round_number_estimate": "Round-number estimate in the top band",
    "third_party_pressure": "Someone else pushing for a fast payment",
    "photos_declined": "Photos declined",
    "night_loss_no_witness": "Night-time loss with no witness or report",
    "policy_not_in_force": "Policy not in force on the loss date",
}

# Where each feature was heard (the platform links a reason to that slot's turn and moment).
FEATURE_SLOT: dict[str, str] = {
    "injury_reported": "injury_reported",
    "other_party_involved": "other_party_involved",
    "police_report_filed": "police_report_filed",
    "vehicle_not_drivable": "vehicle_drivable",
    "airbags_deployed": "airbags_deployed",
    "water_still_entering": "water_still_entering",
    "roof_or_window_opening": "open_to_weather",
    "roof_or_window_damage": "roof_or_window_damage",
    "siding_or_fence_damage": "siding_or_fence_damage",
    "home_not_livable": "home_livable",
    "rooms_affected": "rooms_affected",
    "damage_area_count": "damage_areas",
    "caller_damage_estimate_band": "caller_damage_estimate_band",
    "photos_promised": "photos_promised",
    "photos_declined": "photos_promised",
    "description_words": "loss_description",
    "hours_loss_to_report": "loss_date",
    "loss_collision": "loss_type",
    "loss_hail": "loss_type",
    "loss_wind": "loss_type",
    "loss_water": "loss_type",
    "loss_fire": "loss_type",
    "loss_theft": "loss_type",
    "key_fact_corrections": "loss_time",
    "theft_without_police_report": "police_report_filed",
    "third_party_pressure": "caller_relationship",
    "night_loss_no_witness": "loss_time",
    "round_number_estimate": "caller_damage_estimate_band",
}
FEATURE_SOURCE: dict[str, str] = {
    "days_policy_start_to_loss": "policy",
    "days_coverage_change_to_loss": "policy",
    "prior_claims_36m": "claim_history",
    "deductible": "policy",
    "coverage_limit_log": "policy",
    "vehicle_age_years": "policy",
    "is_auto": "policy",
    "policy_not_in_force": "policy",
    "surge_event_match": "weather",
    "weather_confirms_loss": "weather",
    "weather_contradicts_loss": "weather",
}

_BANDS = {None: 0, "under_2k": 1, "2k_10k": 2, "10k_50k": 3, "over_50k": 4}
NO_CHANGE_DAYS = 3650.0  # "never changed": far in the past


def _b(v: Any) -> float:
    return 1.0 if v is True or v == "true" else 0.0


def _date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _dt(v: Any) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    try:
        d = datetime.fromisoformat(str(v))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


def build_features(
    claim_file: Mapping[str, Any], policy: Mapping[str, Any], call: Mapping[str, Any]
) -> dict[str, float]:
    """Model inputs for one claim. Every value is a float (booleans as 0/1); unknowns take a neutral value."""
    cf, pol = claim_file, policy
    facts: Mapping[str, Any] = {**(call.get("facts") or {}), **{k: v for k, v in call.items() if k != "facts"}}
    loss_type = str(cf.get("loss_type") or "")
    line = str(pol.get("line") or ("auto" if loss_type == "collision" else "property"))
    loss_day = _date(cf.get("loss_date"))
    answered = _dt(facts.get("answered_at"))
    loss_t = None
    if cf.get("loss_time"):
        try:
            loss_t = time.fromisoformat(str(cf["loss_time"]))
        except ValueError:
            loss_t = None
    if loss_day is not None and answered is not None:
        tz = answered.tzinfo
        when = datetime.combine(loss_day, loss_t or time(12, 0), tz)
        hours = max(0.0, (answered - when).total_seconds() / 3600)
    else:
        hours = 2.0
    start = _date(pol.get("effective_from"))
    changed = _date(pol.get("coverage_changed_at"))
    days_start = float((loss_day - start).days) if loss_day and start else NO_CHANGE_DAYS
    days_change = float((loss_day - changed).days) if loss_day and changed else NO_CHANGE_DAYS
    estimate = _BANDS.get(cf.get("caller_damage_estimate_band"), 0)
    areas = [a for a in str(cf.get("damage_areas") or "").split(",") if a.strip()]
    description = str(cf.get("loss_description") or "")
    police = _b(cf.get("police_report_filed"))
    status = str(pol.get("status") or "active")
    end = _date(pol.get("effective_to"))
    in_force = status == "active" and (start is None or loss_day is None or start <= loss_day)
    if end is not None and loss_day is not None and loss_day > end:
        in_force = False
    weather_confirms = facts.get("weather_confirms_loss")
    storm = loss_type in ("wind", "hail")
    night = loss_t is not None and loss_t.hour < 5
    third_party = cf.get("caller_relationship") == "other" or bool(facts.get("third_party_caller"))
    limit = pol.get("coverage_limit")
    out: dict[str, float] = {
        "is_auto": 1.0 if line == "auto" else 0.0,
        **{f"loss_{t}": 1.0 if loss_type == t else 0.0 for t in LOSS_TYPES},
        "injury_reported": _b(cf.get("injury_reported")),
        "other_party_involved": _b(cf.get("other_party_involved")),
        "police_report_filed": police,
        "vehicle_not_drivable": 1.0 if cf.get("vehicle_drivable") is False else 0.0,
        "airbags_deployed": _b(cf.get("airbags_deployed")),
        "water_still_entering": _b(cf.get("water_still_entering")),
        "roof_or_window_opening": _b(cf.get("open_to_weather")),
        "roof_or_window_damage": _b(cf.get("roof_or_window_damage")),
        "siding_or_fence_damage": _b(cf.get("siding_or_fence_damage")),
        "home_not_livable": 1.0 if cf.get("home_livable") is False else 0.0,
        "rooms_affected": float(cf.get("rooms_affected") or 0),
        "damage_area_count": float(len(areas)),
        "caller_damage_estimate_band": float(estimate),
        "vehicle_age_years": float(pol.get("vehicle_age_years") or 0.0),
        "deductible": float(pol.get("deductible") or 0.0),
        "coverage_limit_log": math.log10(float(limit)) if limit else 0.0,
        "surge_event_match": _b(facts.get("surge_match") if "surge_match" in facts else facts.get("surge_event_match")),
        "weather_confirms_loss": _b(weather_confirms),
        "photos_promised": _b(cf.get("photos_promised")),
        "description_words": float(len(description.split())),
        "hours_loss_to_report": round(hours, 2),
        "days_policy_start_to_loss": days_start,
        "days_coverage_change_to_loss": days_change,
        "prior_claims_36m": float(pol.get("prior_claims_36m") or 0),
        "key_fact_corrections": float(facts.get("key_fact_corrections") or 0),
        "weather_contradicts_loss": 1.0 if storm and weather_confirms is False else 0.0,
        "theft_without_police_report": 1.0 if loss_type == "theft" and not police else 0.0,
        "round_number_estimate": _b(facts.get("round_number_estimate")),
        "third_party_pressure": 1.0 if third_party and facts.get("payment_pressure") else 0.0,
        "photos_declined": 1.0 if facts.get("photos_declined") or cf.get("photos_promised") is False else 0.0,
        "night_loss_no_witness": 1.0
        if night and loss_type in ("theft", "collision", "fire") and not police and cf.get("witnesses") is not True
        else 0.0,
        "policy_not_in_force": 0.0 if in_force else 1.0,
    }
    return out


def age_band(date_of_birth: date | None, on: date) -> str:
    """Fairness testing only."""
    if date_of_birth is None:
        return "35_64"
    age = on.year - date_of_birth.year - ((on.month, on.day) < (date_of_birth.month, date_of_birth.day))
    return "under_35" if age < 35 else ("35_64" if age < 65 else "65_plus")


@dataclass(frozen=True, slots=True)
class Sign:
    """One of the signs the closer-look check reports (never a reason to deny on its own)."""

    key: str
    feature: str
    en: str
    fr: str

    def present(self, f: Mapping[str, float]) -> bool:
        v = f.get(self.feature, 0.0)
        if self.key == "new_policy":
            return v <= 30
        if self.key == "coverage_raised":
            return v <= 45
        if self.key == "late_report":
            return v > 14 * 24
        if self.key == "story_changes":
            return v >= 2
        if self.key == "prior_claims":
            return v >= 3
        if self.key == "high_estimate":
            return v >= 4 and f.get("damage_area_count", 0) <= 2
        return v >= 1


SIGNS: tuple[Sign, ...] = (
    Sign(
        "new_policy",
        "days_policy_start_to_loss",
        "Policy started {days} days before the loss",
        "La police a commencé {days} jours avant le sinistre",
    ),
    Sign(
        "coverage_raised",
        "days_coverage_change_to_loss",
        "Coverage was raised {days} days before the loss",
        "La couverture a été augmentée {days} jours avant le sinistre",
    ),
    Sign(
        "late_report",
        "hours_loss_to_report",
        "Reported {report_days} days after the loss",
        "Déclaré {report_days} jours après le sinistre",
    ),
    Sign(
        "story_changes",
        "key_fact_corrections",
        "The account of what happened changed {n} times",
        "Le récit a changé {n} fois",
    ),
    Sign(
        "weather_contradiction",
        "weather_contradicts_loss",
        "Weather records don't show a storm there",
        "Les relevés météo n'indiquent pas de tempête à cet endroit",
    ),
    Sign(
        "theft_no_report",
        "theft_without_police_report",
        "Theft not reported to the police",
        "Vol non déclaré à la police",
    ),
    Sign(
        "round_estimate",
        "round_number_estimate",
        "A round-number estimate in the top band",
        "Une estimation en chiffre rond dans la tranche la plus élevée",
    ),
    Sign(
        "third_party_pressure",
        "third_party_pressure",
        "Someone other than the policyholder pushed for a fast payment",
        "Une autre personne que l'assuré a insisté pour un paiement rapide",
    ),
    Sign("prior_claims", "prior_claims_36m", "{n} claims in the last 3 years", "{n} réclamations en 3 ans"),
    Sign("photos_declined", "photos_declined", "Declined to send photos", "A refusé d'envoyer des photos"),
    Sign(
        "night_no_witness",
        "night_loss_no_witness",
        "Night-time loss with no witness or police report",
        "Sinistre de nuit sans témoin ni rapport de police",
    ),
    Sign(
        "not_in_force",
        "policy_not_in_force",
        "Policy not in force on the loss date",
        "Police non en vigueur à la date du sinistre",
    ),
    Sign(
        "high_estimate",
        "caller_damage_estimate_band",
        "Estimate over $50,000 for limited damage",
        "Estimation de plus de 50 000 $ pour des dommages limités",
    ),
    Sign(
        "no_police_other_party",
        "other_party_no_report",
        "Another party involved but no police report",
        "Une autre partie en cause, sans rapport de police",
    ),
)


def sign_text(sign: Sign, f: Mapping[str, float], language: str) -> str:
    template = sign.fr if language == "fr" else sign.en
    v = f.get(sign.feature, 0.0)
    return template.format(days=int(v), report_days=int(v // 24), n=int(v))


def signs_present(f: Mapping[str, float]) -> list[Sign]:
    g = dict(f)
    g["other_party_no_report"] = 1.0 if f.get("other_party_involved") and not f.get("police_report_filed") else 0.0
    return [s for s in SIGNS if s.present(g)]
