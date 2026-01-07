import pytest

from claimvoice.dialogue.stages import (
    DISPLAY_STEPS,
    GLOBAL_TO_HANDOFF,
    SCRIPT_ORDER,
    STAGE_LABELS,
    STAGE_STEP,
    Event,
    InvalidTransitionError,
    Stage,
    next_stage,
)

HAPPY_PATH = [
    Event.GREETED,
    Event.CONSENT_GIVEN,
    Event.IDENTITY_VERIFIED,
    Event.SAFETY_CLEAR,
    Event.LOSS_TYPE_SET,
    Event.DETAILS_COMPLETE,
    Event.PHOTOS_SENT,
    Event.COVERAGE_EXPLAINED,
    Event.READ_BACK_CONFIRMED,
    Event.WRAP_UP_DONE,
]


def test_happy_path_walks_the_script_in_order():
    stage, seen = Stage.GREETING, [Stage.GREETING]
    for event in HAPPY_PATH:
        stage = next_stage(stage, event).stage
        seen.append(stage)
    assert seen[:-1] == list(SCRIPT_ORDER)
    assert stage is Stage.ENDED


@pytest.mark.parametrize("stage", list(SCRIPT_ORDER))
@pytest.mark.parametrize("event", sorted(GLOBAL_TO_HANDOFF))
def test_hand_off_is_reachable_from_every_stage(stage, event):
    assert next_stage(stage, event).stage is Stage.HANDOFF


def test_hand_back_resumes_the_interrupted_stage():
    assert next_stage(Stage.HANDOFF, Event.HANDOFF_RETURNED, resume_stage=Stage.PHOTOS).stage is Stage.PHOTOS
    with pytest.raises(InvalidTransitionError):
        next_stage(Stage.HANDOFF, Event.HANDOFF_RETURNED)


def test_in_stage_events_never_move_the_call():
    t = next_stage(Stage.LOSS_DETAILS, Event.CARD_NUMBER_DETECTED)
    assert t.stage is Stage.LOSS_DETAILS and not t.changed
    assert next_stage(Stage.READ_BACK, Event.READ_BACK_CORRECTED).stage is Stage.READ_BACK


def test_out_of_order_event_is_rejected():
    with pytest.raises(InvalidTransitionError):
        next_stage(Stage.GREETING, Event.IDENTITY_VERIFIED)
    with pytest.raises(InvalidTransitionError):
        next_stage(Stage.ENDED, Event.GREETED)


def test_every_stage_has_english_and_french_labels():
    for stage in Stage:
        assert set(STAGE_LABELS[stage]) == {"en", "fr"}


def test_seven_display_steps_cover_the_script_in_order():
    steps = [STAGE_STEP[stage] for stage in SCRIPT_ORDER]
    assert steps == sorted(steps)
    assert set(steps) == set(range(1, len(DISPLAY_STEPS) + 1)) == set(range(1, 8))
    assert DISPLAY_STEPS[STAGE_STEP[Stage.SAFETY] - 1]["en"] == "Safety"


def test_a_first_description_reads_as_a_brief_for_the_person_taking_over():
    from claimvoice.dialogue.summary import in_brief

    assert in_brief("Hi, my fence blew down onto my neighbour's car.", "en") == (
        "Their fence blew down onto their neighbour's car"
    )
    assert (
        in_brief("Good morning. So, uh, I smell gas and we're outside.", "en") == "They smell gas and they're outside"
    )
    assert in_brief("Bonjour, mon sous-sol est inondé.", "fr") == "« mon sous-sol est inondé »"
    assert in_brief("Hi.", "en") == ""
