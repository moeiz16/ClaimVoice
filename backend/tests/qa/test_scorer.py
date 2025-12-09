"""Call-quality scorer: rubric items on engine calls and on reviewed calls with known problems."""

from __future__ import annotations

import pytest

from claimvoice.contracts import CallScorer, MemoryCallSink
from claimvoice.dialogue.simulate import run_scenario
from claimvoice.qa.fixtures import reviewed_calls
from claimvoice.qa.language import PROMISES, RuleLanguageChecker
from claimvoice.qa.rubric import RUBRIC
from claimvoice.qa.scorer import events_from_engine, get_call_scorer, slots_from_engine

WORD = {True: "pass", False: "fail", None: "na"}


def test_scorer_satisfies_the_protocol_and_covers_the_rubric():
    scorer = get_call_scorer()
    assert isinstance(scorer, CallScorer)
    call = reviewed_calls()["missed-consent"]
    res = scorer.score(call.turns, call.events, call.slots)
    assert [i.key for i in res.items] == [r.key for r in RUBRIC]


async def test_a_good_engine_call_scores_well_with_evidence():
    result = await run_scenario("calgary-windstorm", MemoryCallSink())
    e = result.engine
    res = get_call_scorer().score(e.turns, events_from_engine(e), slots_from_engine(e))
    assert res.band == "good" and res.score == 100
    consent = next(i for i in res.items if i.key == "consent_first")
    assert consent.passed and consent.evidence_turn_ids == (e.turns[0].turn_id,)


async def test_urgent_call_is_queued_because_a_hand_off_rule_applied():
    result = await run_scenario("airdrie-gas", MemoryCallSink())
    e = result.engine
    res = get_call_scorer().score(e.turns, events_from_engine(e), slots_from_engine(e))
    handoff = next(i for i in res.items if i.key == "handoff_correct")
    assert handoff.passed and res.needs_review


@pytest.mark.parametrize("key", list(reviewed_calls()))
def test_reviewed_calls_match_the_reviewer(key):
    call = reviewed_calls()[key]
    verdicts = get_call_scorer().verdicts(call.turns, call.events, call.slots)
    assert {k: WORD[verdicts[k].passed] for k in call.labels} == call.labels


def test_a_failed_critical_item_fails_the_call_whatever_the_score():
    call = reviewed_calls()["promised-payment"]
    res = get_call_scorer().score(call.turns, call.events, call.slots)
    assert res.score >= 85 and res.band == "failed" and res.needs_review


def test_late_hand_off_says_how_late():
    call = reviewed_calls()["late-handoff"]
    item = next(
        i for i in get_call_scorer().score(call.turns, call.events, call.slots).items if i.key == "handoff_correct"
    )
    assert item.passed is False and "41 seconds late" in item.note


def test_promise_wording():
    assert PROMISES.search("Don't worry, this is covered.")
    assert PROMISES.search("Ce sera remboursé, c'est couvert.")
    assert not PROMISES.search("I can't make a decision on the claim. An adjuster confirms the details.")
    assert RuleLanguageChecker  # used offline
