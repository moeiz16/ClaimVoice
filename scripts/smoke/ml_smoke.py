"""Classical ML toolchain smoke on freMTPL2: XGBoost, logistic baseline, Optuna, calibration, SHAP, MLflow.

A deliberately small version of the severity task (is a motor claim "large", i.e. above the 90th percentile of cost?)
on the real freMTPL2 policies that had a claim, to prove every library loads and runs together on Python 3.13 / arm64
within the memory budget. The real training code lives in backend/claimvoice/ml/.

Run: make data && backend/.venv/bin/python scripts/smoke/ml_smoke.py
"""

from __future__ import annotations

import json
import os
import resource
import sys
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
import shap
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "fremtpl2"
warnings.filterwarnings("ignore")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def load() -> pd.DataFrame:
    freq = pd.read_parquet(DATA / "freMTPL2freq.parquet")
    sev = pd.read_parquet(DATA / "freMTPL2sev.parquet")
    freq["IDpol"] = freq["IDpol"].astype("int64")
    sev["IDpol"] = sev["IDpol"].astype("int64")
    claims = sev.merge(freq.drop(columns=["ClaimNb"]), on="IDpol", how="inner")
    return claims


def main() -> int:
    t0 = time.perf_counter()
    df = load()
    rows = {"freq_rows": None, "claims_joined": len(df)}
    rows["freq_rows"] = len(pd.read_parquet(DATA / "freMTPL2freq.parquet", columns=["IDpol"]))
    cut = df["ClaimAmount"].quantile(0.90)
    y = (df["ClaimAmount"] > cut).astype(int).to_numpy()
    num = ["Exposure", "VehPower", "VehAge", "DrivAge", "BonusMalus", "Density"]
    cat = ["Area", "VehBrand", "VehGas", "Region"]
    X = pd.get_dummies(df[num + cat].astype(dict.fromkeys(cat, "string")), columns=cat, dtype=float)
    X["Density"] = np.log1p(X["Density"])
    groups = df["IDpol"].to_numpy()  # several claims per policy stay on one side of the split
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=7).split(X, y, groups))
    Xtr, Xte, ytr, yte = X.iloc[tr], X.iloc[te], y[tr], y[te]

    base = LogisticRegression(max_iter=500).fit(Xtr, ytr)
    p_base = base.predict_proba(Xte)[:, 1]

    def objective(trial: optuna.Trial) -> float:
        m = xgb.XGBClassifier(
            n_estimators=trial.suggest_int("n_estimators", 100, 300),
            max_depth=trial.suggest_int("max_depth", 3, 6),
            learning_rate=trial.suggest_float("learning_rate", 0.03, 0.2, log=True),
            subsample=0.8,
            tree_method="hist",
            n_jobs=2,
            eval_metric="aucpr",
        )
        m.fit(Xtr, ytr)
        return average_precision_score(yte, m.predict_proba(Xte)[:, 1])

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=7))
    study.optimize(objective, n_trials=4)
    best = xgb.XGBClassifier(**study.best_params, subsample=0.8, tree_method="hist", n_jobs=2)
    cal = CalibratedClassifierCV(best, method="isotonic", cv=3).fit(Xtr, ytr)
    p_xgb = cal.predict_proba(Xte)[:, 1]

    raw = best.fit(Xtr, ytr)
    sv = shap.TreeExplainer(raw).shap_values(Xte.iloc[:200])
    top = pd.Series(np.abs(sv).mean(0), index=X.columns).sort_values(ascending=False).head(3)

    import mlflow

    with tempfile.TemporaryDirectory() as tmp:
        mlflow.set_tracking_uri(f"sqlite:///{tmp}/mlflow.db")
        mlflow.set_experiment("smoke")
        with mlflow.start_run():
            mlflow.log_params(study.best_params)
            mlflow.log_metric("pr_auc", float(average_precision_score(yte, p_xgb)))
        logged = len(mlflow.search_runs(experiment_names=["smoke"]))

    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    out = {
        **rows,
        "positive_rate": round(float(y.mean()), 3),
        "baseline_auc": round(roc_auc_score(yte, p_base), 3),
        "xgb_auc": round(roc_auc_score(yte, p_xgb), 3),
        "baseline_pr_auc": round(average_precision_score(yte, p_base), 3),
        "xgb_pr_auc": round(average_precision_score(yte, p_xgb), 3),
        "xgb_brier": round(brier_score_loss(yte, p_xgb), 4),
        "top_shap": list(top.index),
        "mlflow_runs": logged,
        "versions": {
            "xgboost": xgb.__version__,
            "optuna": optuna.__version__,
            "shap": shap.__version__,
            "mlflow": mlflow.__version__,
        },
        "seconds": round(time.perf_counter() - t0, 1),
        "peak_rss_mb": round(peak_mb),
    }
    print(json.dumps(out, indent=2))
    ok = logged == 1 and out["xgb_auc"] > 0.5
    print("ml smoke:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
