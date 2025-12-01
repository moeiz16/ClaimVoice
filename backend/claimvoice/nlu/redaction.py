"""PCI DSS: payment card numbers are never accepted by voice. Detect them in a caller utterance before anything is
stored, replace them, and tell the engine so it pauses the recording for that segment and tells the caller.

Detects 13-19 digit runs (spaces, dots or dashes between groups allowed) that pass the Luhn check. Spoken digits
("four five three two ...", "quatre cinq ...") are normalised to digits by the STT layer or the NLU before this runs.
Policy numbers (letters + digits, e.g. LM-AB-204118) and phone numbers (10-11 digits) are not affected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REDACTED = "[card number removed]"
_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ .\-]?){12,18}\d(?!\d)")


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass(frozen=True, slots=True)
class Redaction:
    text: str
    count: int
    spans: tuple[tuple[int, int], ...]  # spans in the *redacted* text where the placeholder sits


def redact_card_numbers(text: str) -> Redaction:
    out: list[str] = []
    spans: list[tuple[int, int]] = []
    last = 0
    for m in _CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if not 13 <= len(digits) <= 19 or not luhn_ok(digits):
            continue
        out.append(text[last : m.start()])
        start = sum(len(p) for p in out)
        out.append(REDACTED)
        spans.append((start, start + len(REDACTED)))
        last = m.end()
    out.append(text[last:])
    return Redaction("".join(out), len(spans), tuple(spans))
