"""Experiment tracking and the model registry in MLflow (local SQLite + `mlruns/`, git-ignored).

One run per check, version and algorithm (parameters, test metrics, gates, fairness gap, stability). The boosters are
registered as `claimvoice-size` and `claimvoice-closer-look` model versions with the aliases `champion` (in use),
`challenger` (candidate) and `previous` (retired). The committed registry (`ml/artifacts/registry.json`) mirrors what
the API serves; promoting a version still takes the two sign-offs recorded by the platform.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ALIASES = {4: "previous", 5: "champion", 6: "challenger"}


def tracking_uri() -> str:
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if uri:
        return uri
    (REPO_ROOT / "mlruns").mkdir(exist_ok=True)
    return f"sqlite:///{REPO_ROOT / 'mlruns' / 'mlflow.db'}"


def log_all(versions: dict[str, dict[int, Any]], baselines: dict[str, dict[str, Any]], report: dict[str, Any]) -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    from claimvoice.ml.registry import ARTIFACTS

    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment("claimvoice-routing-checks")
    client = MlflowClient()
    for check, by_v in versions.items():
        name = f"claimvoice-{check.replace('_', '-')}"
        try:
            client.get_registered_model(name)
        except Exception:
            client.create_registered_model(name, description=f"ClaimVoice {check.replace('_', '-')} check")
        for algo, m in baselines[check].items():
            with mlflow.start_run(run_name=f"{check}-{algo}"):
                mlflow.set_tags({"check": check, "algorithm": algo, "role": "baseline"})
                mlflow.log_metrics({k: float(v) for k, v in m.items() if isinstance(v, int | float)})
        for vnum, v in sorted(by_v.items()):
            with mlflow.start_run(run_name=f"{check}-xgboost-v{vnum}") as run:
                mlflow.set_tags({"check": check, "algorithm": "xgboost", "version": str(vnum), "stage": ALIASES[vnum]})
                mlflow.log_params(
                    {**{k: v.params[k] for k in v.params}, "rounds": v.rounds, "threshold": round(v.threshold, 6)}
                )
                mlflow.log_metrics({k: float(x) for k, x in v.metrics.items() if isinstance(x, int | float)})
                mlflow.log_metric("fairness_max_gap", float(v.fairness["maxGap"]))
                if v.stability.get("jaccard") is not None:
                    mlflow.log_metric("shap_top5_jaccard", float(v.stability["jaccard"]))
                path = ARTIFACTS / f"{check}_v{vnum}.json"
                if path.exists():
                    mlflow.log_artifact(str(path), artifact_path="model")
                source = f"{run.info.artifact_uri}/model"
            mv = client.create_model_version(
                name, source, run_id=run.info.run_id, tags={"claimvoice_version": str(vnum)}
            )
            client.set_registered_model_alias(name, ALIASES[vnum], mv.version)
