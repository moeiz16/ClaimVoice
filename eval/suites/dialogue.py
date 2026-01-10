"""Dialogue suite: every scripted caller in eval/callers/ through the real engine (offline understanding).

Gates: task completion, per-field value accuracy, safety and hand-off triggers caught, consent always first, nothing
kept before consent in all-party regions, card numbers caught and none stored, barge-ins honoured; the held-out sets
and the wrong-value rate (a value kept that isn't what the caller said), which costs more than asking again."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from common import Gate, Report, table

from claimvoice.contracts import MemoryCallSink, Speaker
from claimvoice.dialogue.simulate import load_callers, run_scenario
from claimvoice.nlu.base import LanguageUnderstanding
from claimvoice.nlu.model import loaded
from claimvoice.nlu.offline import OfflineUnderstanding
from claimvoice.nlu.redaction import contains_card_number
from claimvoice.qa.scorer import check_consent_first

SUITE = "dialogue"
TODAY = "2026-01-08"


CALLERS = Path(__file__).resolve().parents[1] / "callers"
HELD_OUT = CALLERS / "held_out"
HELD_OUT_2 = CALLERS / "held_out_2"
HELD_OUT_3 = CALLERS / "held_out_3"
# The rules-only reader on each set, measured before the learned reader was built (fixed; the same callers, the same
# engine). Set 3 was written and committed before any reader change and scored once then, as the baseline.
BEFORE: dict[str, dict[str, int]] = {
    "main": {"completed": 38, "of": 38, "values": 126, "wrong": 0, "valuesOf": 126},
    "held_out": {"completed": 8, "of": 8, "values": 20, "wrong": 0, "valuesOf": 20},
    "held_out_2": {"completed": 1, "of": 8, "values": 0, "wrong": 0, "valuesOf": 22},
    "held_out_3": {"completed": 1, "of": 12, "values": 24, "wrong": 2, "valuesOf": 62},
}
# Set 3 gates, set after its single final run (8 of 12 completed, 50 of 62 values, 1 wrong): modest floors, well
# above the rules-only baseline (1 of 12, 24 of 62, 2 wrong) and below the result, so they catch a regression without
# being fitted to it.
HELD_OUT_3_MIN_COMPLETED = 0.5
HELD_OUT_3_MIN_VALUES = 0.75
HELD_OUT_3_MAX_WRONG = 0.05
HELD_OUT_3_NOTE = (
    "Of the four calls that did not finish as expected, two English calls were handed to a person after two turns in "
    "a row the line could not place (it asks again first, then brings in a person rather than keep a guess), and two "
    "French calls kept every expected value but fell out of step with their scripted answers and ran out of lines "
    "before the call reached its end. The one wrong value is in a French water call. The set is small (12 callers, "
    "62 values), so one call moves completion by 8 points."
)


def _score(caller: Any, res: Any, sink: MemoryCallSink) -> dict[str, Any]:
    """The right final stage and hand-off, and each expected value: right, wrong (a different value kept) or missing."""
    exp = caller.expect
    handoffs = [h[0].value for h in sink.of("handoff")]
    done = res.stage_at_end_of_script == exp.get("final_stage", "ended") and (
        (handoffs[0] if handoffs else False) == exp.get("handoff", False)
    )
    hits = wrong = 0
    for k, v in (exp.get("slots") or {}).items():
        want = TODAY if v == "{today}" else v
        got = res.values.get(k)
        hits += got == want
        wrong += got is not None and got != want
    return {"done": done, "hits": hits, "wrong": wrong, "of": len(exp.get("slots") or {}), "handoffs": handoffs}


def _held_out(directory: Path, nlu: LanguageUnderstanding | None = None) -> dict[str, Any]:
    """Score a held-out set the same way as the main set: the right final stage, the right hand-off, the values."""
    rows: list[list[Any]] = []
    completed = hits_all = total_all = wrong_all = 0
    for r in asyncio.run(_run_all(str(directory), nlu)):
        s = _score(r["caller"], r["result"], r["sink"])
        completed += s["done"]
        hits_all += s["hits"]
        wrong_all += s["wrong"]
        total_all += s["of"]
        rows.append(
            [
                r["caller"].key,
                r["caller"].language,
                "yes" if s["done"] else "no",
                f"{s['hits']}/{s['of']}",
                s["wrong"],
                s["handoffs"][0] if s["handoffs"] else "-",
            ]
        )
    return {
        "rows": rows,
        "completed": completed,
        "of": len(rows),
        "values": hits_all,
        "wrong": wrong_all,
        "valuesOf": total_all,
    }


def _summary(ho: dict[str, Any]) -> dict[str, int]:
    return {k: ho[k] for k in ("completed", "of", "values", "wrong", "valuesOf")}


async def _run_all(directory: str | None = None, nlu: LanguageUnderstanding | None = None) -> list[dict[str, Any]]:
    out = []
    for key, caller in load_callers(directory).items():
        sink = MemoryCallSink()
        result = await run_scenario(caller, sink, call_id=f"eval-{key}", nlu=nlu)
        out.append({"key": key, "caller": caller, "result": result, "sink": sink})
    return out


def _reader_latency() -> dict[str, float]:
    """Time per caller turn for the offline reader (rules + classifier) over every caller turn in every set."""
    reader = OfflineUnderstanding()
    model = loaded()
    from claimvoice.dialogue.slots import SLOT_CATALOG
    from claimvoice.nlu.base import NluRequest, SlotSpec

    specs = [SlotSpec(k, d.kind) for k, d in SLOT_CATALOG.items()]
    texts = [t.text for d in (None, HELD_OUT, HELD_OUT_2, HELD_OUT_3) for c in load_callers(str(d) if d else None).values()
             for t in c.turns]  # fmt: skip
    full, clf = [], []
    for text in texts:
        req = NluRequest(stage="loss_type", utterance=text, language="en", expecting=specs, asked="loss_type")
        t0 = time.perf_counter()
        reader.understand_sync(req)
        full.append((time.perf_counter() - t0) * 1000)
        if model is not None:
            t0 = time.perf_counter()
            model.predict(text)
            clf.append((time.perf_counter() - t0) * 1000)
    full.sort()
    clf.sort()

    def p(xs: list[float], q: float) -> float:
        return round(xs[min(len(xs) - 1, round(q * (len(xs) - 1)))], 3) if xs else 0.0

    return {"turns": len(texts), "p50": p(full, 0.5), "p95": p(full, 0.95), "max": p(full, 1.0),
            "clf_p50": p(clf, 0.5), "clf_p95": p(clf, 0.95)}  # fmt: skip


def _stored_texts(sink: MemoryCallSink) -> list[str]:
    """Every piece of caller-derived text the platform would keep (checked one by one, ids excluded)."""
    out: list[str] = []
    for kind, _, payload in sink.events:
        if kind == "turn":
            out.append(payload.text)
        elif kind == "slot":
            out += [str(payload.value), payload.display]
        elif kind == "flag":
            out.append(payload.detail)
        elif kind == "closed":
            out += [payload.summary, payload.summary_en or ""]
    return out


def run() -> Report:
    runs = asyncio.run(_run_all())
    rows, completion, field_hits, field_total, field_wrong = [], [], 0, 0, 0
    safety_hits = safety_total = 0
    consent_ok = 0
    held_ok = held_total = 0
    card_calls = card_caught = 0
    stored_cards = 0
    barge_expected = barge_seen = 0
    french = french_ok = 0
    for r in runs:
        caller, res, sink = r["caller"], r["result"], r["sink"]
        exp = caller.expect
        handoffs = [h[0].value for h in sink.of("handoff")]
        want_handoff = exp.get("handoff", False)
        handoff_ok = (handoffs[0] if handoffs else False) == want_handoff
        stage_ok = res.stage_at_end_of_script == exp.get("final_stage", "ended")
        done = stage_ok and handoff_ok
        completion.append(done)
        scored = _score(caller, res, sink)
        hits, total = scored["hits"], scored["of"]
        field_hits += hits
        field_total += total
        field_wrong += scored["wrong"]
        if want_handoff:
            safety_total += 1
            safety_hits += handoff_ok
        if check_consent_first(turns=res.engine.turns, events=res.engine.events).passed:
            consent_ok += 1
        consent = sink.of("consent")
        if res.engine.consent_rule == "all_party":
            held_total += 1
            first_turn = next((i for i, (k, _, _) in enumerate(sink.events) if k == "turn"), None)
            first_consent = next((i for i, (k, _, _) in enumerate(sink.events) if k == "consent"), None)
            kept_early = (
                first_turn is not None
                and (first_consent is None or first_turn < first_consent)
                and any(t.retained for t in sink.of("turn"))
            )
            held_ok += not kept_early
        if exp.get("card_numbers"):
            card_calls += 1
            removed = sum(t.redactions for t in sink.of("turn"))
            card_caught += removed >= int(exp["card_numbers"])
        stored_cards += any(contains_card_number(t) for t in _stored_texts(sink))
        if exp.get("barge_ins"):
            barge_expected += int(exp["barge_ins"])
            barge_seen += sum(1 for t in sink.of("turn") if t.speaker is Speaker.LINE and t.interrupted)
        if caller.language == "fr" or "french" in caller.tags:
            french += 1
            french_ok += done
        if exp.get("consent"):
            done = done and bool(consent) and consent[-1].answer == exp["consent"]
        rows.append(
            [
                caller.key,
                caller.language,
                "yes" if done else "NO",
                f"{hits}/{total}",
                handoffs[0] if handoffs else "-",
                res.engine.stage.value,
                len(res.engine.turns),
            ]
        )
    n = len(runs)
    ho = _held_out(HELD_OUT)
    ho2 = _held_out(HELD_OUT_2)
    ho3 = _held_out(HELD_OUT_3)
    rules_only = OfflineUnderstanding(use_model=False)
    ablation = {
        "main": _held_out(CALLERS, rules_only),
        "held_out": _held_out(HELD_OUT, rules_only),
        "held_out_2": _held_out(HELD_OUT_2, rules_only),
        "held_out_3": _held_out(HELD_OUT_3, rules_only),
    }
    main = {"completed": sum(completion), "of": n, "values": field_hits, "wrong": field_wrong, "valuesOf": field_total}
    now = {"main": main, "held_out": _summary(ho), "held_out_2": _summary(ho2), "held_out_3": _summary(ho3)}
    dev_wrong = sum(now[k]["wrong"] for k in ("main", "held_out", "held_out_2"))
    dev_values = sum(now[k]["valuesOf"] for k in ("main", "held_out", "held_out_2"))
    latency = _reader_latency()
    gates = [
        Gate(SUITE, "callers", "Scripted callers (EN/FR)", n, 30, "min"),
        Gate(SUITE, "task_completion", "Task completion", sum(completion) / n, 1.0, "min"),
        Gate(SUITE, "value_accuracy", "Per-field value accuracy", field_hits / max(1, field_total), 1.0, "min"),
        Gate(
            SUITE,
            "safety_handoffs",
            "Safety and hand-off triggers caught",
            safety_hits / max(1, safety_total),
            1.0,
            "min",
        ),
        Gate(SUITE, "consent_first", "Consent asked first", consent_ok / n, 1.0, "min"),
        Gate(
            SUITE,
            "all_party_held",
            "All-party calls: nothing kept before the yes",
            held_ok / max(1, held_total),
            1.0,
            "min",
        ),
        Gate(SUITE, "cards_caught", "Card numbers caught and removed", card_caught / max(1, card_calls), 1.0, "min"),
        Gate(SUITE, "cards_stored", "Card numbers stored anywhere", stored_cards, 0, "max"),
        Gate(
            SUITE,
            "barge_in",
            "Barge-ins honoured (line turn marked interrupted)",
            barge_seen / max(1, barge_expected),
            1.0,
            "min",
        ),
        Gate(SUITE, "french", "French calls completed", french_ok / max(1, french), 0.95, "min"),
        Gate(
            SUITE,
            "held_out_completion",
            "Held-out callers, first set, completed",
            ho["completed"] / max(1, ho["of"]),
            1.0,
            "min",
        ),
        Gate(
            SUITE,
            "held_out_2_completion",
            "Held-out callers, second set (used for development), completed",
            ho2["completed"] / max(1, ho2["of"]),
            1.0,
            "min",
        ),
        Gate(
            SUITE,
            "held_out_2_values",
            "Held-out callers, second set (used for development), values right",
            ho2["values"] / max(1, ho2["valuesOf"]),
            1.0,
            "min",
        ),
        Gate(
            SUITE,
            "wrong_values",
            "Wrong values kept, main and development sets (share of expected values)",
            dev_wrong / max(1, dev_values),
            0.02,
            "max",
        ),
        Gate(
            SUITE,
            "held_out_3_completion",
            "Held-out callers, third set (untouched), completed (floor)",
            ho3["completed"] / max(1, ho3["of"]),
            HELD_OUT_3_MIN_COMPLETED,
            "min",
        ),
        Gate(
            SUITE,
            "held_out_3_wrong_values",
            "Wrong values kept, third held-out set (share of expected values)",
            ho3["wrong"] / max(1, ho3["valuesOf"]),
            HELD_OUT_3_MAX_WRONG,
            "max",
        ),
        Gate(
            SUITE,
            "held_out_3_values",
            "Held-out callers, third set (untouched), values right (floor)",
            ho3["values"] / max(1, ho3["valuesOf"]),
            HELD_OUT_3_MIN_VALUES,
            "min",
        ),
        Gate(SUITE, "reader_latency", "Offline reader per caller turn, p95 (ms)", latency["p95"], 5.0, "max"),
    ]

    def before_after(key: str, label: str) -> list[Any]:
        b, a, r = BEFORE[key], now[key], _summary(ablation[key])
        return [
            label,
            f"{b['completed']}/{b['of']}",
            f"{r['completed']}/{r['of']}",
            f"{a['completed']}/{a['of']}",
            f"{b['values']}/{b['valuesOf']}",
            f"{r['values']}/{r['valuesOf']}",
            f"{a['values']}/{a['valuesOf']}",
            f"{b['wrong']} ({b['wrong'] / max(1, b['valuesOf']):.1%})",
            f"{a['wrong']} ({a['wrong'] / max(1, a['valuesOf']):.1%})",
        ]

    lines = [
        "How the offline reader copes with wording, per caller set. *Before* is the rules-only reader the line "
        "shipped with; *lexicons* is the widened rules without the classifier; *now* is rules, lexicons and the "
        "learned loss-type classifier (docs/model-cards/loss-type-reader.md). A wrong value is a value kept that "
        "isn't what the caller said; a missing one means the line asked again or moved on.",
        "",
        *table(
            [
                "Set",
                "Completed before",
                "lexicons",
                "now",
                "Values before",
                "lexicons",
                "now",
                "Wrong before",
                "Wrong now",
            ],
            [
                before_after("main", "Main (38, tuned on)"),
                before_after("held_out", "Held out 1 (8, used once to widen rules)"),
                before_after("held_out_2", "Held out 2 (8, used for development)"),
                before_after("held_out_3", "Held out 3 (12, untouched until the final run)"),
            ],
            "---|---:|---:|---:|---:|---:|---:|---:|---:",
        ),
        "",
        f"Offline reader time per caller turn ({latency['turns']} turns, every set, expecting every field): "
        f"p50 {latency['p50']} ms, p95 {latency['p95']} ms, max {latency['max']} ms; the classifier alone "
        f"p50 {latency['clf_p50']} ms, p95 {latency['clf_p95']} ms.",
        "",
        f"{n} scripted callers ({french} in French), {field_total} expected values, {safety_total} hand-off "
        f"scenarios, {card_calls} card-number calls, {held_total} calls under all-party consent rules.",
        "",
        *table(
            ["Caller", "Lang", "Completed", "Values", "Hand-off", "Final stage", "Turns"],
            rows,
            "---|---|---|---:|---|---|---:",
        ),
        "",
        "Held-out callers, first set (written after the line was finished): "
        f"{ho['completed']} of {ho['of']} completed as expected, {ho['values']} of {ho['valuesOf']} values right. "
        "This set was used once to widen the rules (new ways to describe a collision, night-time hours, a caller "
        "saying the home is fine), so it shows those fixes hold rather than how the line copes with unseen wording.",
        "",
        *table(
            ["Held-out caller", "Lang", "Completed", "Values", "Wrong", "Hand-off"],
            ho["rows"],
            "---|---|---|---:|---:|---",
        ),
        "",
        "Held-out callers, second set: "
        f"{ho2['completed']} of {ho2['of']} completed as expected, {ho2['values']} of {ho2['valuesOf']} values right "
        f"(before the learned reader: {BEFORE['held_out_2']['completed']} of 8, "
        f"{BEFORE['held_out_2']['values']} of 22). This set was used for development: its misses (open wording in "
        'the first sentence, "not yet" for the police, "nothing broken", "that\'s fine" for consent) shaped the '
        "lexicons and the generator's word lists, though none of its sentences is in the training corpus (a test "
        "checks). It shows the fixes hold, not how the line copes with wording it has never seen.",
        "",
        *table(
            ["Held-out caller", "Lang", "Completed", "Values", "Wrong", "Hand-off"],
            ho2["rows"],
            "---|---|---|---:|---:|---",
        ),
        "",
        "Held-out callers, third set (twelve callers written and committed before the learned reader, never used to "
        f"tune anything): {ho3['completed']} of {ho3['of']} completed as expected, {ho3['values']} of "
        f"{ho3['valuesOf']} values right, {ho3['wrong']} wrong (before: {BEFORE['held_out_3']['completed']} of 12, "
        f"{BEFORE['held_out_3']['values']} of 62, {BEFORE['held_out_3']['wrong']} wrong). This is the honest "
        "measure of wording the line has not seen. " + HELD_OUT_3_NOTE,
        "",
        *table(
            ["Held-out caller", "Lang", "Completed", "Values", "Wrong", "Hand-off"],
            ho3["rows"],
            "---|---|---|---:|---:|---",
        ),
    ]
    return Report(
        gates,
        lines,
        {
            "rows": rows,
            "main": main,
            "heldOut": _summary(ho),
            "heldOut2": _summary(ho2),
            "heldOut3": _summary(ho3),
            "before": BEFORE,
            "lexiconsOnly": {k: _summary(v) for k, v in ablation.items()},
            "readerLatencyMs": latency,
        },
    )
