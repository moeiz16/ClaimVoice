"""Re-check the committed routing checks from their artifacts (used by `make eval` and the tests).

Nothing is retrained except what the gates require: the logistic baseline (to compare against) and the bootstrap
refits for reason stability. The data are regenerated with the training seeds, so the numbers are reproducible."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from claimvoice.ml import synth
from claimvoice.ml.metrics import metric_set
from claimvoice.ml.registry import ARTIFACTS, IN_USE, load_models, load_registry
from claimvoice.ml.train import (
    N_AUDIT,
    SEED,
    TARGET,
    Calibrator,
    Data,
    Version,
    choose_threshold,
    drift,
    evaluate_version,
    fairness,
    fit_logistic,
    load_data,
    n_signs,
    route_all,
    shap_stability,
)


def load_version(check: str, version: int = IN_USE) -> Version:
    import xgboost as xgb

    entry = load_models()[check][str(version)]
    tech = load_registry()["checks"][check]["technical"]
    booster = xgb.Booster()
    booster.load_model(str(ARTIFACTS / entry["booster"]))
    cal = Calibrator(list(entry["calibration"]["x"]), list(entry["calibration"]["y"]))
    return Version(
        check,
        version,
        booster,
        cal,
        float(entry["threshold"]),
        tuple(entry["features"]),
        dict(tech["params"]),
        int(tech["rounds"]),
        "",
        "",
    )


def recheck(version: int = IN_USE, *, stability: bool = True) -> dict[str, Any]:
    data: Data = load_data()
    cm = synth.load_cost_model()
    audit = synth.generate(N_AUDIT, seed=SEED + 1, start=date(2025, 10, 1), end=date(2025, 12, 31), cost_model=cm)
    size, closer = load_version("size", version), load_version("closer_look", version)
    routes_audit = route_all(audit, size, closer)
    out: dict[str, Any] = {"costSource": data.cost_source, "drift": drift(size, closer, data.valid, cm)}
    for check, v in (("size", size), ("closer_look", closer)):
        feats = list(v.features)
        y_tr, y_va = data.train[TARGET[check]].to_numpy(), data.valid[TARGET[check]].to_numpy()
        y_te = data.test[TARGET[check]].to_numpy()
        base = fit_logistic(data.train[feats], y_tr)
        cal = Calibrator.fit(base.predict_proba(data.valid[feats])[:, 1], y_va)
        thr = choose_threshold(
            check,
            cal(base.predict_proba(data.valid[feats])[:, 1]),
            y_va,
            n_signs(data.valid) if check == "closer_look" else None,
        )
        baseline = metric_set(
            y_te,
            cal(base.predict_proba(data.test[feats])[:, 1]),
            thr,
            signs=n_signs(data.test) if check == "closer_look" else None,
        )
        out[check] = {
            "metrics": evaluate_version(check, v, data),
            "baseline": baseline,
            "fairness": fairness(audit, routes_audit, check),
            "stability": shap_stability(check, data, v) if stability else {"jaccard": None},
            "positives": int(np.sum(y_te)),
            "testRows": len(y_te),
        }
    return out
