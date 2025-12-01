"""The call-quality rubric (docs/API_CONTRACT.md §1.9). Keys are stable; labels are what reviewers see."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RubricItem:
    key: str
    label: str
    description: str
    points: float
    critical: bool  # a failed critical item caps the call at "failed"


RUBRIC: tuple[RubricItem, ...] = (
    RubricItem(
        "consent_first",
        "Consent asked first",
        "Recording consent was asked before any question about the loss.",
        15,
        True,
    ),
    RubricItem(
        "consent_rule",
        "Consent rule followed",
        "The caller's state or province rule was applied (all-party regions need a yes).",
        10,
        True,
    ),
    RubricItem(
        "identity_verified",
        "Caller and policy verified",
        "The policy was found and the caller confirmed one identity detail.",
        10,
        False,
    ),
    RubricItem(
        "required_fields",
        "Required details collected",
        "Every required claim-file field for the loss type has a value.",
        15,
        False,
    ),
    RubricItem(
        "safety_check", "Safety check done", "The caller was asked whether anyone is hurt or in danger.", 10, True
    ),
    RubricItem("read_back", "Summary read back", "The claim summary was read back and confirmed.", 10, False),
    RubricItem(
        "empathy", "Empathy shown", "Acknowledgement phrases were used, especially after distress or injury.", 5, False
    ),
    RubricItem(
        "no_card_numbers",
        "No card numbers kept",
        "No payment card number appears in the transcript, recording or claim file.",
        10,
        True,
    ),
    RubricItem(
        "handoff_correct",
        "Hand-off handled correctly",
        "A person was offered or reached whenever a hand-off rule applied.",
        10,
        True,
    ),
    RubricItem(
        "language_honoured",
        "Caller's language honoured",
        "The call continued in the caller's language (French first in Quebec).",
        5,
        False,
    ),
    RubricItem(
        "no_promises",
        "No coverage promises",
        "The line never promised payment or said a claim would be denied.",
        0,
        True,
    ),
)

GOOD_AT = 85.0
NEEDS_ATTENTION_AT = 70.0
