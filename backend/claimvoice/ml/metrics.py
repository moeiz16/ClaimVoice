"""Metrics for the routing checks: discrimination (AUC, PR-AUC), calibration (Brier, expected calibration error),
operating-point rates, curves for the fact sheet, and population stability (PSI) for drift."""

from __future__ import annotations

from typing import Any

import numpy as np

PSI_WATCH = 0.10
PSI_ACT = 0.25


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-width bins: sum over bins of |observed - predicted| x share."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(total)


def calibration_bins(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        if m.any():
            out.append(
                {
                    "predicted": round(float(p[m].mean()), 4),
                    "observed": round(float(y[m].mean()), 4),
                    "count": int(m.sum()),
                }
            )
    return out


def curve(y: np.ndarray, p: np.ndarray, kind: str, points: int = 40) -> list[dict[str, float]]:
    from sklearn.metrics import precision_recall_curve, roc_curve

    if kind == "roc":
        x, yy, _ = roc_curve(y, p)
    else:
        prec, rec, _ = precision_recall_curve(y, p)
        x, yy = rec[::-1], prec[::-1]
    idx = np.unique(np.linspace(0, len(x) - 1, min(points, len(x))).astype(int))
    return [{"x": round(float(x[i]), 4), "y": round(float(yy[i]), 4)} for i in idx]


def metric_set(
    y: np.ndarray, p: np.ndarray, threshold: float | None = None, *, signs: np.ndarray | None = None
) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    y = np.asarray(y)
    out: dict[str, Any] = {
        "auc": round(float(roc_auc_score(y, p)), 4),
        "prAuc": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "ece": round(ece(y, p), 4),
        "positiveRate": round(float(y.mean()), 4),
    }
    if threshold is not None:
        flag = p >= threshold
        if signs is not None:
            flag = flag & (signs >= 2)
        tp = float((flag & (y == 1)).sum())
        out.update(
            {
                "threshold": round(float(threshold), 4),
                "recallAtThreshold": round(tp / max(1.0, float((y == 1).sum())), 4),
                "precisionAtThreshold": round(tp / max(1.0, float(flag.sum())), 4),
                "flaggedRate": round(float(flag.mean()), 4),
            }
        )
    return out


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population stability index of `current` against `reference`, with reference-decile bins."""
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / max(1, len(cur))
    r, c = np.clip(r, 1e-4, None), np.clip(c, 1e-4, None)
    return float(np.sum((c - r) * np.log(c / r)))


def status_for_psi(value: float) -> str:
    return "act" if value > PSI_ACT else ("watch" if value >= PSI_WATCH else "stable")
