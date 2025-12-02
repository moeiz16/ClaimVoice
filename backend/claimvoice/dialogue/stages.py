"""The call script as an explicit state machine: stages, events and the transition table (docs/API_CONTRACT.md Part 5).

Control flow lives here and only here. Language understanding (claimvoice.nlu) turns an utterance into an intent and
slot values *inside* the current stage; it never chooses the next stage. The dialogue engine
(`claimvoice.dialogue.machine`) feeds events into `next_stage` and acts on the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    GREETING = "greeting"
    CONSENT = "consent"
    IDENTITY = "identity"  # caller and policy verification
    SAFETY = "safety"  # asked as soon as the caller is identified; urgent safety is also watched on every turn
    LOSS_TYPE = "loss_type"
    LOSS_DETAILS = "loss_details"  # loss-specific questions from the script for that loss type
    PHOTOS = "photos"
    COVERAGE = "coverage"  # coverage basics: what the policy includes, deductible, next steps; never a decision
    READ_BACK = "read_back"  # summary read back to the caller for confirmation
    WRAP_UP = "wrap_up"
    HANDOFF = "handoff"  # waiting for, or talking to, a person
    ENDED = "ended"


# The scripted path, in order. HANDOFF and ENDED are reachable from any active stage.
SCRIPT_ORDER: tuple[Stage, ...] = (
    Stage.GREETING,
    Stage.CONSENT,
    Stage.IDENTITY,
    Stage.SAFETY,
    Stage.LOSS_TYPE,
    Stage.LOSS_DETAILS,
    Stage.PHOTOS,
    Stage.COVERAGE,
    Stage.READ_BACK,
    Stage.WRAP_UP,
)

STAGE_LABELS: dict[Stage, dict[str, str]] = {
    Stage.GREETING: {"en": "Greeting", "fr": "Accueil"},
    Stage.CONSENT: {"en": "Recording consent", "fr": "Consentement à l'enregistrement"},
    Stage.IDENTITY: {"en": "Caller and policy", "fr": "Appelant et police"},
    Stage.LOSS_TYPE: {"en": "What happened", "fr": "Ce qui s'est passé"},
    Stage.LOSS_DETAILS: {"en": "Details", "fr": "Détails"},
    Stage.SAFETY: {"en": "Safety check", "fr": "Vérification de sécurité"},
    Stage.PHOTOS: {"en": "Photos", "fr": "Photos"},
    Stage.COVERAGE: {"en": "Coverage basics", "fr": "Couverture"},
    Stage.READ_BACK: {"en": "Read-back", "fr": "Relecture"},
    Stage.WRAP_UP: {"en": "Wrap-up", "fr": "Conclusion"},
    Stage.HANDOFF: {"en": "With a person", "fr": "Avec une personne"},
    Stage.ENDED: {"en": "Ended", "fr": "Terminé"},
}


# The seven steps people see (the script track on a line and the progress on the switchboard). Several stages share a
# step: greeting and consent are "Consent", what happened and its details are "What happened", read-back and wrap-up
# are "Read-back". Hand-off and ended keep the step they interrupted.
DISPLAY_STEPS: tuple[dict[str, str], ...] = (
    {"en": "Consent", "fr": "Consentement"},
    {"en": "Policy", "fr": "Police"},
    {"en": "Safety", "fr": "Sécurité"},
    {"en": "What happened", "fr": "Ce qui s'est passé"},
    {"en": "Photos", "fr": "Photos"},
    {"en": "Coverage", "fr": "Couverture"},
    {"en": "Read-back", "fr": "Relecture"},
)
STAGE_STEP: dict[Stage, int] = {  # 1-based step number
    Stage.GREETING: 1,
    Stage.CONSENT: 1,
    Stage.IDENTITY: 2,
    Stage.SAFETY: 3,
    Stage.LOSS_TYPE: 4,
    Stage.LOSS_DETAILS: 4,
    Stage.PHOTOS: 5,
    Stage.COVERAGE: 6,
    Stage.READ_BACK: 7,
    Stage.WRAP_UP: 7,
}


class Event(StrEnum):
    # stage-local outcomes (emitted by the engine when a stage's required slots and confirmations are complete)
    GREETED = "greeted"
    CONSENT_GIVEN = "consent_given"
    CONSENT_REFUSED = "consent_refused"  # call continues unrecorded; transcript not kept; a person is offered
    IDENTITY_VERIFIED = "identity_verified"
    IDENTITY_FAILED = "identity_failed"  # after the configured attempts (default 3)
    LOSS_TYPE_SET = "loss_type_set"
    DETAILS_COMPLETE = "details_complete"
    SAFETY_CLEAR = "safety_clear"
    PHOTOS_SENT = "photos_sent"
    PHOTOS_DECLINED = "photos_declined"
    COVERAGE_EXPLAINED = "coverage_explained"
    READ_BACK_CONFIRMED = "read_back_confirmed"
    READ_BACK_CORRECTED = "read_back_corrected"  # stays in READ_BACK; only the corrected items are read again
    WRAP_UP_DONE = "wrap_up_done"
    # global: valid in every active stage
    URGENT_SAFETY = "urgent_safety"  # injury, fire, gas, flooding near power, someone in danger
    HANDOFF_REQUESTED = "handoff_requested"  # caller asks for a person
    LOW_CONFIDENCE = "low_confidence"  # N consecutive turns not understood (hand-off rules)
    DISTRESS_DETECTED = "distress_detected"
    TOOL_FAILED = "tool_failed"  # a required tool (policy lookup) failed or timed out twice
    SUPERVISOR_TAKEOVER = "supervisor_takeover"
    CALLER_HUNG_UP = "caller_hung_up"
    SILENCE_TIMEOUT = "silence_timeout"  # two re-prompts with no answer
    # hand-off stage only
    HANDOFF_COMPLETED = "handoff_completed"  # the person finished the call
    HANDOFF_RETURNED = "handoff_returned"  # the person handed the call back to the voice line
    # in-stage, no transition (handled by the engine, listed so every event has one meaning)
    SLOT_CORRECTED = "slot_corrected"
    CARD_NUMBER_DETECTED = "card_number_detected"  # digits redacted, recording paused for that segment, caller told
    LANGUAGE_SWITCHED = "language_switched"
    OFF_SCRIPT = "off_script"  # brief answer or "I'll note that", then the pending question again
    REPEAT_REQUESTED = "repeat_requested"
    BARGE_IN = "barge_in"  # caller spoke over the line: stop speaking, listen
    WHISPER_RECEIVED = "whisper_received"  # supervisor note; may add a question to the current stage


GLOBAL_TO_HANDOFF = frozenset(
    {
        Event.URGENT_SAFETY,
        Event.HANDOFF_REQUESTED,
        Event.LOW_CONFIDENCE,
        Event.DISTRESS_DETECTED,
        Event.TOOL_FAILED,
        Event.SUPERVISOR_TAKEOVER,
    }
)
GLOBAL_TO_ENDED = frozenset({Event.CALLER_HUNG_UP, Event.SILENCE_TIMEOUT})
IN_STAGE = frozenset(
    {
        Event.SLOT_CORRECTED,
        Event.CARD_NUMBER_DETECTED,
        Event.LANGUAGE_SWITCHED,
        Event.OFF_SCRIPT,
        Event.REPEAT_REQUESTED,
        Event.BARGE_IN,
        Event.WHISPER_RECEIVED,
        Event.READ_BACK_CORRECTED,
    }
)

TRANSITIONS: dict[tuple[Stage, Event], Stage] = {
    (Stage.GREETING, Event.GREETED): Stage.CONSENT,
    (Stage.CONSENT, Event.CONSENT_GIVEN): Stage.IDENTITY,
    (Stage.CONSENT, Event.CONSENT_REFUSED): Stage.IDENTITY,
    (Stage.IDENTITY, Event.IDENTITY_VERIFIED): Stage.SAFETY,
    (Stage.IDENTITY, Event.IDENTITY_FAILED): Stage.HANDOFF,
    (Stage.LOSS_TYPE, Event.LOSS_TYPE_SET): Stage.LOSS_DETAILS,
    (Stage.SAFETY, Event.SAFETY_CLEAR): Stage.LOSS_TYPE,
    (Stage.LOSS_DETAILS, Event.DETAILS_COMPLETE): Stage.PHOTOS,
    (Stage.PHOTOS, Event.PHOTOS_SENT): Stage.COVERAGE,
    (Stage.PHOTOS, Event.PHOTOS_DECLINED): Stage.COVERAGE,
    (Stage.COVERAGE, Event.COVERAGE_EXPLAINED): Stage.READ_BACK,
    (Stage.READ_BACK, Event.READ_BACK_CONFIRMED): Stage.WRAP_UP,
    (Stage.WRAP_UP, Event.WRAP_UP_DONE): Stage.ENDED,
    (Stage.HANDOFF, Event.HANDOFF_COMPLETED): Stage.ENDED,
}


class InvalidTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Transition:
    previous: Stage
    stage: Stage
    event: Event
    changed: bool


def next_stage(stage: Stage, event: Event, *, resume_stage: Stage | None = None) -> Transition:
    """Apply one event. `resume_stage` is where HANDOFF_RETURNED goes back to (the stage the hand-off interrupted).

    Raises InvalidTransitionError for an event that has no meaning in this stage (the engine logs it and stays put).
    """
    if stage is Stage.ENDED:
        raise InvalidTransitionError(f"call already ended (event {event})")
    if event in IN_STAGE:
        if event is Event.READ_BACK_CORRECTED and stage is not Stage.READ_BACK:
            raise InvalidTransitionError("a read-back correction outside the read-back")
        return Transition(stage, stage, event, False)
    if event in GLOBAL_TO_ENDED:
        return Transition(stage, Stage.ENDED, event, True)
    if event in GLOBAL_TO_HANDOFF:
        if stage is Stage.HANDOFF:
            return Transition(stage, stage, event, False)
        return Transition(stage, Stage.HANDOFF, event, True)
    if stage is Stage.HANDOFF and event is Event.HANDOFF_RETURNED:
        if resume_stage is None or resume_stage in (Stage.HANDOFF, Stage.ENDED):
            raise InvalidTransitionError("hand-back needs the stage the hand-off interrupted")
        return Transition(stage, resume_stage, event, True)
    target = TRANSITIONS.get((stage, event))
    if target is None:
        raise InvalidTransitionError(f"{event} is not valid in {stage}")
    return Transition(stage, target, event, target is not stage)
