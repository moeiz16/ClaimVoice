"""Routing-check suite: the committed models re-checked against the gates in docs/API_CONTRACT.md §6.3.

The size check (severity/complexity) and the closer-look check (fraud indicators) are scored on the test months
(October to December 2025) of the synthetic intake records, compared with a logistic baseline, checked for
calibration, fairness by region, language and age band (an audit sample; never inputs), SHAP stability across
bootstrap refits, and PSI drift (weekly, plus a deliberately shifted month that must raise the alarm). The freMTPL2
public benchmark is reported as it is."""

from __future__ import annotations

from common import Gate, Report, table

from claimvoice.ml.evaluate import recheck
from claimvoice.ml.metrics import PSI_ACT
from claimvoice.ml.registry import load_registry

SUITE = "models"
NAMES = {"size": "Size check", "closer_look": "Closer-look check"}


def run() -> Report:
    r = recheck()
    gates: list[Gate] = []
    rows = []
    fair_rows = []
    for check in ("size", "closer_look"):
        m, b, f, s = r[check]["metrics"], r[check]["baseline"], r[check]["fairness"], r[check]["stability"]
        name = NAMES[check]
        band = 0.015 if check == "closer_look" else 0.05
        gates += [
            Gate(
                SUITE,
                f"{check}_pr_auc_lift",
                f"{name}: PR-AUC over the logistic baseline",
                m["prAuc"] - b["prAuc"],
                0.02,
                "min",
            ),
            Gate(SUITE, f"{check}_ece", f"{name}: expected calibration error", m["ece"], 0.05, "max"),
            Gate(
                SUITE,
                f"{check}_fairness",
                f"{name}: largest group gap ({'closer-look' if check == 'closer_look' else 'fast-track'} rate)",
                f["maxGap"],
                band,
                "max",
            ),
            Gate(SUITE, f"{check}_shap", f"{name}: SHAP top-5 stability (Jaccard)", s["jaccard"], 0.70, "min"),
            Gate(
                SUITE,
                f"{check}_psi",
                f"{name}: weekly score PSI (worst week)",
                max(w["psi"] for w in r["drift"]["weeks"][check]),
                PSI_ACT,
                "max",
            ),
        ]
        if check == "size":
            gates.append(
                Gate(
                    SUITE,
                    "size_recall",
                    "Size check: large or complex claims sent to an adjuster",
                    m["recallAtThreshold"],
                    0.85,
                    "min",
                )
            )
        else:
            gates.append(
                Gate(SUITE, "closer_rate", "Closer-look check: share of claims referred", m["flaggedRate"], 0.08, "max")
            )
        rows += [
            [name, "XGBoost (v5, calibrated)", m["auc"], m["prAuc"], m["brier"], m["ece"]],
            [name, "Logistic baseline", b["auc"], b["prAuc"], b["brier"], b["ece"]],
        ]
        fair_rows += [
            [
                name,
                x["label"],
                x["count"],
                f"{x['flaggedRate']:.3f}",
                f"{x['gap']:.3f}",
                "yes" if x["withinBand"] else "NO",
            ]
            for x in f["rows"]
        ]
    shift = r["drift"]["simulatedShift"]
    gates.append(
        Gate(
            SUITE,
            "drift_alarm",
            "Drift alarm fires on a simulated shift (lowest PSI of the two checks)",
            min(shift.values()),
            PSI_ACT,
            "min",
        )
    )
    reg = load_registry()
    rf = {c: reg["checks"][c]["technical"]["randomForest"] for c in ("size", "closer_look")}
    rows += [
        [NAMES[c], "Random forest (training run)", rf[c]["auc"], rf[c]["prAuc"], rf[c]["brier"], rf[c]["ece"]]
        for c in ("size", "closer_look")
    ]
    bench = reg.get("benchmark")
    weeks = [
        [w["label"], r["drift"]["weeks"]["size"][i]["psi"], r["drift"]["weeks"]["closer_look"][i]["psi"]]
        for i, w in enumerate(r["drift"]["weeks"]["size"])
    ]
    lines = [
        f"Test months: October to December 2025 ({r['size']['testRows']} synthetic calls; {r['size']['positives']} "
        f"large or complex, {r['closer_look']['positives']} worth a closer look). Claim costs: {r['costSource']}.",
        "",
        *table(["Check", "Model", "AUC", "PR-AUC", "Brier", "ECE"], rows, "---|---|---:|---:|---:|---:"),
        "",
        "Fairness on an audit sample of 20,000 synthetic calls from the test months (groups never used as inputs):",
        "",
        *table(["Check", "Group", "Calls", "Rate", "Gap", "Within band"], fair_rows, "---|---|---:|---:|---:|---"),
        "",
        "Weekly score PSI against the validation months (Watch at 0.10, Act at 0.25); the last week holds the "
        f"Chinook windstorm surge. Simulated shift: size {shift['size']:.2f}, closer look {shift['closer_look']:.2f}.",
        "",
        *table(["Week", "Size", "Closer look"], weeks),
    ]
    if bench:
        lines += [
            "",
            f"Public benchmark, freMTPL2 only ({bench['rows']:,} real French motor claims; top tenth of cost from "
            f"policy fields): logistic AUC {bench['logistic']['auc']:.3f} (PR-AUC {bench['logistic']['prAuc']:.3f}),"
            f" XGBoost AUC {bench['xgboost']['auc']:.3f} (PR-AUC {bench['xgboost']['prAuc']:.3f}). " + bench["note"],
        ]
    return Report(gates, lines, {k: r[k] for k in ("size", "closer_look")})
