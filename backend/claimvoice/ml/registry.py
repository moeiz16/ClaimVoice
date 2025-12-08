"""The committed model registry: what the API reads for Routing checks and what the scorer loads.

Files in `ml/artifacts/` (no run timestamps, no pickles):
* `{check}_v{n}.json`: XGBoost boosters for the version in use and the candidate;
* `models.json`: per check and version, the features, the isotonic calibration points, the threshold, and for the
  size check the typical settlement ranges;
* `registry.json`: versions, metrics, gates, fact sheets, fairness rows, drift weeks and the four questions, in the
  camelCase shapes of `schemas/ml.py` (sign-offs are people, so the platform adds them).

MLflow (local SQLite + `mlruns/`, git-ignored) keeps the full run history; this registry is the reviewed mirror.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

ARTIFACTS = Path(__file__).parent / "artifacts"
REPO_ROOT = Path(__file__).resolve().parents[3]
IN_USE = 5
CANDIDATE = 6
RETIRED = 4
STAGES = {RETIRED: "retired", IN_USE: "in_use", CANDIDATE: "candidate"}
IN_USE_SINCE = {RETIRED: "2025-06-02", IN_USE: "2025-12-01", CANDIDATE: None}
NAMES = {
    "size": {
        "name": "Size check",
        "question": "How big is this claim likely to be?",
        "decides": "Decides fast-track or adjuster.",
    },
    "closer_look": {
        "name": "Closer-look check",
        "question": "Should someone in special investigations look at it?",
        "decides": "Asks special investigations to look. Never denies.",
    },
}
GATE_LABELS = {
    "beats_baseline": "Better than the simple scorecard",
    "calibrated": "Scores mean what they say",
    "fair": "Fair across groups",
    "reasons_stable": "Reasons stay the same",
    "inputs_stable": "Inputs look like what it learned",
}
NEVER = [
    "denies a claim",
    "uses age, gender, language or postcode to route",
    "stops a person changing the route",
    "changes version without two sign-offs",
]


def _frequency(rate: float) -> str:
    return f"{round(rate * 100)} in 100"


def settle_table(data: Any, size_version: Any) -> dict[str, dict[str, list[float]]]:
    """Typical settlement ranges (25th to 75th percentile of cost, rounded to $500) by loss type and size band."""
    df = data.train.copy()
    df["p"] = size_version.proba(df)
    df["band"] = np.where(df["p"] < 0.2, "small", np.where(df["p"] < 0.5, "moderate", "large"))
    out: dict[str, dict[str, list[float]]] = {}
    for (lt, band), g in df.groupby(["loss_type", "band"]):
        if len(g) < 15:
            continue
        lo, hi = np.quantile(g["cost"], [0.25, 0.75])
        out.setdefault(str(lt), {})[str(band)] = [float(max(250, round(lo / 500) * 500)), float(round(hi / 500) * 500)]
    return out


def _gates(check: str, v: Any, baseline_pr: float, max_psi: float, limits: dict[str, float]) -> list[dict[str, Any]]:
    m = v.metrics
    fair = v.fairness
    stab = v.stability.get("jaccard")
    gates = [
        {
            "key": "beats_baseline",
            "label": GATE_LABELS["beats_baseline"],
            "value": round(m["prAuc"] - baseline_pr, 4),
            "limit": limits["beats_baseline"],
            "passed": m["prAuc"] - baseline_pr >= limits["beats_baseline"],
        },
        {
            "key": "calibrated",
            "label": GATE_LABELS["calibrated"],
            "value": m["ece"],
            "limit": limits["calibrated"],
            "passed": m["ece"] <= limits["calibrated"],
        },
        {
            "key": "fair",
            "label": GATE_LABELS["fair"],
            "value": fair["maxGap"],
            "limit": fair["band"],
            "passed": bool(fair["passed"]),
        },
        {
            "key": "reasons_stable",
            "label": GATE_LABELS["reasons_stable"],
            "value": stab if stab is not None else 0.0,
            "limit": limits["reasons_stable"],
            "passed": stab is not None and stab >= limits["reasons_stable"],
        },
        {
            "key": "inputs_stable",
            "label": GATE_LABELS["inputs_stable"],
            "value": round(max_psi, 4),
            "limit": limits["inputs_stable"],
            "passed": max_psi <= limits["inputs_stable"],
        },
    ]
    return gates


def _version_doc(check: str, v: Any, gates: list[dict[str, Any]]) -> dict[str, Any]:
    m = v.metrics
    return {
        "version": v.version,
        "stage": STAGES[v.version],
        "algorithm": v.algorithm,
        "inUseSince": IN_USE_SINCE[v.version],
        "trainedOn": v.trained_on,
        "split": v.split,
        "metrics": {
            "auc": m["auc"],
            "prAuc": m["prAuc"],
            "brier": m["brier"],
            "ece": m["ece"],
            "recallAtThreshold": m.get("recallAtThreshold"),
            "precisionAtThreshold": m.get("precisionAtThreshold"),
            "threshold": m.get("threshold"),
            "flaggedRate": m.get("flaggedRate"),
        },
        "gates": gates,
        "gatesPassed": all(g["passed"] for g in gates),
        "routes": v.routes_test,
        "stability": v.stability,
    }


def _old_rule_right(data: Any, check: str) -> float:
    """The rule of thumb the checks replaced: fast-track anything without an injury and with one damaged area;
    refer anything with two or more signs."""
    from claimvoice.ml.train import n_signs

    t = data.test
    if check == "size":
        ft = (t["injury_reported"] == 0) & (t["damage_area_count"] <= 1)
        return float((t.loc[ft, "large"] == 0).mean())
    flag = n_signs(t) >= 2
    return float(t.loc[flag, "fraud"].mean()) if flag.any() else 0.0


def _right(v: Any, check: str, data: Any) -> float:
    routes = v.routes_test_series
    t = data.test
    if check == "size":
        ft = routes == "fast_track"
        return float((t.loc[ft, "large"] == 0).mean()) if ft.any() else 0.0
    flag = routes == "special_investigation"
    return float(t.loc[flag, "fraud"].mean()) if flag.any() else 0.0


def write_all(
    versions: dict[str, dict[int, Any]],
    baselines: dict[str, dict[str, Any]],
    report: dict[str, Any],
    drift_by_version: dict[int, dict[str, Any]],
    data: Any,
) -> None:
    from claimvoice.ml import cards
    from claimvoice.ml.features import EXCLUDED, FEATURE_LABELS
    from claimvoice.ml.metrics import calibration_bins, curve, status_for_psi
    from claimvoice.ml.train import GATES, TARGET, route_all

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    models: dict[str, Any] = {}
    reg: dict[str, Any] = {
        "checks": {},
        "never": NEVER,
        "benchmark": report.get("benchmark"),
        "costSource": report.get("costSource"),
    }
    for vnum in (RETIRED, IN_USE, CANDIDATE):
        series = route_all(data.test, versions["size"][vnum], versions["closer_look"][vnum])
        for check in versions:
            versions[check][vnum].__dict__["routes_test_series"] = series
    for check, by_v in versions.items():
        limits = dict(GATES)
        limits_fair = "fair_closer_look" if check == "closer_look" else "fair_fast_track"
        _ = limits_fair
        base_pr = baselines[check]["logistic"]["prAuc"]
        models[check] = {}
        docs = []
        for vnum, v in sorted(by_v.items()):
            weeks = drift_by_version.get(vnum, drift_by_version[IN_USE])["weeks"][check]
            max_psi = max(w["psi"] for w in weeks)
            gates = _gates(check, v, base_pr, max_psi, limits)
            docs.append(_version_doc(check, v, gates))
            if vnum in (IN_USE, CANDIDATE):
                v.booster.save_model(str(ARTIFACTS / f"{check}_v{vnum}.json"))
                entry: dict[str, Any] = {
                    "features": list(v.features),
                    "calibration": {
                        "x": [round(x, 6) for x in v.calibrator.x],
                        "y": [round(y, 6) for y in v.calibrator.y],
                    },
                    "threshold": round(v.threshold, 6),
                    "booster": f"{check}_v{vnum}.json",
                }
                if check == "size":
                    entry["settle"] = settle_table(data, v)
                models[check][str(vnum)] = entry
        v5 = by_v[IN_USE]
        y = data.test[TARGET[check]].to_numpy()
        p = v5.proba(data.test)
        weeks = drift_by_version[IN_USE]["weeks"][check]
        latest = weeks[-1]["status"]
        status = {"stable": "healthy", "watch": "watch", "act": "act"}[latest]
        status_label = {"healthy": "Working as expected", "watch": "Watch: storm week", "act": "Act"}[status]
        right_now, right_old = _right(v5, check, data), _old_rule_right(data, check)
        cand = by_v[CANDIDATE]
        compare = [
            {
                "key": "right",
                "label": "Fast-track right" if check == "size" else "Referrals that found something",
                "inUse": _frequency(right_now),
                "candidate": _frequency(_right(cand, check, data)),
                "better": _right(cand, check, data) >= right_now,
            },
            {
                "key": "investigators_agreed",
                "label": "Found the claims that needed it",
                "inUse": _frequency(v5.metrics.get("recallAtThreshold") or 0),
                "candidate": _frequency(cand.metrics.get("recallAtThreshold") or 0),
                "better": (cand.metrics.get("recallAtThreshold") or 0) >= (v5.metrics.get("recallAtThreshold") or 0),
            },
            {
                "key": "fair",
                "label": "Fair across groups",
                "inUse": "Yes" if v5.fairness["passed"] else "No",
                "candidate": "Yes" if cand.fairness["passed"] else "No",
                "better": None,
            },
            {
                "key": "reasons_same",
                "label": "Reasons stay the same",
                "inUse": _frequency(v5.stability["jaccard"] or 0),
                "candidate": _frequency(cand.stability["jaccard"] or 0),
                "better": (cand.stability["jaccard"] or 0) >= (v5.stability["jaccard"] or 0),
            },
        ]
        fair = v5.fairness
        technical = {
            "test": docs[1]["metrics"] | {"positiveRate": v5.metrics["positiveRate"]},
            "baseline": baselines[check]["logistic"],
            "randomForest": baselines[check]["randomForest"],
            "uncalibrated": report[check]["uncalibrated"],
            "platt": report[check]["platt"],
            "roc": curve(y, p, "roc"),
            "pr": curve(y, p, "pr"),
            "calibration": calibration_bins(y, p),
            "split": v5.split,
            "features": [FEATURE_LABELS.get(f, f) for f in v5.features],
            "params": report[check]["params"],
            "rounds": report[check]["rounds"],
        }
        questions = {
            "right": {
                "bars": [
                    {"label": NAMES[check]["name"], "value": round(right_now, 4), "ours": True},
                    {"label": "Old rule of thumb", "value": round(right_old, 4), "ours": False},
                ],
            },
            "fair": {
                "dots": [
                    {
                        "dimension": r["dimension"],
                        "group": r["group"],
                        "label": r["label"],
                        "rate": r["flaggedRate"],
                        "count": r["count"],
                        "withinBand": r["withinBand"],
                    }
                    for r in fair["rows"]
                ],
                "overallRate": fair["overallRate"],
                "band": fair["band"],
            },
            "likeLearned": {"weeks": weeks},
            "replace": {"compare": compare},
        }
        reg["checks"][check] = {
            **NAMES[check],
            "key": check,
            "status": status,
            "statusLabel": status_label,
            "versions": docs,
            "technical": technical,
            "fairness": {str(vn): by_v[vn].fairness for vn in sorted(by_v)},
            "drift": {
                "weeks": weeks,
                "simulatedShift": drift_by_version[IN_USE]["simulatedShift"][check],
                "statusRule": "Watch at 0.10, act at 0.25 (act pauses fast-track until a person resumes it)",
            },
            "questions": questions,
            "factSheet": cards.fact_sheet(check, v5, technical, fair, EXCLUDED, report),
        }
        _ = status_for_psi
    (ARTIFACTS / "models.json").write_text(json.dumps(models, indent=1) + "\n")
    (ARTIFACTS / "registry.json").write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    cards.write_markdown(reg)
    load_registry.cache_clear()
    load_models.cache_clear()


@cache
def load_registry() -> dict[str, Any]:
    """The registry the API serves (versions, gates, fact sheets, fairness, drift, the four questions)."""
    return json.loads((ARTIFACTS / "registry.json").read_text())


@cache
def load_models() -> dict[str, Any]:
    return json.loads((ARTIFACTS / "models.json").read_text())
