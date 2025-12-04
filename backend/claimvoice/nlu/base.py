"""Protocols for language understanding (NLU) and the raw LLM client it may use."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class Intent(StrEnum):
    ANSWER = "answer"  # gives information for the pending question(s)
    AFFIRM = "affirm"
    DENY = "deny"
    CORRECTION = "correction"  # "no, it was Tuesday, not Monday"
    HANDOFF_REQUEST = "handoff_request"  # asks for a person
    REPEAT = "repeat"
    OFF_SCRIPT = "off_script"  # a question or remark outside the script
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SlotSpec:
    """A value the current stage is waiting for. `kind` drives parsing: text, date, time, yes_no, phone, number,
    choice (with `choices`), address, policy_number, money_band."""

    key: str
    kind: str
    required: bool = True
    choices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SlotValue:
    key: str
    value: Any  # normalised: ISO date for dates, bool for yes_no, E.164 for phones, choice key for choices
    display: str  # how it reads in the claim file ("Tuesday 6 January, about 4 pm")
    confidence: float
    span: tuple[int, int]  # character offsets into the (redacted) utterance the value was heard in
    corrects: bool = False  # replaces an earlier value for the same key


@dataclass(frozen=True, slots=True)
class NluRequest:
    stage: str
    utterance: str  # already redacted (card numbers removed)
    language: str  # "en" | "fr"
    expecting: Sequence[SlotSpec]
    filled: Mapping[str, Any] = field(default_factory=dict)
    recent_turns: Sequence[tuple[str, str]] = ()  # (speaker, text), newest last, at most 6
    loss_type: str | None = None
    asked: str | None = None  # the field the line's last question asked for (gets the lenient reading)
    now: datetime | None = None  # business time of the turn (dates like "yesterday" resolve against it)
    region: str | None = None  # ISO 3166-2; completes a policy number said without its region letters


@dataclass(frozen=True, slots=True)
class NluResult:
    intent: Intent
    slots: tuple[SlotValue, ...] = ()
    language: str | None = None  # detected language when it differs from the request
    distress: float = 0.0  # 0..1, from wording only (never from voice, accent or speech rate)
    urgent_safety: bool = False  # injury, fire, gas, someone in danger, water near electrical panel
    safety_reason: str | None = None
    confidence: float = 1.0
    source: str = "fake"  # "fake" | "llm"
    topic: str | None = None  # off-script topic ("premium", "covered", "timeline", "robot", ...) for a fixed answer


@runtime_checkable
class LanguageUnderstanding(Protocol):
    async def understand(self, request: NluRequest) -> NluResult: ...


@runtime_checkable
class LlmClient(Protocol):
    """Raw completion client (LiteLLM in production). Used by the cloud NLU, the call summary and the QA language
    checks. Always called with a timeout; callers fall back to the rules path on timeout or error."""

    name: str

    async def complete(
        self,
        system: str,
        user: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        timeout_ms: int = 600,
        temperature: float = 0.0,
    ) -> str: ...
