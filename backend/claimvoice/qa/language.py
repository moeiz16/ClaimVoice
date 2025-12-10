"""The language check behind two rubric items: kind words (empathy) and no promises.

Offline the rules decide (fixed phrase lists, EN/FR). With a cloud reader configured, the model also reads the line's
turns and returns `{empathy, promises}`; a promise found by the rules always counts, and a timeout falls back to the
rules. Kind words are expected once the caller has described the loss, and again after an injury or distress."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from claimvoice.contracts import Speaker, TurnRecord
from claimvoice.dialogue.lines import EMPATHY_MARKERS
from claimvoice.nlu.base import LlmClient

PROMISES = re.compile(
    r"\b((you'll|you will|we'll|we will) (be )?(get )?(paid|pay you|cover (it|this|that|everything)|approve)|"
    r"(this|it|that|your claim)( is|'s| will be) (covered|approved|paid)|(i|we) guarantee|guaranteed|"
    r"(won't|will not|isn't|is not) (be )?covered|(claim|it)( is|'s| will be) (denied|rejected)|"
    r"vous serez (payée?|remboursée?)|c'est couvert|(sera|est) (couvert|remboursé|refusé|refusée)|garanti)\b",
    re.I,
)
# A sentence that defers the decision is not a promise: "An adjuster confirms what is covered; nothing is decided."
_DEFERS = re.compile(
    r"\b(can't|cannot|can not|won't decide|not decide|confirm\w*|whether|what's covered|what is covered|if it'?s "
    r"covered|nothing (is|was) decided|ne peux pas|ce qui est couvert|rien n'est décidé|confirmer\w*|"
    r"si c'est couvert)\b",
    re.I,
)


def promises_in(text: str) -> bool:
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        if PROMISES.search(sentence) and not _DEFERS.search(sentence):
            return True
    return False


_EXTRA_KIND = re.compile(r"\b(sorry|désolée?|that must be|ça doit être|i understand|je comprends)\b", re.I)


@dataclass(frozen=True, slots=True)
class LanguageResult:
    empathy: bool | None
    empathy_note: str
    empathy_evidence: tuple[str, ...]
    no_promises: bool
    promises_note: str
    promise_evidence: tuple[str, ...]


class LanguageChecker(Protocol):
    def check(self, turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]]) -> LanguageResult: ...


def _speaking(turns: Sequence[TurnRecord]) -> list[TurnRecord]:
    return [t for t in turns if t.speaker in (Speaker.LINE, Speaker.PERSON)]


class RuleLanguageChecker:
    def check(self, turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]]) -> LanguageResult:
        speaking = _speaking(turns)
        kind = [t for t in speaking if any(m in t.text.lower() for m in EMPATHY_MARKERS) or _EXTRA_KIND.search(t.text)]
        caller_turns = [t for t in turns if t.speaker is Speaker.CALLER]
        distress = any(
            e.get("data", {}).get("kind") in ("distress", "urgent_safety") for e in events if e.get("kind") == "flag"
        )
        if len(caller_turns) < 2 and not distress:
            empathy: bool | None = None
            e_note = "Too short a call to judge."
        elif kind:
            empathy, e_note = True, f"Kind words used {len(kind)} time{'s' if len(kind) > 1 else ''}."
        else:
            empathy, e_note = False, "No acknowledgement of what the caller went through."
        promised = [t for t in speaking if promises_in(t.text)]
        if promised:
            quote = next(
                (PROMISES.search(x) for x in re.split(r"(?<=[.!?;])\s+", promised[0].text) if promises_in(x)), None
            )
            p_note = f'Promised an outcome: "{quote.group(0) if quote else ""}".'
        else:
            p_note = "No payment promised and no claim decision given."
        return LanguageResult(
            empathy,
            e_note,
            tuple(t.turn_id for t in kind[:2]),
            not promised,
            p_note,
            tuple(t.turn_id for t in promised[:1]),
        )


class LlmLanguageChecker:
    """Rules first; a cloud model adds a second reading of kind words. Promises found by rules always count."""

    def __init__(self, llm: LlmClient, timeout_ms: int = 1500) -> None:
        self.llm, self.timeout_ms, self.rules = llm, timeout_ms, RuleLanguageChecker()

    def check(self, turns: Sequence[TurnRecord], events: Sequence[Mapping[str, Any]]) -> LanguageResult:
        base = self.rules.check(turns, events)
        text = "\n".join(f"{t.speaker.value}: {t.text}" for t in turns[:80])
        out: dict[str, Any] = {}

        def run() -> None:
            async def ask() -> str:
                return await self.llm.complete(
                    'You review an insurance claim call. Return JSON {"empathy": bool, "promises": bool}: '
                    "empathy = the agent acknowledged the caller's situation kindly; promises = the agent promised "
                    "payment or said the claim would be approved or denied.",
                    text,
                    json_schema={"type": "object"},
                    timeout_ms=self.timeout_ms,
                )

            with contextlib.suppress(Exception):  # the rules already answered
                out.update(json.loads(asyncio.run(ask())))

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(self.timeout_ms / 1000 + 0.2)
        if "empathy" not in out:
            return base
        empathy = base.empathy if base.empathy is None else bool(out.get("empathy")) or bool(base.empathy)
        promises_ok = base.no_promises and not bool(out.get("promises"))
        return LanguageResult(
            empathy,
            base.empathy_note,
            base.empathy_evidence,
            promises_ok,
            base.promises_note
            if base.no_promises == promises_ok
            else "The reviewer model read a promise of an outcome.",
            base.promise_evidence,
        )
