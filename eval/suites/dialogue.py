"""Dialogue suite: every scripted caller in eval/callers/ through the real engine (offline understanding).

Gates: task completion, per-field value accuracy, safety and hand-off triggers caught, consent always first, nothing
kept before consent in all-party regions, card numbers caught and none stored, barge-ins honoured."""

from __future__ import annotations

import asyncio
from typing import Any

from common import Gate, Report, table

from claimvoice.contracts import MemoryCallSink, Speaker
from claimvoice.dialogue.simulate import load_callers, run_scenario
from claimvoice.nlu.redaction import contains_card_number
from claimvoice.qa.scorer import check_consent_first

SUITE = "dialogue"
TODAY = "2026-01-08"


async def _run_all() -> list[dict[str, Any]]:
    out = []
    for key, caller in load_callers().items():
        sink = MemoryCallSink()
        result = await run_scenario(caller, sink, call_id=f"eval-{key}")
        out.append({"key": key, "caller": caller, "result": result, "sink": sink})
    return out


def _stored_blob(sink: MemoryCallSink) -> str:
    parts: list[str] = []
    for kind, _, payload in sink.events:
        if kind == "turn":
            parts.append(payload.text)
        elif kind == "slot":
            parts.append(f"{payload.value} {payload.display}")
        elif kind in ("flag", "closed"):
            parts.append(repr(payload))
    return "\n".join(parts)


def run() -> Report:
    runs = asyncio.run(_run_all())
    rows, completion, field_hits, field_total = [], [], 0, 0
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
        hits = total = 0
        for k, want in (exp.get("slots") or {}).items():
            want = TODAY if want == "{today}" else want
            total += 1
            hits += res.values.get(k) == want
        field_hits += hits
        field_total += total
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
        stored_cards += contains_card_number(_stored_blob(sink))
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
    gates = [
        Gate(SUITE, "callers", "Scripted callers (EN/FR)", n, 30, "min"),
        Gate(SUITE, "task_completion", "Task completion", sum(completion) / n, 0.95, "min"),
        Gate(SUITE, "value_accuracy", "Per-field value accuracy", field_hits / max(1, field_total), 0.95, "min"),
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
    ]
    lines = [
        f"{n} scripted callers ({french} in French), {field_total} expected values, {safety_total} hand-off "
        f"scenarios, {card_calls} card-number calls, {held_total} calls under all-party consent rules.",
        "",
        *table(
            ["Caller", "Lang", "Completed", "Values", "Hand-off", "Final stage", "Turns"],
            rows,
            "---|---|---|---:|---|---|---:",
        ),
    ]
    return Report(gates, lines, {"rows": rows})
