"""Fact sheets (model cards) in plain language, generated from the training run without run timestamps.

`fact_sheet()` returns the sections the Routing checks page shows; `write_markdown()` writes the same content to
docs/model-cards/ for reviewers and the regulator pack."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from claimvoice.ml.features import FEATURE_LABELS

REPO_ROOT = Path(__file__).resolve().parents[3]
CARDS_DIR = REPO_ROOT / "docs" / "model-cards"


def _pct(x: float) -> str:
    return f"{round(x * 100)} in 100"


def fact_sheet(
    check: str,
    v: Any,
    technical: Mapping[str, Any],
    fair: Mapping[str, Any],
    excluded: Mapping[str, str],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    m = v.metrics
    looks = sorted({FEATURE_LABELS.get(f, f) for f in v.features})
    if check == "size":
        for_ = [
            "Estimates how likely a new claim is to be large or complex, so simple claims can be fast-tracked and the "
            "rest go straight to an adjuster.",
            "Runs once, when the call ends. A person can change the route with a reason at any time.",
        ]
        not_for = [
            "Deciding whether a claim is covered or how much is paid.",
            "Pricing a policy, or judging the caller.",
        ]
        tested = [
            f"On {technical['test'].get('auc', 0):.2f} AUC terms it separates large from small claims well; at the "
            f"setting in use it sends {_pct(m.get('recallAtThreshold') or 0)} of large or complex claims to an "
            "adjuster.",
            f"Its scores are calibrated: when it says 30 in 100, about 30 in 100 such claims turn out large "
            f"(expected calibration error {m['ece']:.3f}).",
            f"It beats a simple scorecard on the same data (PR-AUC {m['prAuc']:.2f} against "
            f"{technical['baseline']['prAuc']:.2f}).",
        ]
    else:
        for_ = [
            "Asks someone in special investigations to look at a claim when several documented signs line up.",
            "A referral is a request for review. It is not a finding of fraud and never denies a claim.",
        ]
        not_for = [
            "Denying, delaying or reducing a claim.",
            "Judging a person by who they are: it never sees age, language, region or anything about their voice.",
        ]
        tested = [
            f"It refers {_pct(m.get('flaggedRate') or 0)} claims for review and needs at least two signs before it "
            "can refer one.",
            f"Of the claims it refers, {_pct(m.get('precisionAtThreshold') or 0)} turn out to need a closer look in "
            "testing; it finds "
            f"{_pct(m.get('recallAtThreshold') or 0)} of those that do.",
            f"It beats a simple scorecard on the same data (PR-AUC {m['prAuc']:.2f} against "
            f"{technical['baseline']['prAuc']:.2f}); scores are calibrated (expected calibration error "
            f"{m['ece']:.3f}).",
        ]
    worst = max(fair["rows"], key=lambda r: r["gap"])
    fairness = [
        f"The {'closer-look' if check == 'closer_look' else 'fast-track'} rate is "
        f"{_pct(fair['overallRate'])} overall. Every region, language and age band stays within "
        f"{fair['band'] * 100:.1f} points of it (largest gap {worst['gap'] * 100:.1f} points, {worst['label']})."
        if fair["passed"]
        else f"A group is outside the allowed band ({worst['label']}, {worst['gap'] * 100:.1f} points): this version "
        "cannot go into use.",
        "Age, language and region are never used to route a claim. We use them only here, to check fairness.",
    ]
    limits = [
        "It learned from synthetic claim calls shaped like the ones the line takes, with real claim costs from "
        "French motor insurance data (freMTPL2). Its absolute accuracy describes that data, not a real book of "
        "business; what carries over is the method: calibration, reasons, fairness tests, monitoring and sign-off.",
        "It only knows what the caller said and what the policy shows. Photos and an adjuster's visit come later.",
    ]
    if check == "closer_look":
        limits.append(
            "The closer-look labels come from documented patterns injected into the synthetic data, with 3 in 100 "
            "labels flipped to mimic investigators disagreeing."
        )
    bench = report.get("benchmark")
    tech_lines = [
        f"Algorithm: {v.algorithm}, tuned with Optuna; isotonic calibration on the validation months.",
        f"Split: {v.split}.",
        f"Test: AUC {m['auc']:.3f}, PR-AUC {m['prAuc']:.3f}, Brier {m['brier']:.4f}, ECE {m['ece']:.4f}.",
        f"Logistic baseline: AUC {technical['baseline']['auc']:.3f}, PR-AUC {technical['baseline']['prAuc']:.3f}; "
        f"random forest: AUC {technical['randomForest']['auc']:.3f}, PR-AUC {technical['randomForest']['prAuc']:.3f}.",
        f"Before calibration: Brier {technical['uncalibrated']['brier']:.4f}, "
        f"ECE {technical['uncalibrated']['ece']:.4f}; Platt scaling: Brier {technical['platt']['brier']:.4f}, "
        f"ECE {technical['platt']['ece']:.4f}.",
        f"Reasons: exact TreeSHAP values; top-5 overlap across 5 bootstrap refits {v.stability['jaccard']:.2f} "
        "(Jaccard).",
    ]
    if bench and check == "size":
        tech_lines.append(
            f"Public benchmark on freMTPL2 alone (top tenth of claim cost from policy fields): logistic AUC "
            f"{bench['logistic']['auc']:.2f}, XGBoost AUC {bench['xgboost']['auc']:.2f}. {bench['note']}"
        )
    return {
        "sections": [
            {"key": "for", "title": "What it is for", "body": for_},
            {"key": "not_for", "title": "What it is not for", "body": not_for},
            {"key": "looks_at", "title": "What it looks at", "body": looks},
            {"key": "never_looks_at", "title": "What it never looks at", "body": list(excluded.values())},
            {"key": "tested", "title": "How it was tested", "body": tested},
            {"key": "fairness", "title": "Fairness", "body": fairness},
            {"key": "limits", "title": "Limits", "body": limits},
            {
                "key": "sign_offs",
                "title": "Sign-offs",
                "body": [
                    "A version goes into use only when every gate passes and two different people sign: a claims "
                    "supervisor and compliance (model risk)."
                ],
            },
            {"key": "technical", "title": "For the technical reviewer", "body": tech_lines},
        ]
    }


def write_markdown(reg: Mapping[str, Any]) -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    for key, check in reg["checks"].items():
        lines = [f"# {check['name']} fact sheet", "", f"*{check['question']}* {check['decides']}", ""]
        for s in check["factSheet"]["sections"]:
            lines += [f"## {s['title']}", ""] + [f"- {b}" for b in s["body"]] + [""]
        lines += ["## Versions", "", "| Version | Stage | PR-AUC | ECE | Gates |", "|---|---|---:|---:|---|"]
        for ver in check["versions"]:
            passed = (
                "all passed" if ver["gatesPassed"] else ", ".join(g["label"] for g in ver["gates"] if not g["passed"])
            )
            lines.append(
                f"| {ver['version']} | {ver['stage'].replace('_', ' ')} | {ver['metrics']['prAuc']:.3f} | "
                f"{ver['metrics']['ece']:.3f} | {passed} |"
            )
        lines += ["", "Generated by `make train`. No run dates are recorded here; MLflow keeps the run history.", ""]
        (CARDS_DIR / f"{key.replace('_', '-')}.md").write_text("\n".join(lines))
