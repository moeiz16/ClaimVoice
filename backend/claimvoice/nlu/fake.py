"""Offline deterministic NLU and LLM fakes (LLM_FAKE=true, the default)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from claimvoice.nlu.base import Intent, NluRequest, NluResult

_HANDOFF = re.compile(
    r"\b(speak|talk) (to|with) (a |an )?(person|human|agent|someone|representative)\b"
    r"|\b(real person|a human)\b|\b(parler|discuter) (à|avec) (une |un |quelqu'un)(personne|agent|humain|conseiller)?",
    re.IGNORECASE,
)
_YES = re.compile(r"^\s*(yes|yeah|yep|sure|correct|that's right|ok(ay)?|oui|d'accord|exact|c'est ça)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|not really|non|pas du tout)\b", re.I)
_REPEAT = re.compile(r"\b(repeat|say that again|pardon|répét(er|ez)|redire)\b", re.I)
_URGENT = re.compile(
    r"\b(bleeding|unconscious|not breathing|on fire|fire|smell gas|gas leak|trapped|ambulance|hurt badly|"
    r"saigne|inconscient|ne respire|feu|incendie|odeur de gaz|fuite de gaz|coincé|ambulance|blessé gravement)\b",
    re.I,
)
_DISTRESS = re.compile(r"\b(panic|scared|terrified|crying|can't cope|panique|peur|terrifié|pleure)\b", re.I)


@dataclass
class FakeUnderstanding:
    """Pattern-based understanding for the common intents and safety words, EN/FR. Slot extraction per loss type is
    added by the dialogue scripts (the fake is deliberately conservative: unknown beats wrong)."""

    async def understand(self, request: NluRequest) -> NluResult:
        text = request.utterance
        urgent = _URGENT.search(text)
        distress = 0.8 if _DISTRESS.search(text) else 0.0
        if _HANDOFF.search(text):
            intent = Intent.HANDOFF_REQUEST
        elif _REPEAT.search(text):
            intent = Intent.REPEAT
        elif _YES.search(text):
            intent = Intent.AFFIRM
        elif _NO.search(text):
            intent = Intent.DENY
        elif text.strip():
            intent = Intent.ANSWER
        else:
            intent = Intent.UNKNOWN
        return NluResult(
            intent=intent,
            distress=distress,
            urgent_safety=bool(urgent),
            safety_reason=urgent.group(0).lower() if urgent else None,
            confidence=0.9 if intent is not Intent.UNKNOWN else 0.2,
        )


@dataclass
class FakeLlm:
    """Deterministic stand-in for the cloud LLM: echoes a stable JSON object (or the `baseline` text supplied by the
    caller) so summaries and QA language checks are reproducible offline."""

    name: str = "fake-llm"

    async def complete(
        self,
        system: str,
        user: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        timeout_ms: int = 600,
        temperature: float = 0.0,
    ) -> str:
        if json_schema is not None:
            return json.dumps({"fake": True})
        marker = "BASELINE:"
        return user.split(marker, 1)[1].strip() if marker in user else ""
