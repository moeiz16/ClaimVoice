"""PCI DSS: payment card numbers are never accepted by voice. Detect them in a caller utterance before anything is
stored, replace them, and tell the engine so it pauses the recording for that segment and tells the caller.

What counts as a card number:
* a run of 13-19 digits that passes the Luhn check, written as numerals ("4111 1111 1111 1111", "4111-1111-...") or
  spoken as digit words ("four one one one ...", "quatre cinq ...", "double one"), and
* once the caller mentions a card ("my card", "Visa", "credit card", "ma carte"), any run of two or more digits after
  that word, spoken or written, because callers often stop half-way and a partial card number is still card data.

Policy numbers (letters + digits, e.g. LM-AB-204118), postal codes and phone numbers outside a card context are not
affected. The replacement text is the same everywhere: `[card number removed]`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from claimvoice.nlu.parse import digit_runs

REDACTED = "[card number removed]"
_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ .\-]?){12,18}\d(?!\d)")
_CARD_CONTEXT = re.compile(
    r"\b(card|credit|debit|visa|master\s?card|amex|american express|carte|crédit|débit|expir\w*|cvv|"
    r"security code|code de sécurité)\b",
    re.IGNORECASE,
)
_PHONE_SHAPE = re.compile(r"(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}")
_POLICY_LIKE = re.compile(r"\bL\s*-?\s*M\s*-?\s*[A-Z]{2}\s*-?\s*\d{6}\b", re.IGNORECASE)


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
    card_context: bool = False  # the caller mentioned a card (the line explains it never takes payment details)


def _card_spans(text: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    policy = [m.span() for m in _POLICY_LIKE.finditer(text)]

    def inside_policy(span: tuple[int, int]) -> bool:
        return any(a <= span[0] and span[1] <= b for a, b in policy)

    for m in _CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            found.append(m.span())
    for run in digit_runs(text):
        if 13 <= len(run.digits) <= 19 and luhn_ok(run.digits) and not inside_policy(run.span):
            found.append(run.span)
    ctx = _CARD_CONTEXT.search(text)
    if ctx:
        for run in digit_runs(text):
            raw = text[run.span[0] : run.span[1]]
            looks_like_phone = len(run.digits) in (10, 11) and bool(_PHONE_SHAPE.fullmatch(raw.strip()))
            if (
                run.span[0] >= ctx.start()
                and len(run.digits) >= 2
                and not inside_policy(run.span)
                and not looks_like_phone
            ):
                found.append(run.span)
    # merge overlaps
    found.sort()
    merged: list[tuple[int, int]] = []
    for a, b in found:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def redact_card_numbers(text: str) -> Redaction:
    spans = _card_spans(text)
    out: list[str] = []
    placed: list[tuple[int, int]] = []
    last = 0
    for a, b in spans:
        out.append(text[last:a])
        start = sum(len(p) for p in out)
        out.append(REDACTED)
        placed.append((start, start + len(REDACTED)))
        last = b
    out.append(text[last:])
    return Redaction("".join(out), len(placed), tuple(placed), bool(_CARD_CONTEXT.search(text)))


def contains_card_number(text: str) -> bool:
    """True when text still holds something that looks like a card number (used by the eval and the QA rubric)."""
    for m in _CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            return True
    return any(13 <= len(r.digits) <= 19 and luhn_ok(r.digits) for r in digit_runs(text))
