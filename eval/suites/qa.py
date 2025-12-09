"""Call-quality suite: the scorer's agreement with a reviewer's verdicts.

Two labelled sets: reviewed calls handled by people or older scripts, with known problems (all eleven rubric items,
`backend/claimvoice/qa/data/reviewed_calls.yml`), and the scripted callers (the six beads, `eval/qa/labels.yml`)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

import yaml
from common import Gate, Report, table

from claimvoice.dialogue.simulate import load_callers, run_scenario
from claimvoice.qa.fixtures import reviewed_calls
from claimvoice.qa.rubric import RUBRIC
from claimvoice.qa.scorer import events_from_engine, get_call_scorer, slots_from_engine

SUITE = "qa"
LABELS = Path(__file__).resolve().parents[1] / "qa" / "labels.yml"
WORD = {True: "pass", False: "fail", None: "na"}


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    if not pairs:
        return 1.0
    cats = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


async def _scripted() -> dict[str, dict[str, str]]:
    scorer = get_call_scorer()
    labels = yaml.safe_load(LABELS.read_text())["calls"]
    callers = load_callers()
    out: dict[str, dict[str, str]] = {}
    for key in labels:
        res = await run_scenario(callers[key])
        e = res.engine
        v = scorer.verdicts(e.turns, events_from_engine(e), slots_from_engine(e))
        out[key] = {k: WORD[x.passed] for k, x in v.items()}
    return out


def run() -> Report:
    scorer = get_call_scorer()
    pairs: list[tuple[str, str, str]] = []  # (item, human, scorer)
    crit_fail_human = crit_fail_caught = 0
    rows = []
    for call in reviewed_calls().values():
        v = scorer.verdicts(call.turns, call.events, call.slots)
        res = scorer.score(call.turns, call.events, call.slots)
        for item, human in call.labels.items():
            pairs.append((item, human, WORD[v[item].passed]))
        crit = [i.key for i in RUBRIC if i.critical and call.labels.get(i.key) == "fail"]
        if crit:
            crit_fail_human += 1
            crit_fail_caught += res.band == "failed"
        rows.append(
            [
                call.title,
                f"{res.score:.0f}",
                res.band.replace("_", " "),
                ", ".join(k for k, h in call.labels.items() if h == "fail") or "-",
            ]
        )
    scripted = asyncio.run(_scripted())
    labels = yaml.safe_load(LABELS.read_text())["calls"]
    for key, human in labels.items():
        for item, verdict in human.items():
            pairs.append((item, verdict, scripted[key][item]))
    overall = sum(h == s for _, h, s in pairs) / len(pairs)
    kappa = cohen_kappa([(h, s) for _, h, s in pairs])
    by_item: dict[str, list[bool]] = defaultdict(list)
    for item, h, s in pairs:
        by_item[item].append(h == s)
    item_rows = [[k, len(v), f"{sum(v) / len(v):.2f}"] for k, v in sorted(by_item.items())]
    gates = [
        Gate(SUITE, "agreement", "Agreement with reviewers (all items)", overall, 0.90, "min"),
        Gate(SUITE, "kappa", "Cohen's kappa", kappa, 0.70, "min"),
        Gate(
            SUITE,
            "critical_failures",
            "Calls with a critical failure marked failed",
            crit_fail_caught / max(1, crit_fail_human),
            1.0,
            "min",
        ),
        Gate(
            SUITE,
            "worst_item",
            "Worst single-item agreement",
            min(sum(v) / len(v) for v in by_item.values()),
            0.80,
            "min",
        ),
    ]
    lines = [
        f"{len(pairs)} reviewer verdicts: {len(reviewed_calls())} reviewed calls (every rubric item) and "
        f"{len(labels)} scripted calls (the six beads). Cohen's kappa {kappa:.2f}.",
        "",
        *table(["Reviewed call", "Score", "Band", "Reviewer found"], rows, "---|---:|---|---"),
        "",
        *table(["Rubric item", "Verdicts", "Agreement"], item_rows),
    ]
    return Report(gates, lines, {"agreement": overall, "kappa": kappa, "byItem": {r[0]: r[2] for r in item_rows}})
