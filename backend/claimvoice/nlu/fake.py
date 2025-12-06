"""Offline deterministic language understanding and LLM fakes (LLM_FAKE=true, the default).

`FakeUnderstanding` is a full rule-based reader for English and Canadian French: the intent of a turn (an answer,
yes, no, a correction, a request for a person, a repeat, an off-script question, goodbye), urgent-safety words with
negation handled ("nothing's dangerous" is not an alarm), wording-based distress (never voice, accent or speech
rate), the caller's language, and the claim-file values the stage is expecting, each with its transcript span.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from claimvoice import clock
from claimvoice.nlu.base import Intent, NluRequest, NluResult
from claimvoice.nlu.extract import NO, YES, extract_values

_HANDOFF = re.compile(
    r"\b(speak|talk|chat)(ing)? (to|with) (a |an |some )?(real |actual |live )?(person|human|agent|someone|somebody|"
    r"representative|rep|adjuster|operator)\b|\b(real|actual|live) (person|human)\b|\b(get|give|put) me (a |an )?"
    r"(person|human|agent|operator|representative)\b|\bi want (a|an) (person|human|agent)\b|\boperator\b|"
    r"\b(parler|discuter) (à|avec) (une |un |quelqu'un|une vraie|un vrai|un agent|une personne|un humain|"
    r"un conseiller|une conseillère)|\b(une vraie personne|un être humain|je veux parler à quelqu'un)\b",
    re.IGNORECASE,
)
_REPEAT = re.compile(
    r"\b(repeat|say that again|say again|what did you (say|ask)|come again|didn't (catch|hear) (that|you)|"
    r"répét(er|ez)|redire|pouvez-vous répéter|vous dites)\b|^\s*(sorry|pardon|what)\s*\??\s*$",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"^\s*(no|nope|sorry|actually|wait|oops|oh wait|hang on|non|pardon|en fait|désolée?|attendez|oups)\b.*"
    r"\b(it was|it were|more like|i mean|i meant|c'était|plutôt|je veux dire)\b"
    r"|\b(actually it was|i meant|correction|i misspoke|je me suis trompée?|en fait c'était)\b",
    re.IGNORECASE,
)
_GOODBYE = re.compile(
    r"\b(bye|goodbye|that's (all|everything|it)|nothing else|that is all|au revoir|c'est tout|rien d'autre|"
    r"bonne journée)\b",
    re.IGNORECASE,
)
_LATE_YES = re.compile(r"[.?!,]\s*(okay,?\s+)?(yes|yeah|oui|sure|d'accord)\b[^?]*$", re.IGNORECASE)
_ANY_NO = re.compile(r"\b(no|not|don't|non|pas|refuse)\b", re.IGNORECASE)
_QUESTION = re.compile(
    r"\?\s*$|^\s*(what|how|when|why|will|would|can|could|is|are|do|does|should|est-ce|combien|quand|pourquoi|"
    r"comment|qu'est-ce|vais-je|est-ce que)\b",
    re.IGNORECASE,
)
TOPICS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "robot",
        re.compile(
            r"\b(are you (a )?(robot|real|human|machine|bot|computer|ai)|êtes-vous (un robot|"
            r"une machine|une vraie personne|humain))\b",
            re.I,
        ),
    ),
    ("premium", re.compile(r"\b(rates?|premiums?|price|cost me|go up|prime|tarifs?|augmenter)\b", re.I)),
    ("covered", re.compile(r"\b(covered|cover (it|this|that)|pay for|going to pay|couvert|rembours\w+)\b", re.I)),
    ("deductible", re.compile(r"\b(deductible|franchise)\b", re.I)),
    ("rental", re.compile(r"\b(rental|loaner|courtesy car|voiture de (location|courtoisie))\b", re.I)),
    (
        "contractor",
        re.compile(
            r"\b(contractor|repair shop|body shop|roofer|my own (guy|garage|shop)|"
            r"entrepreneur|couvreur|garagiste)\b",
            re.I,
        ),
    ),
    ("timeline", re.compile(r"\b(how long|when will|how soon|combien de temps|quand est-ce|dans combien)\b", re.I)),
    ("next", re.compile(r"\b(what happens next|what now|what's next|et ensuite|la suite|et après)\b", re.I)),
)

# Urgent safety: words that bring in a person now. Checked sentence by sentence; a negated sentence is not an alarm.
_URGENT: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "gas",
        re.compile(
            r"\b(smell(s|ing)? (of |like )?gas|gas (leak|smell)|leaking gas|odeur de gaz|fuite de gaz|"
            r"ça sent le gaz|sent le gaz)\b",
            re.I,
        ),
    ),
    (
        "fire",
        re.compile(
            r"\b(on fire|is burning|still burning|flames|smoke (is )?(coming|everywhere|filling|pouring)|"
            r"house is burning|en feu|des flammes|fumée partout|ça brûle|brûle encore)\b",
            re.I,
        ),
    ),
    (
        "injury",
        re.compile(
            r"\b(bleeding (badly|a lot|heavily)|unconscious|not breathing|can't breathe|passed out|"
            r"badly hurt|seriously (hurt|injured)|broke(n)? (his|her|my) (leg|arm|neck|back)|need an ambulance|"
            r"call an ambulance|saigne beaucoup|inconscient(e)?|ne respire (plus|pas)|gravement blessé(e)?|"
            r"besoin d'une ambulance)\b",
            re.I,
        ),
    ),
    ("trapped", re.compile(r"\b(trapped|stuck inside|can't get out|coincé(e)?s?|pris au piège)\b", re.I)),
    (
        "water_power",
        re.compile(
            r"\bwater (is |was )?(near|by|around|on|at|reaching|touching|up to) the (electrical|electric|breaker|"
            r"fuse) (panel|box)|\b(electrical|breaker) panel is (wet|under water|flooded)|\beau (est )?(près du|"
            r"proche du|atteint le|touche le|sur le) panneau électrique|\bpanneau électrique (est )?(mouillé|inondé)",
            re.I,
        ),
    ),
    (
        "power_line",
        re.compile(
            r"\b((power|hydro) lines? (is |are )?(down|fell|came down|on the (ground|car|house)|sparking)|"
            r"downed (power |hydro )?lines?|fils? électriques? (tombés?|par terre|au sol)|lignes? électriques? "
            r"(tombées?|au sol))\b",
            re.I,
        ),
    ),
)
SAFETY_REASONS: dict[str, dict[str, str]] = {
    "gas": {"en": "Smells gas", "fr": "Odeur de gaz"},
    "fire": {"en": "Fire or smoke right now", "fr": "Feu ou fumée en ce moment"},
    "injury": {"en": "Someone badly hurt", "fr": "Une personne gravement blessée"},
    "trapped": {"en": "Someone trapped", "fr": "Une personne coincée"},
    "water_power": {"en": "Water near the electrical panel", "fr": "De l'eau près du panneau électrique"},
    "power_line": {"en": "A power line is down", "fr": "Une ligne électrique est tombée"},
    "keyword": {"en": "Said a word on the hand-off list", "fr": "Un mot de la liste de transfert"},
}
_NEGATED = re.compile(
    r"\b(no|not|don't|doesn't|didn't|isn't|aren't|never|nothing|nobody|no one|without|ne\b|n'|pas|aucune?|"
    r"jamais|rien|personne)\b",
    re.I,
)
_STRONG_DISTRESS = re.compile(
    r"\b(i can't (cope|handle (this|it)|deal with (this|it)|do this|breathe)|i'm (panicking|freaking out|falling "
    r"apart|losing it)|can't stop (crying|shaking)|i'm (so |really )?terrified|help me please|je panique|je n'en "
    r"peux plus|je suis (terrifiée?|à bout|en panique)|je (n'arrête pas de )?pleur\w+|je craque)\b",
    re.I,
)
_MILD_DISTRESS = re.compile(
    r"\b(scared|upset|stressed|worried|shaken|nervous|frightened|frightening|overwhelmed|a mess|inquiète?|"
    r"stressée?|secouée?|peur|bouleversée?|angoiss\w+)\b",
    re.I,
)
_FR_WORDS = frozenset(
    [
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "est",
        "et",
        "je",
        "j'",
        "mon",
        "ma",
        "mes",
        "c'est",
        "oui",
        "non",
        "pas",
        "avec",
        "dans",
        "pour",
        "que",
        "qui",
        "il",
        "elle",
        "nous",
        "vous",
        "au",
        "du",
        "merci",
        "bonjour",
        "sur",
        "mais",
        "très",
        "bien",
        "ça",
        "d'accord",
        "votre",
        "notre",
        "été",
        "eu",
        "mal",
        "ce",
        "cette",
        "s'il",
    ]
)
_EN_WORDS = frozenset(
    [
        "the",
        "is",
        "and",
        "i",
        "my",
        "it",
        "was",
        "yes",
        "no",
        "with",
        "in",
        "for",
        "that",
        "we",
        "you",
        "thanks",
        "hi",
        "hello",
        "on",
        "but",
        "very",
        "okay",
        "it's",
        "i'm",
        "this",
        "our",
        "your",
        "please",
        "there",
        "were",
        "have",
        "has",
    ]
)
_WORD = re.compile(r"[a-zà-ÿ']+", re.I)


def detect_language(text: str) -> str | None:
    """'fr', 'en', or None when the turn is too short to tell (a bare "ok")."""
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return None
    fr = sum(1 for w in words if w in _FR_WORDS or w.startswith(("j'", "c'", "l'", "d'", "qu'", "n'", "s'")))
    en = sum(1 for w in words if w in _EN_WORDS)
    if re.search(r"[éèàùâêîôûç]", text):
        fr += 2
    if fr >= 2 and fr > en:
        return "fr"
    if en >= 2 and en > fr:
        return "en"
    return None


def _sentences(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    start = 0
    for m in re.finditer(r"[.!?;]+\s*|,\s+(?:but|mais)\s+", text):
        out.append((start, text[start : m.start()]))
        start = m.end()
    if start < len(text):
        out.append((start, text[start:]))
    return out


def urgent_safety(text: str, extra_keywords: tuple[str, ...] = ()) -> tuple[str, tuple[int, int]] | None:
    for offset, sentence in _sentences(text):
        for key, pattern in _URGENT:
            m = pattern.search(sentence)
            if not m:
                continue
            before = sentence[: m.start()]
            if _NEGATED.search(before[-28:]) and key not in ("injury",):
                continue
            return key, (offset + m.start(), offset + m.end())
        for word in extra_keywords:
            m2 = re.search(r"\b" + re.escape(word) + r"\b", sentence, re.I)
            if m2 and not _NEGATED.search(sentence[: m2.start()][-28:]):
                return "keyword", (offset + m2.start(), offset + m2.end())
    return None


def distress_score(text: str) -> float:
    if _STRONG_DISTRESS.search(text):
        return 0.85
    if _MILD_DISTRESS.search(text):
        return 0.45
    return 0.0


def classify_intent(text: str, *, asked_yes_no: bool = False) -> tuple[Intent, str | None]:
    if not text.strip():
        return Intent.UNKNOWN, None
    if _HANDOFF.search(text):
        return Intent.HANDOFF_REQUEST, None
    if _REPEAT.search(text):
        return Intent.REPEAT, None
    if _CORRECTION.search(text):
        return Intent.CORRECTION, None
    if YES.search(text):
        return Intent.AFFIRM, None
    if NO.search(text):
        return Intent.DENY, None
    if _LATE_YES.search(text) and not _ANY_NO.search(text):
        return Intent.AFFIRM, None  # "Before I answer, is this recorded? Okay, yes, that's fine."
    if _QUESTION.search(text):
        for topic, pattern in TOPICS:
            if pattern.search(text):
                return Intent.OFF_SCRIPT, topic
        if text.strip().endswith("?"):
            return Intent.OFF_SCRIPT, "other"
    if _GOODBYE.search(text):
        return Intent.GOODBYE, None
    return Intent.ANSWER, None


@dataclass
class FakeUnderstanding:
    """Rule-based understanding (EN/FR): intents, safety and distress signals, and claim-file values with spans."""

    extra_urgent_keywords: tuple[str, ...] = ()

    async def understand(self, request: NluRequest) -> NluResult:
        return self.understand_sync(request)

    def understand_sync(self, request: NluRequest) -> NluResult:
        text = request.utterance
        asked_spec = next((s for s in request.expecting if s.key == request.asked), None)
        intent, topic = classify_intent(text, asked_yes_no=bool(asked_spec and asked_spec.kind == "yes_no"))
        now: datetime = request.now or clock.now()
        slots = extract_values(
            text,
            request.language,
            request.expecting,
            asked=request.asked,
            now=now,
            filled=request.filled,
            region=request.region,
            correcting=intent is Intent.CORRECTION,
        )
        if intent is Intent.OFF_SCRIPT and any(v.key == request.asked for v in slots):
            intent, topic = Intent.ANSWER, None  # "It's with Front Range Auto, is that okay?" still answers
        urgent = urgent_safety(text, self.extra_urgent_keywords)
        language = detect_language(text)
        if intent is Intent.UNKNOWN or (intent is Intent.ANSWER and not slots and len(text.split()) <= 1):
            confidence = 0.3
        else:
            confidence = 0.9
        return NluResult(
            intent=intent,
            slots=tuple(slots),
            language=language if language and language != request.language else None,
            distress=distress_score(text),
            urgent_safety=urgent is not None,
            safety_reason=urgent[0] if urgent else None,
            confidence=confidence,
            source="fake",
            topic=topic,
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
