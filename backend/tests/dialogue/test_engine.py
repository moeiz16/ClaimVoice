"""The dialogue engine end to end, through scripted callers and the in-memory sink."""

from __future__ import annotations

import pytest

from claimvoice.contracts import HandoffReason, MemoryCallSink, Speaker
from claimvoice.dialogue.fakes import MemoryPolicyDirectory, YamlPlaybook
from claimvoice.dialogue.machine import EndedOut, HushOut, Say, StopOut, whisper_to_question
from claimvoice.dialogue.simulate import load_callers, run_scenario
from claimvoice.dialogue.stages import Stage
from claimvoice.nlu.redaction import REDACTED, contains_card_number

from .helpers import GORD_START, call


def turns(sink: MemoryCallSink):
    return sink.of("turn")


def line_texts(result) -> list[str]:
    return [o.text for o in result.outs if isinstance(o, Say)]


@pytest.mark.parametrize("key", ["calgary-windstorm", "denver-rear-end", "montreal-basement"])
async def test_the_demo_callers_finish_their_claims(key):
    result = await run_scenario(key, MemoryCallSink())
    caller = load_callers()[key]
    assert result.engine.stage is Stage.ENDED and result.engine.end_reason == "completed"
    for slot, want in caller.expect.get("slots", {}).items():
        got = result.values.get(slot)
        if want == "{today}":
            want = "2026-01-08"
        assert got == want, slot


async def test_consent_is_asked_first_and_nothing_is_kept_before_the_yes():
    sink = MemoryCallSink()
    result, _ = await call(GORD_START[:1], sink=sink, hang_up=False)
    first = line_texts(result)[0]
    assert "recorded" in first and first.endswith("Is that okay? Pour le français, répondez simplement en français.")
    assert turns(sink) == [] and sink.of("slot") == []  # all-party region: held until the caller agrees
    assert result.engine.values()["loss_type"] == "wind"  # but the line already understood


async def test_held_turns_are_released_in_order_once_consent_is_given():
    _result, sink = await call(GORD_START[:2], hang_up=False)
    kinds = [k for k, _, _ in sink.events if k in ("turn", "consent", "slot")]
    assert kinds[0] == "consent"
    seqs = [t.seq for t in turns(sink)]
    assert seqs == sorted(seqs) and len(seqs) >= 3 and all(t.retained for t in turns(sink))


async def test_consent_refused_stops_recording_and_offers_a_person():
    result, sink = await call(["No, I don't want to be recorded.", "Yes, a person please."])
    assert sink.of("consent")[0].answer == "refused"
    assert all(not t.retained for t in turns(sink))
    assert [h[0] for h in sink.of("handoff")] == [HandoffReason.CONSENT_REFUSED]
    assert any("stopped recording" in t for t in line_texts(result))


async def test_one_party_region_records_from_the_first_word():
    _result, sink = await call(["Hey, I just got rear-ended on Colfax."], region="US-CO", hang_up=False)
    assert turns(sink) and turns(sink)[0].speaker is Speaker.LINE


async def test_urgent_safety_outranks_consent():
    result, sink = await call(["I smell gas, the wind tore the cover off my gas meter."])
    assert [h[0] for h in sink.of("handoff")] == [HandoffReason.URGENT_SAFETY]
    assert any(f.kind.value == "urgent_safety" for f in sink.of("flag"))
    assert "call 911" in line_texts(result)[-1]
    assert result.engine.values()["danger_now"] is True


async def test_asking_for_a_person_hands_off_at_once_in_either_language():
    _, sink = await call([*GORD_START[:2], "Can I just talk to a real person?"])
    assert sink.of("handoff")[0][0] is HandoffReason.CALLER_ASKED
    _, sink_fr = await call(["Bonjour, je veux parler à quelqu'un."], region="CA-QC")
    assert sink_fr.of("handoff")[0][0] is HandoffReason.CALLER_ASKED


async def test_card_numbers_are_removed_before_anything_is_stored():
    lines = [*GORD_START, "Everyone's fine. Do you need my card? It's 4111 1111 1111 1111."]
    result, sink = await call(lines)
    caller_turn = [t for t in turns(sink) if t.speaker is Speaker.CALLER][-1]
    assert REDACTED in caller_turn.text and caller_turn.redactions == 1
    assert any(isinstance(o, HushOut) for o in result.outs)
    assert any(f.kind.value == "card_number_removed" for f in sink.of("flag"))
    assert any("never take card numbers" in t for t in line_texts(result))
    texts = [t.text for t in sink.of("turn")] + [f"{x.value} {x.display}" for x in sink.of("slot")]
    assert "4111" not in repr(sink.events)
    assert not any(contains_card_number(t) for t in texts)


