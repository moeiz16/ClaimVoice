"""Low-level parsers for what callers say, in English and Canadian French: spoken numbers and digits, dates, times,
policy numbers, postal and ZIP codes, phone numbers and money. Every parser returns the character span it read, so
each value can point back at the words it came from.

Pure functions, no I/O. `now` is the call's business time (claimvoice.clock), passed in so tests are deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

Span = tuple[int, int]

UNITS_EN = {
    "zero": 0,
    "oh": 0,
    "o": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}
UNITS_FR = {
    "zéro": 0,
    "zero": 0,
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
}
DIGIT_WORDS = {**UNITS_FR, **UNITS_EN}

SMALL_EN = {
    **{k: v for k, v in UNITS_EN.items() if k not in ("oh", "o")},
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "a": 1,
    "an": 1,
    "a couple": 2,
    "a few": 3,
}
SMALL_FR = {
    **UNITS_FR,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
    "dix-sept": 17,
    "dix-huit": 18,
    "dix-neuf": 19,
    "vingt": 20,
    "trente": 30,
    "quarante": 40,
    "cinquante": 50,
    "soixante": 60,
    "quatre-vingt": 80,
    "quatre-vingts": 80,
}
ORDINALS_EN = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
}
MONTHS = {
    "january": 1,
    "jan": 1,
    "janvier": 1,
    "february": 2,
    "feb": 2,
    "février": 2,
    "fevrier": 2,
    "march": 3,
    "mar": 3,
    "mars": 3,
    "april": 4,
    "apr": 4,
    "avril": 4,
    "may": 5,
    "mai": 5,
    "june": 6,
    "juin": 6,
    "july": 7,
    "juillet": 7,
    "august": 8,
    "aug": 8,
    "août": 8,
    "aout": 8,
    "september": 9,
    "sept": 9,
    "septembre": 9,
    "october": 10,
    "oct": 10,
    "octobre": 10,
    "november": 11,
    "nov": 11,
    "novembre": 11,
    "december": 12,
    "dec": 12,
    "décembre": 12,
    "decembre": 12,
}
WEEKDAYS = {
    "monday": 0,
    "lundi": 0,
    "tuesday": 1,
    "mardi": 1,
    "wednesday": 2,
    "mercredi": 2,
    "thursday": 3,
    "jeudi": 3,
    "friday": 4,
    "vendredi": 4,
    "saturday": 5,
    "samedi": 5,
    "sunday": 6,
    "dimanche": 6,
}


def word_number(word: str) -> int | None:
    """'twenty' -> 20, 'twenty-five' -> 25, 'vingt-cinq' -> 25, '14' -> 14, 'third' -> 3."""
    w = word.lower().strip().replace("’", "'")
    if w.isdigit():
        return int(w)
    if w in SMALL_EN:
        return SMALL_EN[w]
    if w in SMALL_FR:
        return SMALL_FR[w]
    if w in ORDINALS_EN:
        return ORDINALS_EN[w]
    m = re.fullmatch(r"(\d+)(st|nd|rd|th|er|e)", w)
    if m:
        return int(m.group(1))
    if w == "premier":
        return 1
    w = w.replace(" et ", "-").replace(" ", "-")
    if w in SMALL_FR:
        return SMALL_FR[w]
    for base in ("quatre-vingt", "soixante"):  # soixante-dix-neuf = 79, quatre-vingt-deux = 82
        if w.startswith(base + "-"):
            rest = word_number(w[len(base) + 1 :])
            if rest is not None and rest < 20:
                return SMALL_FR[base] + rest
    for sep in ("-", " "):
        if sep in w:
            head, _, tail = w.partition(sep)
            h = SMALL_EN.get(head, SMALL_FR.get(head))
            t = word_number(tail.replace("et-", "").replace("et ", ""))
            if h is not None and h >= 20 and t is not None and t < 10:
                return h + t
    return None


_NUM_WORD = (
    r"(?:\d+|zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|zéro|un|une|deux|trois|quatre|cinq|sept|"
    r"huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt|trente|quarante|cinquante)"
)

# ------------------------------------------------------------------ spoken digit runs (card numbers, policy numbers)

_TOKEN = re.compile(r"[A-Za-zÀ-ÿ']+|\d+")


@dataclass(frozen=True, slots=True)
class DigitRun:
    digits: str
    span: Span


def digit_runs(text: str, *, max_gap: int = 3) -> list[DigitRun]:
    """Runs of digits said as numerals or digit words ("four five three two", "4532-0151", "double five"), with
    separators (spaces, commas, dashes, "and"/"et") between them. Used to catch card numbers read aloud."""
    runs: list[DigitRun] = []
    cur, start, end, last_end, pending_double = "", -1, -1, -1, False
    for m in _TOKEN.finditer(text):
        tok = m.group(0).lower()
        val: str | None = None
        if tok.isdigit():
            val = tok
        elif tok in DIGIT_WORDS and tok not in ("un", "une", "a", "o"):
            val = str(DIGIT_WORDS[tok])
        elif tok in ("o",) and cur:
            val = "0"
        elif tok in ("un", "une") and cur:
            val = "1"
        elif tok in ("double", "triple") and cur is not None:
            pending_double = tok == "double"
            if start < 0:
                start = m.start()
            last_end = m.end()
            continue
        gap = text[last_end : m.start()] if last_end >= 0 else ""
        if val is not None and (start < 0 or (len(gap) <= max_gap and not re.search(r"[A-Za-z]", gap))):
            if start < 0:
                start = m.start()
            cur += val * 2 if pending_double and len(val) == 1 else val
            pending_double = False
            end = last_end = m.end()
            continue
        if cur:
            runs.append(DigitRun(cur, (start, end)))
        cur, start, end, last_end, pending_double = "", -1, -1, -1, False
        if val is not None:
            cur, start, end, last_end = val, m.start(), m.end(), m.end()
    if cur:
        runs.append(DigitRun(cur, (start, end)))
    return runs


# ------------------------------------------------------------------ policy numbers

_POLICY_PLAIN = re.compile(r"\bL\s*-?\s*M\s*-?\s*([A-Z]{2})\s*-?\s*(\d{6})\b", re.IGNORECASE)
_SPELL_TOKEN = re.compile(r"[A-Za-z]+|\d+")


def find_policy_number(text: str, default_region: str | None = None) -> tuple[str, Span] | None:
    """'LM-AB-204118', 'lm ab 204118', or spelled out: 'L-M, A-B, two-oh-four, one-one-eight'."""
    m = _POLICY_PLAIN.search(text)
    if m:
        return f"LM-{m.group(1).upper()}-{m.group(2)}", m.span()
    # spelled: map single letters and digit words, then look for LM + region + 6 digits in the compact stream
    toks = [(t.group(0), t.span()) for t in _SPELL_TOKEN.finditer(text)]
    compact: list[tuple[str, Span]] = []
    for tok, span in toks:
        low = tok.lower()
        if tok.isdigit():
            compact.extend((ch, span) for ch in tok)
        elif low in UNITS_EN and low not in ("a",):
            compact.append((str(UNITS_EN[low]), span))
        elif len(tok) == 1 and tok.isalpha():
            compact.append((tok.upper(), span))
        elif len(tok) == 2 and tok.isupper():
            compact.extend((ch, span) for ch in tok)
        else:
            compact.append(("|", span))
    stream = "".join(c for c, _ in compact)
    m2 = re.search(r"LM([A-Z]{2})?(\d{6})", stream)
    if not m2:
        return None
    region = m2.group(1) or (default_region.split("-")[1] if default_region and "-" in default_region else None)
    if not region:
        return None
    first, last = compact[m2.start()][1], compact[m2.end() - 1][1]
    return f"LM-{region}-{m2.group(2)}", (first[0], last[1])


# ------------------------------------------------------------------ postal codes, ZIP, phone

_POSTAL_CA = re.compile(r"\b([A-Za-z]\d[A-Za-z])[ -]?(\d[A-Za-z]\d)\b")
_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?(\d{3})\)?[ .-]?(\d{3})[ .-]?(\d{4})(?!\d)")


def find_postal(text: str) -> tuple[str, Span] | None:
    m = _POSTAL_CA.search(text)
    if m:
        return f"{m.group(1).upper()} {m.group(2).upper()}", m.span()
    z = _ZIP.search(text)
    if z:
        return z.group(1), z.span()
    return None


def find_phone(text: str) -> tuple[str, Span] | None:
    m = _PHONE.search(text)
    if m:
        return f"+1{m.group(1)}{m.group(2)}{m.group(3)}", m.span()
    runs = [r for r in digit_runs(text) if len(r.digits) in (10, 11)]
    for r in runs:
        d = r.digits[-10:]
        return f"+1{d}", r.span
    return None


# ------------------------------------------------------------------ money

_MONEY = re.compile(
    r"(?:\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?|(\d[\d,\s]*)\s*(\$|dollars|piasses)|"
    r"(" + _NUM_WORD + r"(?:[ -]" + _NUM_WORD + r")?)\s+(thousand|mille)(?:\s+(dollars|\$))?)",
    re.IGNORECASE,
)


def find_money(text: str) -> tuple[float, Span] | None:
    for m in _MONEY.finditer(text):
        if m.group(1):
            amount = float(m.group(1).replace(",", ""))
            if m.group(2):
                amount *= 1000
            return amount, m.span()
        if m.group(3):
            return float(re.sub(r"[,\s]", "", m.group(3))), m.span()
        if m.group(5):
            n = word_number(m.group(5))
            if n is not None:
                return float(n * 1000), m.span()
    return None


def money_band(amount: float) -> str:
    if amount < 2000:
        return "under_2k"
    if amount < 10000:
        return "2k_10k"
    if amount < 50000:
        return "10k_50k"
    return "over_50k"


# ------------------------------------------------------------------ times

_AMPM = r"(a\.?\s?m\.?|p\.?\s?m\.?)"
_TIME_DIGITS = re.compile(r"\b(\d{1,2})\s?(?::|h)\s?(\d{2})?\s*" + _AMPM + r"?", re.IGNORECASE)
_TIME_AMPM = re.compile(r"\b(\d{1,2})\s*" + _AMPM, re.IGNORECASE)
_HOUR_WORDS = (
    r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dix-sept|dix-huit|dix-neuf|vingt-et-une|"
    r"vingt et une|vingt-deux|vingt-trois|treize|quatorze|quinze|seize|vingt|une|deux|trois|quatre|cinq|six|sept|"
    r"huit|neuf|dix|onze|douze|\d{1,2})"
)
_MIN_WORDS = (
    r"(o'clock|oh[ -]?(?:one|two|three|four|five|six|seven|eight|nine)|fifteen|thirty|forty[ -]?five|forty|twenty|"
    r"ten|five|fifty|quarante[ -]?cinq|trente|quinze|vingt|dix|cinq|\d{2})"
)
_TIME_WORDS_EN = re.compile(
    r"\b(?:around|about|at|like|roughly|maybe|close to)?\s*" + _HOUR_WORDS + r"(?:[ -]" + _MIN_WORDS + r")?"
    r"(?:\s+(in the morning|at night|in the afternoon|in the evening|a\.?m\.?|p\.?m\.?))?\b",
    re.IGNORECASE,
)
_PAST = re.compile(
    r"\b(ten|five|twenty|twenty[ -]five|quarter|half)\s+(past|after|to)\s+" + _HOUR_WORDS + r"\b", re.IGNORECASE
)
_TIME_FR = re.compile(
    r"\b(?:vers|à|autour de|environ)?\s*" + _HOUR_WORDS + r"\s+heures?(?:\s+(et demie|et quart|moins le quart|"
    r"quinze|trente|quarante-cinq|\d{2}))?(?:\s+(du matin|de l'après-midi|du soir|de la nuit))?",
    re.IGNORECASE,
)
_NAMED = re.compile(r"\b(midnight|noon|midday|minuit|midi)\b", re.IGNORECASE)
_RELATIVE = re.compile(
    r"\b(?:("
    + _NUM_WORD
    + r"|a few|a couple of|an?|half an?)\s+(minutes?|hours?)\s+ago|il y a\s+("
    + _NUM_WORD
    + r"|quelques)\s+(minutes?|heures?)|just now|à l'instant|tout à l'heure)\b",
    re.IGNORECASE,
)

_MORNING = re.compile(
    r"\b(this morning|in the morning|overnight|last night|during the night|middle of the night|ce matin|du matin|"
    r"cette nuit|de la nuit|pendant la nuit|a\.?m\.?)\b",
    re.IGNORECASE,
)
_NIGHT_BEFORE = re.compile(r"\b(last night|hier soir|la nuit dernière)\b", re.IGNORECASE)
_EVENING = re.compile(
    r"\b(this afternoon|this evening|tonight|in the afternoon|in the evening|after work|yesterday evening|"
    r"yesterday afternoon|cet après-midi|ce soir|hier soir|hier après-midi|de l'après-midi|du soir|p\.?m\.?)\b",
    re.IGNORECASE,
)


def _minutes(word: str | None) -> int:
    if not word:
        return 0
    w = word.lower().replace("-", " ").strip()
    if w in ("o'clock",):
        return 0
    if w.startswith("oh "):
        return word_number(w[3:]) or 0
    if w in ("et demie",):
        return 30
    if w in ("et quart",):
        return 15
    if w == "moins le quart":
        return -15
    n = word_number(w.replace(" ", "-")) or word_number(w)
    return n or 0


@dataclass(frozen=True, slots=True)
class TimeHit:
    value: time
    span: Span
    explicit_half: bool  # a.m./p.m. or morning/evening was said
    relative_minutes: int | None = None  # "twenty minutes ago"


def _apply_half(
    hour: int, text: str, ampm: str | None, prior: time | None, now: datetime | None = None
) -> tuple[int, bool]:
    if ampm:
        pm = ampm.lower().startswith("p")
        return (hour % 12) + (12 if pm else 0), True
    if hour > 12:
        return hour, True
    if _EVENING.search(text):
        return (hour % 12) + 12, True
    if _NIGHT_BEFORE.search(text) and 6 <= hour <= 11:  # "around eleven last night" is 11 p.m.
        return hour + 12, True
    if _MORNING.search(text):
        return hour % 12, True
    if prior is not None:  # a correction keeps the half of day it corrects
        return (hour % 12) + (12 if prior.hour >= 12 else 0), False
    if now is not None:  # the most recent of the two that is already past
        am_hour, pm_hour = hour % 12, hour % 12 + 12
        return (pm_hour if pm_hour <= now.hour else am_hour), False
    return (hour % 12) + (12 if 1 <= hour <= 6 else 0), False


def find_time(text: str, *, now: datetime, prior: time | None = None) -> TimeHit | None:
    hit = _find_clock_time(text, prior=prior, now=now)
    if hit is not None:
        return hit
    rel = _RELATIVE.search(text)
    if rel:
        phrase = rel.group(0).lower()
        if "just now" in phrase or "instant" in phrase or "tout à l'heure" in phrase:
            mins = 5
        else:
            qty = (rel.group(1) or rel.group(3) or "").lower()
            unit = (rel.group(2) or rel.group(4) or "").lower()
            n = {"a few": 3, "a couple of": 2, "quelques": 3, "a": 1, "an": 1, "half a": 0, "half an": 0}.get(qty)
            if n is None:
                n = word_number(qty) or 1
            mins = n * 60 if unit.startswith(("hour", "heure")) else n
            if qty.startswith("half"):
                mins = 30
        t = (now - timedelta(minutes=mins)).time().replace(second=0, microsecond=0)
        return TimeHit(t, rel.span(), True, mins)
    return None


def _find_clock_time(text: str, *, prior: time | None, now: datetime) -> TimeHit | None:
    m = _NAMED.search(text)
    if m:
        h = 0 if m.group(1).lower() in ("midnight", "minuit") else 12
        return TimeHit(time(h, 0), m.span(), True)
    m = _PAST.search(text)
    if m:
        hour = word_number(m.group(3)) or 0
        mins = {"quarter": 15, "half": 30}.get(m.group(1).lower(), word_number(m.group(1).replace(" ", "-")) or 0)
        if m.group(2).lower() == "to":
            hour, mins = hour - 1, 60 - mins
        hour24, explicit = _apply_half(hour, text, None, prior, now)
        return TimeHit(time(hour24 % 24, mins % 60), m.span(), explicit)
    m = _TIME_FR.search(text)
    if m:
        fr_hour = word_number(m.group(1))
        if fr_hour is not None and 0 <= fr_hour <= 23:
            hour = fr_hour
            mins = _minutes(m.group(2))
            if mins < 0:
                hour, mins = hour - 1, 45
            half = m.group(3)
            if half and ("soir" in half or "après" in half) and hour < 12:
                hour += 12
            explicit = bool(half) or hour > 12
            if not explicit:
                hour, explicit = _apply_half(hour, text, None, prior, now)
            return TimeHit(time(hour % 24, mins), m.span(), explicit)
    m = _TIME_DIGITS.search(text)
    if m and (m.group(2) or m.group(3)):
        hour, mins = int(m.group(1)), int(m.group(2) or 0)
        if hour <= 24 and mins < 60:
            hour24, explicit = _apply_half(hour, text, m.group(3), prior, now)
            return TimeHit(time(hour24 % 24, mins), m.span(), explicit)
    m = _TIME_AMPM.search(text)
    if m:
        hour24, explicit = _apply_half(int(m.group(1)), text, m.group(2), prior, now)
        return TimeHit(time(hour24 % 24, 0), m.span(), explicit)
    for m in _TIME_WORDS_EN.finditer(text):
        lead = text[max(0, m.start() - 12) : m.start()].lower() + m.group(0).lower()
        has_cue = re.search(r"\b(around|about|at|like|roughly|close to)\b", lead) or m.group(3)
        if not has_cue or not m.group(1):
            continue
        # "at two in the morning", "around two thirty"; never "two cars"
        after = text[m.end() : m.end() + 8].lower()
        if re.match(r"\s*(cars?|people|kids|rooms?|days?|weeks?|of|inch|cm|feet|foot|minutes?|hours?|mins?)", after):
            continue
        spoken = word_number(m.group(1))
        if spoken is None or not 0 < spoken <= 12:
            continue
        hour = spoken
        mins = _minutes(m.group(2))
        ampm = m.group(3) if m.group(3) and "m" in m.group(3).lower() else None
        hour24, explicit = _apply_half(hour, text, ampm, prior, now)
        if m.group(3) and not explicit:
            hour24, explicit = _apply_half(hour, m.group(3), None, prior, now)
        return TimeHit(time(hour24 % 24, mins % 60), m.span(), explicit)
    return None


# ------------------------------------------------------------------ dates

_TODAY = re.compile(
    r"\b(today|this morning|this afternoon|this evening|tonight|just now|a few minutes ago|minutes ago|an hour ago|"
    r"hours? ago|aujourd'hui|ce matin|cet après-midi|ce soir|tantôt|à l'instant|il y a (?:quelques |\w+ )?minutes|"
    r"il y a (?:une|deux|trois) heures?)\b",
    re.IGNORECASE,
)
_OVERNIGHT = re.compile(
    r"\b(overnight|last night|during the night|middle of the night|cette nuit|la nuit dernière|pendant la nuit)\b",
    re.IGNORECASE,
)
_YESTERDAY = re.compile(r"\b(yesterday|hier)\b", re.IGNORECASE)
_DAY_BEFORE = re.compile(r"\b((?:the )?day before yesterday|avant-hier)\b", re.IGNORECASE)
_DAYS_AGO = re.compile(
    r"\b(?:(" + _NUM_WORD + r"|a couple of|a few)\s+days?\s+ago|il y a\s+(" + _NUM_WORD + r")\s+jours?)\b",
    re.IGNORECASE,
)
_WEEKDAY = re.compile(
    r"\b(?:(last|this past|on|this)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|lundi|mardi|"
    r"mercredi|jeudi|vendredi|samedi|dimanche)(?:\s+(dernier|passé))?\b",
    re.IGNORECASE,
)
_DAY_WORD = (
    r"(\d{1,2}(?:st|nd|rd|th|er|e)?|premier|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|"
    r"twenty[ -](?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)|thirtieth|thirty[ -]first|"
    r"trente[ -]et[ -]un|trente|vingt[ -](?:et[ -])?(?:un|deux|trois|quatre|cinq|six|sept|huit|neuf)|"
    r"dix-sept|dix-huit|dix-neuf|"
    r"un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt)(?![\d\w])"
)
_MONTH_WORD = (
    r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|"
    r"aug|sept|oct|nov|dec|janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|"
    r"novembre|décembre|decembre)(?![A-Za-zÀ-ÿ])"
)
_YEAR = (
    r"(?:,?\s+(\d{4}|nineteen[ -]\w+(?:[ -]\w+)?|twenty[ -]\w+(?:[ -]\w+)?|"
    r"(?:mille )?neuf cent(?:[ -](?:et|un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|"
    r"quinze|seize|vingt|trente|quarante|cinquante|soixante|quatre-vingts?|dix-\w+))*))?"
)
_MONTH_DAY = re.compile(r"\b" + _MONTH_WORD + r"\.?\s+(?:the\s+)?" + _DAY_WORD + _YEAR, re.IGNORECASE)
_DAY_MONTH = re.compile(
    r"\b(?:le\s+|the\s+)?" + _DAY_WORD + r"(?:\s+of)?\s+" + _MONTH_WORD + _YEAR,
    re.IGNORECASE,
)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def spoken_year(text: str | None) -> int | None:
    if not text:
        return None
    t = text.lower().strip()
    if t.isdigit():
        return int(t)
    t = t.replace("-", " ")
    words = t.split()
    if words[:1] == ["nineteen"] and len(words) >= 2:
        rest = word_number("-".join(words[1:])) or word_number(words[1])
        return 1900 + rest if rest is not None else None
    if words[:2] == ["twenty", "twenty"] or (words[:1] == ["two"] and "thousand" in words):
        return None
    if words[:1] == ["twenty"] and len(words) >= 2:
        rest = word_number("-".join(words[1:])) or word_number(words[1])
        return 2000 + rest if rest is not None else None
    if "neuf cent" in t:
        tail = t.split("neuf cent", 1)[1].strip()
        rest = word_number(tail.replace(" ", "-")) if tail else 0
        if rest is None:
            parts = tail.split()
            rest = sum(word_number(p) or 0 for p in parts if p != "et")
        return 1900 + rest
    return None


@dataclass(frozen=True, slots=True)
class DateHit:
    value: date
    span: Span
    has_year: bool = False


def _day(word: str) -> int | None:
    return word_number(word.replace(" ", "-"))


def find_date(text: str, *, today: date, loss_time: time | None = None) -> DateHit | None:
    m = _ISO.search(text)
    if m:
        try:
            return DateHit(date(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.span(), True)
        except ValueError:
            pass
    m = _SLASH.search(text)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        month, day = (a, b) if a <= 12 else (b, a)
        try:
            return DateHit(date(y, month, day), m.span(), True)
        except ValueError:
            pass
    for pattern, month_group, day_group in ((_MONTH_DAY, 1, 2), (_DAY_MONTH, 2, 1)):
        m = pattern.search(text)
        if m:
            month_n = MONTHS.get(m.group(month_group).lower())
            day_n = _day(m.group(day_group))
            year = spoken_year(m.group(3))
            if month_n and day_n and 1 <= day_n <= 31:
                month, day = month_n, day_n
                y = year or today.year
                try:
                    d = date(y, month, day)
                except ValueError:
                    continue
                if year is None and d > today:
                    d = d.replace(year=y - 1)
                return DateHit(d, m.span(), year is not None)
    m = _DAYS_AGO.search(text)
    if m:
        qty = (m.group(1) or m.group(2) or "").lower()
        n = {"a couple of": 2, "a few": 3}.get(qty) or word_number(qty) or 1
        return DateHit(today - timedelta(days=n), m.span())
    m = _DAY_BEFORE.search(text)
    if m:
        return DateHit(today - timedelta(days=2), m.span())
    m = _YESTERDAY.search(text)
    if m:
        return DateHit(today - timedelta(days=1), m.span())
    m = _OVERNIGHT.search(text)
    if m:
        after_midnight = loss_time is not None and loss_time.hour < 7
        last_night = m.group(1).lower() in ("last night", "la nuit dernière")
        if after_midnight or (not last_night and loss_time is None):
            return DateHit(today, m.span())
        return DateHit(today - timedelta(days=1), m.span())
    m = _TODAY.search(text)
    if m:
        return DateHit(today, m.span())
    m = _WEEKDAY.search(text)
    if m:
        wd = WEEKDAYS[m.group(2).lower()]
        delta = (today.weekday() - wd) % 7
        if delta == 0 and (m.group(1) or m.group(3)) and (m.group(1) or "").lower() != "this":
            delta = 7
        return DateHit(today - timedelta(days=delta), m.span())
    return None
