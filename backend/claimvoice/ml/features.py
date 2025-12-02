"""Feature contract for the routing models (docs/API_CONTRACT.md §6.2). Training, scoring and drift all import this."""

from __future__ import annotations

# Never model inputs. Used only to compute fairness gaps (eval and the fairness endpoint).
PROTECTED_FOR_TESTING_ONLY: tuple[str, ...] = ("region", "language", "age_band")

# Explicitly excluded from every model, with the reason recorded in the model card.
EXCLUDED: dict[str, str] = {
    "voice_features": "No voice stress, accent, speech-rate or pitch features: unreliable and discriminatory.",
    "postal_code": "Proxy for protected characteristics; region-level effects are tested for, not learned.",
    "date_of_birth": "Age is used only to form age bands for fairness testing.",
    "caller_name": "Identity is not evidence.",
}

SEVERITY_FEATURES: tuple[str, ...] = (
    "line",  # auto | property
    "loss_type",
    "injury_reported",
    "other_party_involved",
    "police_report_filed",
    "vehicle_drivable",
    "water_still_entering",
    "roof_or_window_opening",  # the building is open to the weather (roof hole, smashed skylight)
    "rooms_affected",
    "caller_damage_estimate_band",  # 0 none given, 1 < $2k, 2 $2-10k, 3 $10-50k, 4 > $50k
    "vehicle_age_years",
    "deductible",
    "coverage_limit",
    "surge_event_match",
    "weather_confirms_loss",
    "photos_promised",
    "description_words",
    "hours_loss_to_report",
)

FRAUD_FEATURES: tuple[str, ...] = (
    "loss_type",
    "days_policy_start_to_loss",
    "days_coverage_change_to_loss",
    "hours_loss_to_report",
    "prior_claims_36m",
    "key_fact_corrections",  # corrections to date, place or sequence of events during the call
    "weather_contradicts_loss",  # e.g. storm damage reported where no storm was recorded
    "police_report_filed",
    "theft_without_police_report",
    "round_number_estimate",
    "third_party_caller",
    "caller_damage_estimate_band",
    "photos_declined",
    "night_loss_no_witness",
)

ROUTES: tuple[str, ...] = ("fast_track", "adjuster", "special_investigation")