async def test_corrections_keep_history_and_count_as_story_changes():
    result = await run_scenario("calgary-windstorm", MemoryCallSink())
    t = result.engine.slots["loss_time"]
    assert t.value == "02:30" and t.history and t.history[0][0] == "02:00"
    assert result.engine.corrections_key_facts == 1
    assert any("changed that to about 2:30 a.m." in s for s in line_texts(result))


async def test_barge_in_marks_the_line_turn_interrupted():
    _, sink = await call([*GORD_START[:1], {"text": "Yes, that's fine.", "barge_in_after_ms": 500}], hang_up=False)
    line_turns = [t for t in turns(sink) if t.speaker is Speaker.LINE]
    assert line_turns[1].interrupted is True  # the consent re-ask was cut off


async def test_every_heard_value_points_at_its_words():
    result, _sink = await run_scenario("denver-rear-end", MemoryCallSink()), None
    by_id = {t.turn_id: t for t in result.engine.turns}
    heard = [s for s in result.engine.slots.values() if s.source == "heard" and s.span]
    assert len(heard) >= 8
    for s in heard:
        text = by_id[s.turn_id].text
        assert 0 <= s.span[0] < s.span[1] <= len(text), s.key


async def test_identity_fails_after_three_attempts():
    lines = ["Hi, my fence blew down.", "Yes.", "LM-AB-204118", "January 1st, 1999", "T2T 2T2", "June 5th, 1980"]
    _, sink = await call(lines)
    assert sink.of("handoff")[0][0] is HandoffReason.IDENTITY_UNVERIFIED


async def test_policy_lookup_failing_twice_hands_off():
    sink = MemoryCallSink()
    _, _ = await call(
        ["Hi, my fence blew down.", "Yes.", "LM-AB-204118", "LM-AB-204118"],
        sink=sink,
        policies=MemoryPolicyDirectory(fail=True),
    )
    assert sink.of("handoff")[0][0] is HandoffReason.TOOL_FAILED
    assert [r.ok for r in sink.of("tool")][:2] == [False, False]


async def test_slow_policy_lookup_times_out_within_budget():
    sink = MemoryCallSink()
    await call(
        ["Hi, my fence blew down.", "Yes.", "LM-AB-204118"],
        sink=sink,
        hang_up=False,
        policies=MemoryPolicyDirectory(delay_ms=900),
    )
    rec = sink.of("tool")[0]
    assert rec.timed_out and rec.elapsed_ms < 600


async def test_two_turns_not_understood_hand_off():
    _, sink = await call([*GORD_START[:2], "hmm", "mmm"])
    assert sink.of("handoff")[0][0] is HandoffReason.LOW_CONFIDENCE


async def test_strong_distress_hands_off_with_kind_words():
    result, sink = await call([*GORD_START, "I can't cope with this, I'm falling apart."])
    assert sink.of("handoff")[0][0] is HandoffReason.DISTRESS
    assert "That sounds like a lot to deal with" in line_texts(result)[-1]


async def test_off_script_question_gets_a_fixed_answer_then_the_question_again():
    result, _ = await call([*GORD_START, "Everyone is fine.", "Will my rates go up?"], hang_up=False)
    last = line_texts(result)[-1]
    assert last.startswith("I can't say how a claim affects your premium") and last.endswith("?")


async def test_caller_can_switch_to_french():
    result, sink = await call(
        [*GORD_START, "Excusez-moi, je préfère continuer en français s'il vous plaît."], hang_up=False
    )
    assert result.engine.language == "fr"
    assert any(f.kind.value == "language_switched" for f in sink.of("flag"))


async def test_whisper_becomes_one_question_the_caller_hears_in_plain_words():
    sink = MemoryCallSink()
    result = await run_scenario(
        "calgary-windstorm", sink, whisper_before_turn={8: "Ask if the garage skylight is damaged too"}
    )
    asked = [t for t in line_texts(result) if "garage skylight" in t]
    assert asked and asked[0].startswith("One more question: Is the garage skylight damaged too?")
    assert not any("Ask if" in t for t in line_texts(result))
    assert "garage skylight" in result.engine.values().get("extra_notes", "")


def test_whisper_to_question():
    assert whisper_to_question("Ask if the garage skylight is damaged too") == "Is the garage skylight damaged too?"
    assert whisper_to_question("ask whether the fence is down") == "Is the fence down?"
    assert whisper_to_question("Ask about the fence") == "Can you tell me about the fence?"


