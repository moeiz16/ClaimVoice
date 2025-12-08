"""Routing checks: features, synthetic data, rules, reasons, the committed models and the registry."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from claimvoice.contracts import TriageInput, TriageScorer
from claimvoice.ml import synth
from claimvoice.ml.features import (
    EXCLUDED,
    FRAUD_FEATURES,
    PROTECTED_FOR_TESTING_ONLY,
    SEVERITY_FEATURES,
    SIGNS,
    age_band,
    build_features,
    sign_text,
    signs_present,
)
from claimvoice.ml.metrics import ece, psi, status_for_psi
from claimvoice.ml.reasons import phrase, top_reasons
from claimvoice.ml.registry import load_models, load_registry
from claimvoice.ml.routing import decide
from claimvoice.ml.scorer import get_triage_scorer

POLICY = {
    "line": "property",
    "region": "CA-AB",
    "status": "active",
    "effective_from": "2019-12-01",
    "coverage_changed_at": None,
    "deductible": 1000,
    "coverage_limit": 650000,
    "prior_claims_36m": 0,
}
DANA = {
    "loss_type": "wind",
    "loss_date": "2026-01-08",
    "loss_time": "02:10",
    "roof_or_window_damage": True,
    "open_to_weather": False,
    "mitigation_taken": True,
    "home_livable": True,
    "damage_areas": "skylight",
    "injury_reported": False,
    "photos_promised": True,
}
CALL = {"facts": {"answered_at": "2026-01-08T09:14:00+00:00", "weather_confirms_loss": True, "surge_event_match": True}}


def test_no_protected_attribute_or_proxy_is_a_model_input():
    banned = set(PROTECTED_FOR_TESTING_ONLY) | {"postal_code", "date_of_birth", "caller_name", "age"}
    assert not banned & set(SEVERITY_FEATURES) and not banned & set(FRAUD_FEATURES)
    assert {"voice_features", "language", "region"} <= set(EXCLUDED)
    feats = build_features(DANA, POLICY, {**CALL, "region": "CA-QC", "language": "fr"})
    assert "region" not in feats and "language" not in feats


def test_features_from_a_claim_file():
    f = build_features(DANA, POLICY, CALL)
    assert f["loss_wind"] == 1 and f["roof_or_window_opening"] == 0 and f["damage_area_count"] == 1
    assert 0 < f["hours_loss_to_report"] < 1  # called within minutes
    assert f["days_policy_start_to_loss"] == (date(2026, 1, 8) - date(2019, 12, 1)).days
    assert f["weather_contradicts_loss"] == 0 and f["policy_not_in_force"] == 0


def test_the_fourteen_signs_and_their_words():
    f = build_features(
        {"loss_type": "collision", "loss_date": "2026-01-07", "caller_relationship": "other"},
        {**POLICY, "line": "auto", "effective_from": "2025-12-19", "coverage_changed_at": "2025-12-29"},
        {"facts": {"payment_pressure": True, "answered_at": "2026-01-08T13:47:00+00:00"}},
    )
    present = {s.key for s in signs_present(f)}
    assert present == {"new_policy", "coverage_raised", "third_party_pressure"}
    assert len(SIGNS) == 14
    texts = [sign_text(s, f, "en") for s in signs_present(f)]
    assert "Policy started 19 days before the loss" in texts


def test_age_bands_are_for_fairness_only():
    assert age_band(date(1990, 5, 1), date(2026, 1, 8)) == "35_64"
    assert age_band(date(1958, 10, 3), date(2026, 1, 8)) == "65_plus"
    assert age_band(date(2000, 1, 1), date(2026, 1, 8)) == "under_35"


def test_synthetic_records_are_reproducible_and_patterns_independent_of_groups():
    a = synth.generate(1500, seed=3)
    b = synth.generate(1500, seed=3)
    assert a["fraud"].tolist() == b["fraud"].tolist() and a["cost"].tolist() == b["cost"].tolist()
    rates = a.assign(signed=a["patterns"] != "").groupby("region")["signed"].mean()
    assert rates.max() - rates.min() < 0.08
    parts = synth.time_split(synth.generate(3000, seed=5))
    assert parts["train"]["loss_date"].max() < parts["valid"]["loss_date"].min()
    assert parts["valid"]["loss_date"].max() < parts["test"]["loss_date"].min()


def test_rules_always_win():
    f = build_features(DANA, POLICY, CALL)
    assert decide(f, 0.01, 0.0, size_threshold=0.1, fraud_threshold=0.5).route == "fast_track"
    assert decide(f, 0.01, 0.0, size_threshold=0.1, fraud_threshold=0.5, urgent_safety=True).route == "adjuster"
    hurt = {**f, "injury_reported": 1.0}
    r = decide(hurt, 0.01, 0.0, size_threshold=0.1, fraud_threshold=0.5)
    assert r.route == "adjuster" and "injury" in r.rules
    open_home = {**f, "roof_or_window_opening": 1.0}
    assert decide(open_home, 0.01, 0.0, size_threshold=0.1, fraud_threshold=0.5).route == "adjuster"
    # a high closer-look score with fewer than two signs never refers
    assert decide(f, 0.01, 0.99, size_threshold=0.1, fraud_threshold=0.5).route == "fast_track"
    assert decide(f, 0.01, 0.0, size_threshold=0.1, fraud_threshold=0.5, fast_track_paused=True).route == "adjuster"


def test_reasons_are_plain_sentences():
    assert phrase("hours_loss_to_report", 11 * 24, True)[0] == "Reported 11 days after the loss"
    assert phrase("days_policy_start_to_loss", 6 * 365 + 40, False)[0] == "Policy active 6 years"
    assert phrase("roof_or_window_opening", 0, False) == (
        "Nothing is open to the weather",
        "Rien n'est ouvert aux intempéries",
    )
    picked = top_reasons(
        {"deductible": 0.9, "rooms_affected": 0.5, "injury_reported": 0.3},
        {"deductible": 500, "rooms_affected": 0, "injury_reported": 1},
    )
    assert [p[0] for p in picked] == ["injury_reported"]


def test_metrics():
    y = np.array([0, 0, 1, 1])
    assert ece(y, np.array([0.0, 0.0, 1.0, 1.0])) == 0
    rng = np.random.default_rng(1)
    ref = rng.normal(0, 1, 5000)
    assert psi(ref, rng.normal(0, 1, 5000)) < 0.05
    assert psi(ref, rng.normal(1.5, 1, 5000)) > 0.25
    assert [status_for_psi(x) for x in (0.05, 0.15, 0.3)] == ["stable", "watch", "act"]


def test_committed_registry_has_three_versions_and_passing_gates_in_use():
    reg = load_registry()
    for key in ("size", "closer_look"):
        check = reg["checks"][key]
        stages = {v["version"]: v["stage"] for v in check["versions"]}
        assert stages == {4: "retired", 5: "in_use", 6: "candidate"}
        in_use = next(v for v in check["versions"] if v["stage"] == "in_use")
        assert in_use["gatesPassed"], [g for g in in_use["gates"] if not g["passed"]]
        assert {s["key"] for s in check["factSheet"]["sections"]} >= {"for", "never_looks_at", "fairness", "technical"}
        assert len(check["drift"]["weeks"]) == 8
    assert "denies a claim" in reg["never"]
    assert set(load_models()) == {"size", "closer_look"}


@pytest.fixture(scope="module")
def scorer():
    return get_triage_scorer()


def test_scorer_satisfies_the_protocol_and_routes_the_landing_call(scorer):
    assert isinstance(scorer, TriageScorer)
    d = scorer.score(TriageInput("c1", "o1", "property", "wind", build_features(DANA, POLICY, CALL)))
    assert d.route == "fast_track" and not d.siu_referral and d.severity_band == "small"
    assert len(d.reasons) == 3 and all(r.text["en"] and r.text["fr"] for r in d.reasons)
    assert d.settle_low < d.settle_high and d.signs_checked == 14
    assert d.model_versions == {"size": "5", "closer_look": "5"}


def test_scorer_refers_the_tomas_claim_for_a_person_to_review(scorer):
    f = build_features(
        {
            "loss_type": "collision",
            "loss_date": "2026-01-07",
            "loss_time": "17:52",
            "caller_relationship": "other",
            "other_party_involved": True,
            "police_report_filed": True,
            "vehicle_drivable": True,
        },
        {
            **POLICY,
            "line": "auto",
            "effective_from": "2025-12-19",
            "coverage_changed_at": "2025-12-29",
            "deductible": 250,
        },
        {"facts": {"payment_pressure": True, "answered_at": "2026-01-08T13:47:00+00:00"}},
    )
    d = scorer.score(TriageInput("c2", "o1", "auto", "collision", f))
    assert d.route == "special_investigation" and d.siu_referral
    assert {s.feature for s in d.fraud_indicators} >= {"new_policy", "coverage_raised", "third_party_pressure"}
    assert any("special investigations is asked to review" in r for r in d.rules_applied)


def test_injury_and_urgent_safety_are_never_fast_tracked(scorer):
    hurt = build_features({**DANA, "injury_reported": True}, POLICY, CALL)
    assert scorer.score(TriageInput("c3", "o1", "property", "wind", hurt)).route == "adjuster"
    urgent = {**build_features(DANA, POLICY, CALL), "urgent_safety": True}
    assert scorer.score(TriageInput("c4", "o1", "property", "wind", urgent)).route == "adjuster"


def test_scoring_ignores_fairness_groups(scorer):
    f = build_features(DANA, POLICY, CALL)
    a = scorer.score(TriageInput("c5", "o1", "property", "wind", f, {"region": "CA-AB", "language": "en"}))
    b = scorer.score(
        TriageInput("c5", "o1", "property", "wind", f, {"region": "CA-QC", "language": "fr", "age_band": "65_plus"})
    )
    assert (a.route, a.severity_probability, a.fraud_score) == (b.route, b.severity_probability, b.fraud_score)
