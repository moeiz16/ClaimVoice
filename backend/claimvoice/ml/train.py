"""Train, calibrate, explain, test and register the two routing checks (`make train`).

    python -m claimvoice.ml.train all       # everything below, reproducibly (fixed seeds, 2 threads)

For each check (size = severity/complexity, closer_look = fraud indicators):
1. synthetic intake records (`ml.synth`) with costs from freMTPL2, split by loss month (train before July 2025,
   validate July-September, test October-December);
2. baselines first: logistic regression (scorecard-style, standardised) and a random forest;
3. XGBoost tuned with Optuna (TPE, fixed seed) on validation PR-AUC;
4. isotonic calibration on the validation months (Platt reported for comparison); Brier and ECE on test;
5. thresholds for fixed targets: size recall of large/complex claims >= 0.90; closer-look referral rate <= 8 %;
6. TreeSHAP reasons, and their stability across 5 bootstrap refits;
7. fairness by region, language and age band on a separate audit sample (never inputs);
8. PSI drift over the eight weeks to the demo date, and a simulated shift that must raise the alarm;
9. three versions per check (v4 retired, v5 in use, v6 candidate) in MLflow (SQLite + mlruns/) and in the committed
   registry the API reads (`ml/artifacts/registry.json`), plus fact sheets in docs/model-cards/;
10. a freMTPL2-only large-claim benchmark on real public data.
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from claimvoice.ml import synth
from claimvoice.ml.features import FEATURE_LABELS, FRAUD_FEATURES, SEVERITY_FEATURES
from claimvoice.ml.metrics import calibration_bins, curve, ece, metric_set, psi, status_for_psi
from claimvoice.ml.routing import decide

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = Path(__file__).parent / "artifacts"
CARDS_DIR = ROOT / "docs" / "model-cards"
SEED = 7
THREADS = 2
N_RECORDS = 18000
N_AUDIT = 20000
OPTUNA_TRIALS = 30
CHECKS = ("size", "closer_look")
TARGET = {"size": "large", "closer_look": "fraud"}
FEATURES = {"size": SEVERITY_FEATURES, "closer_look": FRAUD_FEATURES}
GATES = {
    "beats_baseline": 0.02,  # XGBoost PR-AUC >= logistic + 0.02
    "calibrated": 0.05,  # ECE after isotonic <= 0.05
    "fair_closer_look": 0.015,  # closer-look rate within +-1.5 points per group
    "fair_fast_track": 0.05,  # fast-track rate within +-5 points per group
    "reasons_stable": 0.70,  # mean Jaccard of SHAP top-5 across 5 bootstrap refits
    "inputs_stable": 0.25,  # weekly score PSI below Act
}
WEEK_STARTS = [date(2025, 11, 17) + pd.Timedelta(weeks=i).to_pytimedelta() for i in range(8)]
SURGE = (date(2026, 1, 7), date(2026, 1, 8))

warnings.filterwarnings("ignore")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


# ------------------------------------------------------------------ data


@dataclass
class Data:
    all: pd.DataFrame
    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame
    cost_source: str


def load_data(n: int = N_RECORDS, seed: int = SEED) -> Data:
    cm = synth.load_cost_model()
    df = synth.generate(n, seed=seed, cost_model=cm)
    parts = synth.time_split(df)
    return Data(df, parts["train"], parts["valid"], parts["test"], cm.source)


# ------------------------------------------------------------------ models


def fit_logistic(X: pd.DataFrame, y: np.ndarray) -> Any:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=3000)).fit(X, y)


def fit_forest(X: pd.DataFrame, y: np.ndarray, seed: int = SEED) -> Any:
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=20, n_jobs=THREADS, random_state=seed
    ).fit(X, y)


def xgb_params(trial_params: dict[str, Any], pos_rate: float) -> dict[str, Any]:
    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "nthread": THREADS,
        "seed": SEED,
        "max_depth": int(trial_params["max_depth"]),
        "eta": float(trial_params["eta"]),
        "min_child_weight": float(trial_params["min_child_weight"]),
        "subsample": float(trial_params["subsample"]),
        "colsample_bytree": float(trial_params["colsample_bytree"]),
        "lambda": float(trial_params["lambda"]),
        "scale_pos_weight": float(trial_params.get("scale_pos_weight", 1.0)),
    }


def fit_xgb(X: pd.DataFrame, y: np.ndarray, params: dict[str, Any], rounds: int) -> Any:
    import xgboost as xgb

    return xgb.train(params, xgb.DMatrix(X, label=y, feature_names=list(X.columns)), num_boost_round=rounds)


def predict_xgb(booster: Any, X: pd.DataFrame) -> np.ndarray:
    import xgboost as xgb

    return np.asarray(booster.predict(xgb.DMatrix(X, feature_names=list(X.columns))))


def contributions(booster: Any, X: pd.DataFrame) -> np.ndarray:
    """Exact TreeSHAP values from XGBoost (last column is the bias)."""
    import xgboost as xgb

    return np.asarray(booster.predict(xgb.DMatrix(X, feature_names=list(X.columns)), pred_contribs=True))


def tune(X: pd.DataFrame, y: np.ndarray, Xv: pd.DataFrame, yv: np.ndarray, trials: int) -> tuple[dict[str, Any], int]:
    import optuna
    from sklearn.metrics import average_precision_score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    pos = float(y.mean())

    def objective(trial: optuna.Trial) -> float:
        p = {
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "eta": trial.suggest_float("eta", 0.02, 0.2, log=True),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 20.0, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "lambda": trial.suggest_float("lambda", 0.5, 10.0, log=True),
            "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, max(1.5, 0.5 / max(pos, 1e-3))),
        }
        rounds = trial.suggest_int("rounds", 80, 400, step=40)
        b = fit_xgb(X, y, xgb_params(p, pos), rounds)
        return float(average_precision_score(yv, predict_xgb(b, Xv)))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=trials)
    best = dict(study.best_params)
    rounds = int(best.pop("rounds"))
    return best, rounds


@dataclass
class Calibrator:
    """Isotonic regression stored as its step points (no pickles in the repository)."""

    x: list[float]
    y: list[float]

    def __call__(self, p: np.ndarray) -> np.ndarray:
        return np.interp(np.asarray(p, dtype=float), self.x, self.y)

    @classmethod
    def fit(cls, raw: np.ndarray, y: np.ndarray) -> Calibrator:
        from sklearn.isotonic import IsotonicRegression

        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw, y)
        xs = [float(v) for v in iso.X_thresholds_]
        ys = [float(v) for v in iso.y_thresholds_]
        return cls(xs, ys)


def platt(raw_valid: np.ndarray, yv: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    from sklearn.linear_model import LogisticRegression

    eps = 1e-6

    def logit(p: np.ndarray) -> np.ndarray:
        p = np.clip(p, eps, 1 - eps)
        return np.log(p / (1 - p)).reshape(-1, 1)

    lr = LogisticRegression().fit(logit(raw_valid), yv)
    return lambda p: lr.predict_proba(logit(np.asarray(p)))[:, 1]


def choose_threshold(check: str, p: np.ndarray, y: np.ndarray, signs: np.ndarray | None = None) -> float:
    """size: the highest threshold that still catches >= 90 % of large/complex claims.
    closer_look: the threshold with the best F1 among those referring <= 8 % of claims (with >= 2 signs)."""
    grid = np.unique(np.round(p, 4))
    if check == "size":
        best = float(grid.min())
        for t in grid:
            if (p[y == 1] >= t).mean() >= 0.90:
                best = float(t)
        return best
    assert signs is not None
    best_t, best_f1 = float(grid.max()), -1.0
    for t in grid:
        flag = (p >= t) & (signs >= 2)
        if flag.mean() > 0.08 or flag.sum() == 0:
            continue
        tp = float((flag & (y == 1)).sum())
        prec, rec = tp / flag.sum(), tp / max(1, (y == 1).sum())
        f1 = 0 if tp == 0 else 2 * prec * rec / (prec + rec)
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1
    return best_t


# ------------------------------------------------------------------ one version of one check


@dataclass
class Version:
    check: str
    version: int
    booster: Any
    calibrator: Calibrator
    threshold: float
    features: tuple[str, ...]
    params: dict[str, Any]
    rounds: int
    trained_on: str
    split: str
    algorithm: str = "Gradient-boosted trees (XGBoost)"

    def proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.calibrator(predict_xgb(self.booster, X[list(self.features)]))


def n_signs(df: pd.DataFrame) -> np.ndarray:
    from claimvoice.ml.features import signs_present

    cols = [c for c in FRAUD_FEATURES + SEVERITY_FEATURES if c in df.columns]
    return np.array([len(signs_present(r)) for r in df[list(dict.fromkeys(cols))].to_dict("records")])


def build_version(
    check: str,
    version: int,
    train: pd.DataFrame,
    calib: pd.DataFrame,
    *,
    params: dict[str, Any],
    rounds: int,
    features: tuple[str, ...],
    trained_on: str,
    split: str,
) -> Version:
    target = TARGET[check]
    Xtr, ytr = train[list(features)], train[target].to_numpy()
    booster = fit_xgb(Xtr, ytr, xgb_params(params, float(ytr.mean())), rounds)
    raw_cal = predict_xgb(booster, calib[list(features)])
    cal = Calibrator.fit(raw_cal, calib[target].to_numpy())
    p_cal = cal(raw_cal)
    thr = choose_threshold(check, p_cal, calib[target].to_numpy(), n_signs(calib) if check == "closer_look" else None)
    return Version(check, version, booster, cal, thr, features, params, rounds, trained_on, split)


# ------------------------------------------------------------------ evaluation


def route_all(df: pd.DataFrame, size: Version, closer: Version) -> pd.Series:
    ps, pf = size.proba(df), closer.proba(df)
    cols = list(dict.fromkeys([*SEVERITY_FEATURES, *FRAUD_FEATURES]))
    routes = [
        decide(r, float(a), float(b), size_threshold=size.threshold, fraud_threshold=closer.threshold).route
        for r, a, b in zip(df[cols].to_dict("records"), ps, pf, strict=True)
    ]
    return pd.Series(routes, index=df.index)


def fairness(df: pd.DataFrame, routes: pd.Series, check: str) -> dict[str, Any]:
    """Closer-look (or fast-track) rate per region, language and age band against the overall rate."""
    flag = (routes == ("special_investigation" if check == "closer_look" else "fast_track")).astype(int)
    target = df[TARGET[check]]
    band = GATES["fair_closer_look"] if check == "closer_look" else GATES["fair_fast_track"]
    overall = float(flag.mean())
    labels = {
        "CA-AB": "Alberta",
        "US-CO": "Colorado",
        "CA-QC": "Québec",
        "en": "English",
        "fr": "French",
        "under_35": "Under 35",
        "35_64": "35 to 64",
        "65_plus": "65 and over",
    }
    rows: list[dict[str, Any]] = []
    for dim in ("region", "language", "age_band"):
        for group, idx in df.groupby(dim).groups.items():
            f, t = flag.loc[idx], target.loc[idx]
            positive = check == "closer_look"
            tp_mask = t == 1 if positive else t == 0
            tpr = float(f[tp_mask].mean()) if tp_mask.sum() else None
            fpr = float(f[~tp_mask].mean()) if (~tp_mask).sum() else None
            rate = float(f.mean())
            rows.append(
                {
                    "dimension": dim,
                    "group": str(group),
                    "label": labels.get(str(group), str(group)),
                    "count": len(idx),
                    "flaggedRate": round(rate, 4),
                    "truePositiveRate": None if tpr is None else round(tpr, 4),
                    "falsePositiveRate": None if fpr is None else round(fpr, 4),
                    "gap": round(abs(rate - overall), 4),
                    "withinBand": abs(rate - overall) <= band,
                }
            )
    return {
        "overallRate": round(overall, 4),
        "band": band,
        "passed": all(r["withinBand"] for r in rows),
        "maxGap": round(max(float(r["gap"]) for r in rows), 4),
        "rows": rows,
        "note": "Age, language and region are never used to route a claim. We use them only here, to check fairness.",
    }


def shap_stability(check: str, data: Data, v: Version, *, refits: int = 5, k: int = 5) -> dict[str, Any]:
    feats = list(v.features)
    X_test = data.test[feats]

    def top_k(booster: Any) -> set[str]:
        c = contributions(booster, X_test)[:, :-1]
        imp = np.abs(c).mean(axis=0)
        return {feats[i] for i in np.argsort(-imp)[:k]}

    base = top_k(v.booster)
    rng = np.random.default_rng(SEED)
    jac = []
    for _ in range(refits):
        idx = rng.integers(0, len(data.train), len(data.train))
        boot = data.train.iloc[idx]
        b = fit_xgb(
            boot[feats],
            boot[TARGET[check]].to_numpy(),
            xgb_params(v.params, float(boot[TARGET[check]].mean())),
            v.rounds,
        )
        other = top_k(b)
        jac.append(len(base & other) / len(base | other))
    return {"jaccard": round(float(np.mean(jac)), 3), "runs": [round(j, 3) for j in jac], "top": sorted(base)}


_FRAMES: dict[tuple[Any, ...], pd.DataFrame] = {}


def _frame(n: int, seed: int, start: date, end: date, cm: synth.CostModel, **kw: Any) -> pd.DataFrame:
    key = (n, seed, start, end, tuple(sorted((kw.get("shift") or {}).items())), kw.get("wind_surge"))
    if key not in _FRAMES:
        _FRAMES[key] = synth.generate(n, seed=seed, start=start, end=end, cost_model=cm, **kw)
    return _FRAMES[key]


def recent_weeks(cm: synth.CostModel) -> list[tuple[date, pd.DataFrame]]:
    """Eight weeks of synthetic calls up to the demo date; the last week holds the Chinook windstorm surge."""
    out = []
    for i, start in enumerate(WEEK_STARTS):
        end = start + pd.Timedelta(days=6).to_pytimedelta()
        out.append((start, _frame(260, 100 + i, start, end, cm, wind_surge=SURGE)))
    return out


SHIFT = {"wind_share": 6.0, "severe": 8.0, "late_report": 5.0, "new_policy": 5.0, "story_changes": 5.0}


def shifted_frame(cm: synth.CostModel) -> pd.DataFrame:
    """A deliberately shifted month (drift alarm test): far more wind, costlier claims, many more signs."""
    return _frame(1500, 999, date(2026, 1, 1), date(2026, 1, 31), cm, shift=SHIFT)


def drift(size: Version, closer: Version, reference: pd.DataFrame, cm: synth.CostModel) -> dict[str, Any]:
    """Weekly score PSI for the eight weeks to the demo date (the Chinook surge in the last), and a simulated shift."""
    ref = {"size": size.proba(reference), "closer_look": closer.proba(reference)}
    weeks: dict[str, list[dict[str, Any]]] = {"size": [], "closer_look": []}
    for start, df in recent_weeks(cm):
        for check, v in (("size", size), ("closer_look", closer)):
            value = psi(ref[check], v.proba(df))
            weeks[check].append(
                {
                    "label": f"Week of {start.day} {start.strftime('%b')}",
                    "psi": round(value, 3),
                    "status": status_for_psi(value),
                }
            )
    shifted = shifted_frame(cm)
    alarm = {
        check: round(psi(ref[check], v.proba(shifted)), 3) for check, v in (("size", size), ("closer_look", closer))
    }
    return {"weeks": weeks, "simulatedShift": alarm}


def evaluate_version(check: str, v: Version, data: Data) -> dict[str, Any]:
    y = data.test[TARGET[check]].to_numpy()
    p = v.proba(data.test)
    signs = n_signs(data.test) if check == "closer_look" else None
    return metric_set(y, p, v.threshold, signs=signs)


# ------------------------------------------------------------------ freMTPL2 benchmark


def fremtpl_benchmark() -> dict[str, Any] | None:
    d = synth.FREMTPL_DIR
    if not (d / "freMTPL2freq.parquet").exists():
        return None
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import GroupShuffleSplit

    freq = pd.read_parquet(d / "freMTPL2freq.parquet")
    sev = pd.read_parquet(d / "freMTPL2sev.parquet")
    freq["IDpol"] = freq["IDpol"].astype("int64")
    sev["IDpol"] = sev["IDpol"].astype("int64")
    freq = freq.drop_duplicates("IDpol")
    df = sev.merge(freq.drop(columns=["ClaimNb"]), on="IDpol", how="inner")
    y = (df["ClaimAmount"] > df["ClaimAmount"].quantile(0.90)).astype(int).to_numpy()
    num = ["Exposure", "VehPower", "VehAge", "BonusMalus", "Density"]  # no driver age, no region (fairness only)
    cat = ["Area", "VehBrand", "VehGas"]
    X = pd.get_dummies(df[num + cat].astype(dict.fromkeys(cat, "string")), columns=cat, dtype=float)
    X["Density"] = np.log1p(X["Density"])
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED).split(X, y, df["IDpol"]))
    base = fit_logistic(X.iloc[tr], y[tr])
    pb = base.predict_proba(X.iloc[te])[:, 1]
    params = {
        "max_depth": 3,
        "eta": 0.05,
        "min_child_weight": 5.0,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "lambda": 2.0,
    }
    b = fit_xgb(X.iloc[tr], y[tr], xgb_params(params, float(y.mean())), 300)
    px = predict_xgb(b, X.iloc[te])
    return {
        "rows": len(df),
        "positiveRate": round(float(y.mean()), 3),
        "logistic": {
            "auc": round(float(roc_auc_score(y[te], pb)), 3),
            "prAuc": round(float(average_precision_score(y[te], pb)), 3),
        },
        "xgboost": {
            "auc": round(float(roc_auc_score(y[te], px)), 3),
            "prAuc": round(float(average_precision_score(y[te], px)), 3),
        },
        "note": "Real French motor claims, policy fields only (no driver age, no region). Whether a claim lands in "
        "the top tenth of cost is only weakly predictable from the policy alone; the size of a loss depends on what "
        "happened, which is why the size check is trained on what the caller tells the line.",
    }


# ------------------------------------------------------------------ the whole run


def train_all(*, trials: int = OPTUNA_TRIALS, log_mlflow: bool = True, write: bool = True) -> dict[str, Any]:
    t0 = time.perf_counter()
    data = load_data()
    cm = synth.load_cost_model()
    audit = synth.generate(N_AUDIT, seed=SEED + 1, start=date(2025, 10, 1), end=date(2025, 12, 31), cost_model=cm)
    report: dict[str, Any] = {
        "costSource": data.cost_source,
        "records": len(data.all),
        "split": {k: len(getattr(data, k)) for k in ("train", "valid", "test")},
    }
    versions: dict[str, dict[int, Version]] = {}
    baselines: dict[str, dict[str, Any]] = {}
    for check in CHECKS:
        feats = FEATURES[check]
        target = TARGET[check]
        Xtr, ytr = data.train[list(feats)], data.train[target].to_numpy()
        Xva, yva = data.valid[list(feats)], data.valid[target].to_numpy()
        Xte, yte = data.test[list(feats)], data.test[target].to_numpy()
        signs_te = n_signs(data.test) if check == "closer_look" else None
        # baselines, calibrated the same way so the comparison is fair
        logit = fit_logistic(Xtr, ytr)
        forest = fit_forest(Xtr, ytr)
        base_rows = {}
        for name, model in (("logistic", logit), ("randomForest", forest)):
            cal = Calibrator.fit(model.predict_proba(Xva)[:, 1], yva)
            p_va = cal(model.predict_proba(Xva)[:, 1])
            thr = choose_threshold(check, p_va, yva, n_signs(data.valid) if check == "closer_look" else None)
            base_rows[name] = metric_set(yte, cal(model.predict_proba(Xte)[:, 1]), thr, signs=signs_te)
        baselines[check] = base_rows
        # v5, the version in use: tuned on the validation months
        params, rounds = tune(Xtr, ytr, Xva, yva, trials)
        v5 = build_version(
            check,
            5,
            data.train,
            data.valid,
            params=params,
            rounds=rounds,
            features=feats,
            trained_on=f"{len(data.train):,} synthetic claim calls (January 2023 to June 2025) with "
            "French motor claim costs (freMTPL2)",
            split="Time split: trained on losses before 1 July 2025, calibrated on July to September, "
            "tested on October to December 2025",
        )
        # v4, the version before: older data, default settings, no tuning
        old_train = data.all[data.all["loss_date"] < "2025-01-01"]
        old_cal = data.all[(data.all["loss_date"] >= "2025-01-01") & (data.all["loss_date"] < "2025-04-01")]
        v4 = build_version(
            check,
            4,
            old_train,
            old_cal,
            params={
                "max_depth": 3,
                "eta": 0.1,
                "min_child_weight": 1.0,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "lambda": 1.0,
            },
            rounds=150,
            features=feats,
            trained_on=f"{len(old_train):,} synthetic claim calls (2023 to 2024)",
            split="Time split: trained on losses before 2025, calibrated on January to March 2025",
        )
        # v6, the candidate: the same settings retrained with the summer months
        new_train = data.all[data.all["loss_date"] < "2025-08-16"]
        new_cal = data.all[(data.all["loss_date"] >= "2025-08-16") & (data.all["loss_date"] < "2025-10-01")]
        v6 = build_version(
            check,
            6,
            new_train,
            new_cal,
            params=params,
            rounds=rounds,
            features=feats,
            trained_on=f"{len(new_train):,} synthetic claim calls (January 2023 to mid-August 2025) "
            "with French motor claim costs (freMTPL2)",
            split="Time split: trained on losses before 16 August 2025, calibrated on 16 August to "
            "30 September, tested on October to December 2025",
        )
        versions[check] = {4: v4, 5: v5, 6: v6}
        raw_te = predict_xgb(v5.booster, Xte)
        platt_p = platt(predict_xgb(v5.booster, Xva), yva)(raw_te)
        report[check] = {
            "params": params,
            "rounds": rounds,
            "threshold": v5.threshold,
            "baselines": base_rows,
            "uncalibrated": {"brier": round(float(np.mean((raw_te - yte) ** 2)), 4), "ece": round(ece(yte, raw_te), 4)},
            "platt": {"brier": round(float(np.mean((platt_p - yte) ** 2)), 4), "ece": round(ece(yte, platt_p), 4)},
        }
    # fairness, stability and drift for each version that can be in use
    for vnum in (4, 5, 6):
        s, c = versions["size"][vnum], versions["closer_look"][vnum]
        routes_audit = route_all(audit, s, c)
        routes_test = route_all(data.test, s, c)
        for check, v in (("size", s), ("closer_look", c)):
            v.__dict__["metrics"] = evaluate_version(check, v, data)
            v.__dict__["fairness"] = fairness(audit, routes_audit, check)
            v.__dict__["routes_test"] = routes_test.value_counts(normalize=True).round(4).to_dict()
    for check in CHECKS:
        for vnum in (4, 5, 6):
            v = versions[check][vnum]
            v.__dict__["stability"] = shap_stability(check, data, v)
    drift_by_version = {
        vnum: drift(versions["size"][vnum], versions["closer_look"][vnum], data.valid, cm) for vnum in (4, 5, 6)
    }
    report["drift"] = drift_by_version[5]
    report["benchmark"] = fremtpl_benchmark()
    report["seconds"] = round(time.perf_counter() - t0, 1)
    if write:
        from claimvoice.ml import registry

        registry.write_all(versions, baselines, report, drift_by_version, data)
    if log_mlflow:
        from claimvoice.ml import tracking

        tracking.log_all(versions, baselines, report)
    return report


def main(argv: list[str]) -> int:
    what = argv[1] if len(argv) > 1 else "all"
    if what not in ("all", "quick"):
        print("usage: python -m claimvoice.ml.train [all|quick]")
        return 2
    report = train_all(trials=OPTUNA_TRIALS if what == "all" else 6)
    print(json.dumps({k: v for k, v in report.items() if k not in ("drift",)}, indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

_ = (FEATURE_LABELS, calibration_bins, curve)