async def test_take_over_say_and_hand_back_resume_the_interrupted_stage():
    result, sink = await call([*GORD_START, "Everyone is fine."], hang_up=False)
    engine = result.engine
    stage_before = engine.stage
    await engine.take_over(user_id="u1", name="Renée Kowalchuk")
    assert engine.stage is Stage.HANDOFF
    _turn_id, outs = await engine.say_as_person(
        "Hi Gord, it's Renée from Larkspur.", user_id="u1", name="Renée Kowalchuk"
    )
    assert any(isinstance(o, Say) and o.speaker == "person" for o in outs)
    await engine.caller_turn("Hi Renée.")  # the line stays quiet but keeps taking notes
    outs = await engine.hand_back(user_id="u1")
    assert engine.stage is stage_before
    assert any(isinstance(o, Say) and "Let's carry on" in o.text for o in outs)
    person = [t for t in turns(sink) if t.speaker is Speaker.PERSON]
    assert person and person[0].speaker_name == "Renée Kowalchuk"


async def test_take_over_stops_the_line_mid_sentence():
    result, _ = await call(GORD_START[:2], hang_up=False)
    outs = await result.engine.take_over(user_id="u1", name="Renée")
    assert any(isinstance(o, StopOut) and o.reason == "takeover" for o in outs)


async def test_waiting_too_long_offers_a_call_back():
    result, _sink = await call([*GORD_START[:2], "I want a human."], hang_up=False)
    outs = await result.engine.handoff_timeout()
    assert any("call back" in o.text for o in outs if isinstance(o, Say))
    outs = await result.engine.caller_turn("Yes, call me back please.")
    assert any(isinstance(o, EndedOut) and o.reason == "callback_requested" for o in outs)


async def test_urgent_safety_never_falls_back_to_a_call_back():
    result, _ = await call(["There's a gas leak in my kitchen!"], hang_up=False)
    assert await result.engine.handoff_timeout() == []


async def test_silence_reprompts_twice_then_ends():
    result, sink = await call(GORD_START[:2], hang_up=False)
    for _ in range(2):
        await result.engine.silence()
    assert not result.engine.ended
    await result.engine.silence()
    assert result.engine.ended and sink.of("closed")[0].reason == "silence"


async def test_french_lines_carry_an_english_version_for_staff():
    result = await run_scenario("montreal-basement", MemoryCallSink())
    fr_lines = [t for t in result.engine.turns if t.speaker is Speaker.LINE]
    assert all(t.language == "fr" and t.text_en for t in fr_lines)
    closing = result.engine._closing
    assert closing.summary.startswith("Martine Gagnon a signalé") and closing.summary_en.startswith("Martine")


async def test_surge_questions_are_asked_only_when_switched_on():
    lines = ["Hi, the wind damaged my roof.", "Yes.", "LM-AB-204118", "March third, 1971.", "Nobody's hurt."]
    off, _ = await call(lines, hang_up=False, playbook=YamlPlaybook(surge_questions_on=False))
    on, _ = await call(lines, hang_up=False, playbook=YamlPlaybook(surge_questions_on=True))
    assert on.engine.surge_questions and not off.engine.surge_questions
    for result in (on, off):  # pretend every ordinary question is answered
        for q in result.engine.script.questions:
            if not q.surge_only:
                result.engine.slots[q.slot_key] = result.engine.slots.get("injury_reported")
    assert on.engine._next_question().slot_key == "power_out"
    assert off.engine._next_question() is None


async def test_wrap_up_reads_the_reserved_claim_number():
    _result, sink = await call([], hang_up=False)
    full = await run_scenario("denver-rear-end", sink)
    number = sink.of("claim_number")[0]
    assert any(number in t for t in line_texts(full))
    ended = [o for o in full.outs if isinstance(o, EndedOut)]
    assert ended and ended[0].claim_number == number


async def test_times_are_read_in_the_callers_zone_on_a_live_call():
    """A live call's clock is UTC; "ten past two" at 7:50 a.m. in Calgary (14:50 UTC) is 2:10 a.m., not p.m."""
    from datetime import UTC, datetime

    res = await run_scenario("dana-skylight", answered_at=datetime(2026, 1, 8, 14, 50, tzinfo=UTC))
    assert res.values["loss_time"] == "02:10"
    assert res.values["loss_date"] == "2026-01-08"
    late = await run_scenario(
        "dana-skylight", answered_at=datetime(2026, 1, 9, 5, 30, tzinfo=UTC)
    )  # 10:30 p.m. on the 8th
    assert late.values["loss_date"] == "2026-01-08"


async def test_an_announcement_that_already_asks_is_not_followed_by_a_second_question():
    from claimvoice.contracts import ConsentRule

    class AskingPlaybook(YamlPlaybook):
        async def consent_rule(self, org_id: str, region: str) -> ConsentRule:
            asks = {"en": "This call is recorded to help with your claim. Is that okay with you?", "fr": "D'accord?"}
            return ConsentRule(region, "all_party", asks)

    res = await run_scenario("dana-skylight", playbook=AskingPlaybook(), upto_caller_turn=0)
    first = next(o.text for o in res.outs if isinstance(o, Say))
    assert "Is that okay with you?" in first and "Is that okay with you? Is that okay?" not in first
