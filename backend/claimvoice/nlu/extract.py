"""Rule-based value extraction for the claim file, English and Canadian French.

`extract_values` looks only for the fields the engine is expecting in the current stage, returns each value with the
character span it was heard in, and is deliberately conservative: unknown beats wrong. The asked question gets a more
lenient reading (a bare "yes" answers a yes/no question; a free-text question takes the caller's words).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from claimvoice.dialogue.slots import display
from claimvoice.nlu import lexicon as lx
from claimvoice.nlu.base import SlotSpec, SlotValue
from claimvoice.nlu.parse import (
    find_date,
    find_money,
    find_phone,
    find_policy_number,
    find_postal,
    find_time,
    money_band,
    word_number,
)

Span = tuple[int, int]
I = re.IGNORECASE  # noqa: E741
# Free-text fields where the caller's own words are the answer (names, insurers and numbers need a pattern).
FREE_TEXT = frozenset(
    {"debris_source", "damage_areas", "items_stolen", "loss_place", "extra_notes", "loss_description", "injury_detail"}
)
NAME_FIELDS = frozenset({"other_party_insurer", "other_party_name"})
# Values that describe the situation now (a later mention updates them) or that accumulate (damage seen so far).
UPDATABLE = frozenset(
    {
        "injury_reported",
        "injury_detail",
        "open_to_weather",
        "water_still_entering",
        "home_livable",
        "power_out",
        "danger_now",
        "mitigation_taken",
        "damage_areas",
        "police_report_filed",  # "no, I haven't called the police yet" after a hurried "yes"
    }
)


@dataclass(frozen=True, slots=True)
class Hit:
    value: Any
    span: Span
    confidence: float = 0.9


def _first(patterns: Sequence[tuple[re.Pattern[str], Any]], text: str) -> Hit | None:
    best: Hit | None = None
    for pattern, value in patterns:
        m = pattern.search(text)
        if m and (best is None or m.start() < best.span[0]):
            best = Hit(value(m) if callable(value) else value, m.span())
    return best


def _rx(*alternatives: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{a})" for a in alternatives), I)


def _alt(words: Sequence[str]) -> str:
    """A regex alternation of lexicon phrases, longest first, with spaces and hyphens matched loosely."""
    parts = sorted({w for w in words if w}, key=len, reverse=True)
    return "(?:" + "|".join(re.escape(w).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]?") for w in parts) + ")"


# A negation shortly before a word ("nothing broken", "pas de fenêtre brisée") turns a mention into a "no".
_NEG_BEFORE = re.compile(
    r"\b(no|not|nothing|none|never|without|isn't|wasn't|aren't|weren't|didn't|doesn't|don't|haven't|hasn't|"
    r"rien|pas|aucune?|jamais|sans)\b[^.,;!?]{0,18}$",
    I,
)


def _negated(text: str, start: int) -> bool:
    return bool(_NEG_BEFORE.search(text[max(0, start - 30) : start]))


# ------------------------------------------------------------------ yes / no

YES = _rx(
    r"^\s*(?:yes|yeah|yep|yup|yea|ya|sure|correct|right|that's right|that is right|ok(?:ay)?|of course|absolutely|"
    r"definitely|please do|go ahead|uh[- ]huh|mm[- ]hmm|i do|we do|it is|there is|they did|that's (?:fine|ok(?:ay)?|"
    r"alright|all right|good)|that is fine|fine|no problem|no worries|that works|go for it|sounds good|alright|"
    r"all right|for sure|you bet|sure thing|by all means|totally|affirmative)\b",
    r"^\s*please\s*[.!]?\s*$",
    r"^\s*(?:oui|ouais|d'accord|bien sûr|exact|exactement|c'est ça|allez-y|vas-y|tout à fait|absolument|"
    r"j'accepte|je veux bien|volontiers|c'est correct|correct|ça me va|pas de problème|pas de souci|ben oui|"
    r"mais oui|certainement|bien entendu|parfait|oké)\b",
    r"^\s*s'il vous plaît\s*[.!]?\s*$",
)
NO = _rx(
    r"^\s*(?:no|nope|nah|not really|not at all|i don't|we don't|it isn't|it's not|there isn't|i'd rather not|"
    r"no thanks|no thank you|negative|not yet|no way|i don't think so|not that i know of)\b",
    r"^\s*(?:non|pas du tout|pas vraiment|non merci|je refuse|je ne veux pas|pas question|pas encore|pantoute)\b",
)
# An answer to a yes/no question the line just asked may lead with a short clause instead of "yes" or "no":
# "Nothing broken", "We haven't", "It didn't", "Je l'ai pas", "Y'a pas de trou". Only read for the asked question.
_ANSWER_NO = _rx(
    r"^\s*(?:nothing|none|nobody|no one|never|i didn't|we didn't|they didn't|he didn't|she didn't|it didn't|"
    r"it doesn't|it won't|i haven't|we haven't|haven't|i can't|we can't|it can't|i wasn't|it wasn't|there wasn't|"
    r"there weren't|not that i saw|i don't think)\b",
    r"^\s*(?:rien|aucun\w*|personne|jamais|je l'ai pas|j'ai pas|on n'a pas|on a pas|je n'ai pas|il y a pas|"
    r"y'a pas|y a pas|ils ont pas|c'est pas|non plus)\b",
)
_ANSWER_YES = _rx(
    r"^\s*(?:i think so|i believe so|probably|pretty sure|i did|we did|he did|she did|it did|it does|i have|"
    r"we have|they have|i can|we can|it can|there was|there were|they came|i guess so)\b",
    r"^\s*(?:je pense que oui|je crois que oui|probablement|j'ai|on a|ils ont|elle a|il a)\b",
)


def yes_no(text: str) -> Hit | None:
    """A yes or a no leading an answer to the yes/no question the line asked."""
    m = YES.search(text)
    if m:
        return Hit(True, m.span(), 0.9)
    m = NO.search(text)
    if m:
        return Hit(False, m.span(), 0.9)
    m = _ANSWER_NO.search(text)
    if m:
        return Hit(False, m.span(), 0.8)
    m = _ANSWER_YES.search(text)
    if m:
        return Hit(True, m.span(), 0.75)
    return None


# ------------------------------------------------------------------ loss type

LOSS_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_rx(r"\b(hail|hailstorm|hailstones?|grêle|grêlons?)\b"), "hail"),
    (
        _rx(
            r"\b(wind|winds|windstorm|chinook|gusts?|blew (off|over|down|away|in)|blown (off|over|down|away)|"
            r"tore (up|off)|(?:le|du|des|les|grands?|coup de|au) vents?|tempête de vent|bourrasques?|rafales?)\b"
        ),
        "wind",
    ),
    (
        _rx(
            r"\b(rear[- ]ended|rear end|crash(ed)?|collision|collided|accident|fender[- ]bender|hit me|hit my "
            r"(car|truck|van|vehicle)|backed into|t-boned|sideswiped|ran into|accrochage|embouti|frappé|"
            r"carambolage|accident de voiture|slid into|hit a (pole|deer|tree|curb|post|wall|parked car)|scraped|"
            r"backed (into|out)|car accident|ding(ed)?|dent(ed)?|bumped( into)?|hit[- ]and[- ]run|"
            r"(someone|somebody|a (car|truck|van|driver)|another (car|truck|driver|vehicle)) (hit|struck|rammed)|"
            r"recul\w* dans|heurt\w+|percut\w+|emboutie)\b"
        ),
        "collision",
    ),
    (
        _rx(
            r"\b(flood(ed|ing)?|burst|pipe|leak(ed|ing)?|water (damage|everywhere|in the)|sewer|backed up|"
            r"water heater|sewage|water in|inondé(e)?|inondation|dégât d'eau|tuyau|fuite|refoulement|dégâts d'eau|"
            r"chauffe-eau|a coulé|de l'eau partout|eau dans)\b"
        ),
        "water",
    ),
    (
        _rx(
            r"\b(kitchen fire|house fire|caught fire|burn(ed|t)|smoke damage|fire damage|incendie|feu de cuisine|"
            r"brûlé|dommages? de fumée|a fire)\b"
        ),
        "fire",
    ),
    (
        _rx(
            r"\b(stolen|stole|theft|broke in|break[- ]in|broken into|burglar\w*|robbed|vol|volé(e)?|"
            r"cambriol\w+|entrée par effraction|par effraction|on m'a volé)\b"
        ),
        "theft",
    ),
]


def loss_type(text: str) -> Hit | None:
    return _first(LOSS_TYPE_PATTERNS, text)


# ------------------------------------------------------------------ per-field patterns

NEG = r"(?:no|not|n't|never|nobody|no one|none|nothing|aucun\w*|personne|pas|jamais|rien)"


_BODY_ALT = _alt(lx.BODY_EN)
_HURT_ADJ = r"(sore|stiff|aching|bruised|sprained|swollen|tender|banged up|hurting|hurt)"


def _injury(text: str) -> Hit | None:
    negative = _rx(
        r"\b(nobody|no one|no-one|none of us)( else)?('s| is| was| got)? (hurt|injured)\b",
        r"\b(everyone|everybody|we|we're|we are|i'm|i am)('s| is| are)? (all )?(okay|ok|fine|safe|alright|all right|"
        r"good)\b",
        r"\bnot (hurt|injured)\b",
        r"\bpersonne n'(est|a été) bless\w+",
        r"\b(pas|personne de|aucun) bless\w*",
        r"\btout le monde (va bien|est correct|est en sécurité)",
        r"\b(je vais bien|on va bien|nous allons bien)\b",
    )
    positive = _rx(
        r"\bmy (neck|back|head|arm|leg|shoulder|knee|wrist|chest|hand)('s| is| feels)?( a little| a bit| kind of| "
        r"really| pretty)? (sore|hurts?|stiff|bleeding|aching|bruised|cut)",
        r"\b(sore|stiff|hurt) (neck|back|shoulder)",
        r"\b(i'm|i am|i got|he's|she's|they're|my (wife|husband|son|daughter|kid|passenger)( is)?) "
        r"(hurt|injured|bleeding)",
        r"\bwhiplash\b",
        r"\b" + _HURT_ADJ + r"( \w+){0,2} (in|on) (the|my|his|her) " + _BODY_ALT + r"\b",
        r"\b(hurt|bumped|banged|cut|twisted|sprained|tweaked|pulled|bruised|wrenched|jammed) (my|his|her|their) "
        + _BODY_ALT
        + r"\b",
        r"\b" + _BODY_ALT + r" (is|feels|'s|are) (a (little|bit) |kind of |really |pretty )?(sore|stiff|hurting|"
        r"aching|bruised|swollen|tender)",
        r"\bj'ai (un peu |vraiment |très )?mal (au|à la|à l'|aux) \w+",
        r"\b(je me suis|il s'est|elle s'est) (fait mal|blessée?|cogné\w*)",
        r"(?<!pas )\b(je suis|il est|elle est) (un peu |légèrement )?bless\w+",
    )
    pos = positive.search(text)
    if pos:
        return Hit(True, pos.span())
    neg = negative.search(text)
    if neg:
        return Hit(False, neg.span())
    return None


_BODY = r"(neck|back|head|arm|leg|shoulder|knee|wrist|chest|hand|cou|dos|tête|bras|jambe|épaule|genou|poignet)"


def _injury_detail(text: str) -> Hit | None:
    m = re.search(
        r"\bmy " + _BODY + r"('s| is| feels)?( a little| a bit| kind of| really| pretty)? (sore|stiff|hurts?)", text, I
    )
    if m:
        part = m.group(1).lower()
        return Hit(f"Sore {part}", m.span())
    m = re.search(r"\b(sore|stiff) " + _BODY, text, I)
    if m:
        return Hit(f"Sore {m.group(2).lower()}", m.span())
    m = re.search(r"\bj'ai (un peu )?mal (au|à la|aux) " + _BODY, text, I)
    if m:
        return Hit(f"Mal {m.group(2)} {m.group(3).lower()}", m.span())
    m = re.search(r"\bwhiplash\b", text, I)
    if m:
        return Hit("Whiplash", m.span())
    m = re.search(r"\b" + _HURT_ADJ + r"(?: \w+){0,2} (?:in|on) (?:the|my|his|her) (" + _BODY_ALT + r")\b", text, I)
    if m:
        word = m.group(1).lower()
        word = "Sore" if word in ("aching", "tender", "hurting", "hurt", "banged up") else word.capitalize()
        return Hit(f"{word} {m.group(2).lower()}", m.span())
    m = re.search(r"\b(?:hurt|bumped|banged|cut|twisted|sprained|tweaked|pulled|bruised) (?:my|his|her) (" + _BODY_ALT
                  + r")\b", text, I)  # fmt: skip
    if m:
        return Hit(f"Hurt {m.group(1).lower()}", m.span())
    return None


def _danger(text: str) -> Hit | None:
    neg = _rx(
        r"\bnothing('s| is)? dangerous\b",
        r"\bno (danger|gas smell|smell of gas|smoke|fire)\b",
        r"\b(it's|everything's|we're) safe\b",
        r"\brien de dangereux\b",
        r"\baucun danger\b",
        r"\bl'eau ne s'en approche pas\b",
        r"\bnowhere near\b",
        r"\bpower('s| is) still on\b",
    )
    m = neg.search(text)
    if m:
        return Hit(False, m.span())
    return None


def _power_out(text: str) -> Hit | None:
    off = _rx(
        r"\b(power|electricity|hydro)('s| is)? (out|off|down|gone)\b",
        r"\b(no|lost( the)?) (power|electricity|hydro)\b",
        r"\bpanne (de courant|d'électricité)\b",
        r"\bplus d'électricité\b",
    )
    on = _rx(
        r"\b(power|electricity|hydro)('s| is)? (still )?on\b",
        r"\b(we|i) (still )?have power\b",
        r"\bon a (encore |toujours )?(de l'électricité|le courant)\b",
    )
    m = on.search(text)
    if m:
        return Hit(False, m.span())
    m = off.search(text)
    if m:
        return Hit(True, m.span())
    return None


_AGENT_EN = _alt(
    [a for a in lx.OTHER_VEHICLES_EN if a.split()[0] in ("a", "an", "another", "the", "this", "some", "my")]
    + ["someone", "somebody", "a guy", "another driver", "the other driver"]
)
_AGENT_FR = _alt([a for a in lx.OTHER_VEHICLES_FR if a.split()[0] in ("un", "une", "l'auto", "le", "quelqu'un")])
_HIT_FR = _alt([v.split(" ", 1)[1] if v.startswith(("a ", "m'a ", "est ")) else v for v in lx.COLLISION_VERBS_FR])


def _other_party(text: str) -> Hit | None:
    yes = _rx(
        r"\b(a|an|the|another|other) (pickup|truck|car|driver|vehicle|suv|van|bus|cyclist)( \w+)? "
        r"(hit|rear-ended|backed into|ran into|struck|sideswiped)",
        r"\b" + _AGENT_EN + r"(?: \w+){0,2} (?:had )?" + _alt(lx.COLLISION_VERBS_EN) + r"\b",
        r"\b" + _AGENT_FR + r"(?: [\w-]+){0,3} (?:m'a |a |est |m'est )?" + _HIT_FR,
        r"\b(i|we) (got|was|were) (rear-ended|hit|sideswiped|t-boned|clipped|cut off)",
        r"\bje me suis fait (emboutir|frapper|accrocher|rentrer dedans|couper)",
        r"\b(the other|another) (driver|car|vehicle|party)\b",
        r"\b(someone|somebody|a guy|a woman|a man) (hit|rear-ended|backed into|ran into)\b",
        r"\b(rear-ended|t-boned|sideswiped)\b",
        r"\bl'autre (conducteur|conductrice|véhicule|voiture|automobiliste)\b",
        r"\b(une|un) (camionnette|voiture|camion|véhicule) (m'a|a) (frappé|embouti|accroché)",
    )
    no = _rx(
        r"\b(no one|nobody|no other (car|driver|vehicle))( else)? (was )?(involved|there)\b",
        r"\b(single vehicle|just me|only me|i hit (a|the) (pole|deer|curb|tree|post|ditch|wall))\b",
        r"\baucun autre véhicule\b",
        r"\bpersonne d'autre\b",
        r"\b(just|only) (me|us|my car)\b",
        r"\b(juste|seulement) (moi|nous)\b",
        # hitting an object leaves no one else in it; hitting an animal doesn't say (the line still asks)
        r"\b(i|we) (slid into|went into|backed into|swerved into) (a|an|the) (pole|post|tree|curb|ditch|guardrail|"
        r"median|sign|snowbank|wall|bollard|pillar|light post)\b",
    )
    m = no.search(text)
    if m:
        return Hit(False, m.span())
    m = yes.search(text)
    if m:
        return Hit(True, m.span())
    return None


def _clean_name(raw: str) -> str:
    raw = re.split(r"[.,;!?]| and | et ", raw)[0]
    return raw.strip().strip("'\" ")


INSURERS = (
    "Intact", "Aviva", "Wawanesa", "Desjardins", "TD Insurance", "Co-operators", "Cooperators", "Economical",
    "Definity", "Sonnet", "Belairdirect", "belairdirect", "Beneva", "La Capitale", "SSQ", "Promutuel", "RBC Insurance",
    "Northbridge", "Allstate", "State Farm", "Geico", "GEICO", "Progressive", "Farmers", "Liberty Mutual", "USAA",
    "Nationwide", "American Family", "Travelers", "Gore Mutual", "Pembridge", "Square One", "Optimum", "Larkspur",
)  # fmt: skip
_INSURER_NAMES = re.compile(
    r"\b((?:" + "|".join(re.escape(n) for n in sorted(INSURERS, key=len, reverse=True)) + r")"
    r"(?: (?:Insurance|Assurances?|Mutual|Group|General|Auto|Company))*)\b"
)


def _insurer(text: str) -> Hit | None:
    hit = _insurer_said(text)
    if hit is not None:
        return hit
    known = _INSURER_NAMES.search(text)  # a known insurer named anywhere ("He said Intact, I wrote it down")
    if known and not _negated(text, known.start()):
        return Hit(known.group(1), known.span(1), 0.85)
    return None


def _insurer_said(text: str) -> Hit | None:
    m = re.search(
        r"\b(?:insurance|insured|insurer|coverage)(?: is| was)?(?:,)?(?: it's| it is)? (?:with|through|by) "
        r"((?:[A-Z][\w&'-]*\s?){1,5})",
        text,
    )
    if not m:
        m = re.search(
            r"\b(?:it's|it is|they're|they are|he's|she's|he is|she is) (?:with|through|insured (?:with|by|through)) "
            r"((?:[A-Z][\w&'-]*\s?){1,5})",
            text,
        )
    if not m:
        m = re.search(r"\bassuré(?:e)? (?:chez|avec|par) ((?:[A-Z][\w&'-]*\s?){1,5})", text)
    if m:
        name = _clean_name(m.group(1))
        start = m.start(1)
        return Hit(name, (start, start + len(name)))
    return None


def _other_name(text: str) -> Hit | None:
    m = re.search(r"\b(?:his|her|their|the other driver's) name (?:is|was) ((?:[A-Z][\w'-]*\s?){1,3})", text)
    if not m:
        m = re.search(r"\b(?:il|elle) s'appelle ((?:[A-Z][\w'-]*\s?){1,3})", text)
    if m:
        name = _clean_name(m.group(1))
        return Hit(name, (m.start(1), m.start(1) + len(name)))
    return None


def _plate(text: str) -> Hit | None:
    m = re.search(
        r"\b(?:plate|licen[cs]e plate|plaque)(?: number| d'immatriculation)?(?: is| was|,| est)? "
        r"([A-Z0-9][A-Z0-9 -]{2,8}[A-Z0-9])\b",
        text,
        I,
    )
    if m:
        return Hit(m.group(1).upper(), m.span(1))
    return None


def _police_filed(text: str) -> Hit | None:
    yes = _rx(
        r"\b(police|cops|officers?|rcmp|constables?) (came|attended|were (there|here)|was (there|here)|showed up|"
        r"took (a|the|my) (report|statement)|report|are coming|came out|gave me)\b",
        r"\b(report number|file number|incident number|case number|filed a (police )?report|called the (police|cops)|"
        r"police report number|reported it( to the police)?|called it in|filed (it|a report) online|made a report)\b",
        r"\bla police (est venue|est passée|a fait un rapport|est déjà venue)\b",
        r"\b(rapport de police|numéro de rapport|numéro de dossier|un policier|les policiers|une policière|"
        r"appelé la police|fait une (plainte|déclaration)|porté plainte)\b",
    )
    no = _rx(
        r"\b(no|didn't call the|haven't called the|did not call the|didn't call|haven't called) (police|cops)\b",
        r"\bno (police )?report\b",
        r"\b(haven't|have not|didn't|did not) (reported|report|called|filed)\b",
        r"\b(just|only) (swapped|exchanged|traded) (info|information|numbers|insurance)\b",
        r"\bpas (appelé|de|encore appelé|encore) (la )?police\b",
        r"\bpas de (rapport|plainte|police)\b",
    )
    m = no.search(text)
    if m:
        return Hit(False, m.span())
    m = yes.search(text)
    if m:
        return Hit(True, m.span())
    return None


_REPORT_ID = r"([A-Z]{0,4}[ -]?\d[\d -]{2,}\d)"


def _report_number(text: str) -> Hit | None:
    m = re.search(
        r"\b(?:report|rapport|file|case|incident|dossier)(?: number| numéro| no\.?)?(?: is|,| est| c'est)?(?: le)? "
        + _REPORT_ID
        + r"\b",
        text,
        I,
    )
    if m:
        return Hit(m.group(1).upper(), m.span(1))
    return None


def _bare_report_number(text: str) -> Hit | None:
    """The answer to "do you have the report number?" may be the number alone ("Yeah, it's 26-004417")."""
    m = re.search(r"(?<![\w-])" + _REPORT_ID + r"\b", text)
    if m and sum(c.isdigit() for c in m.group(1)) >= 4:
        return Hit(m.group(1).upper(), m.span(1), 0.8)
    return None


_PARTS_EN = (
    "bumper",
    "trunk",
    "tailgate",
    "hood",
    "door",
    "fender",
    "windshield",
    "tail light",
    "taillight",
    "headlight",
    "mirror",
    "quarter panel",
    "roof",
    "shingles",
    "siding",
    "skylight",
    "fence",
    "window",
    "garage door",
    "eavestrough",
    "gutter",
    "soffit",
    "ceiling",
    "drywall",
    "floor",
    "carpet",
    "furnace",
)
_PARTS_FR = (
    "pare-chocs",
    "coffre",
    "capot",
    "portière",
    "aile",
    "pare-brise",
    "phare",
    "rétroviseur",
    "toit",
    "bardeaux",
    "revêtement",
    "puits de lumière",
    "lucarne",
    "clôture",
    "fenêtre",
    "porte de garage",
    "gouttière",
    "plafond",
    "plancher",
    "tapis",
)


_ALL_PARTS = tuple(
    dict.fromkeys(
        [*_PARTS_EN, *_PARTS_FR]
        + [
            p
            for p in (*lx.VEHICLE_PARTS_EN, *lx.HOME_PARTS_EN, *lx.VEHICLE_PARTS_FR, *lx.HOME_PARTS_FR)
            if len(p) > 3
            and p not in ("side", "wall", "frame", "vent", "porte", "vitre", "deck", "patio")
            and not p.startswith(("l'", "le ", "côté", "back end", "front end", "rear end", "driver's side"))
            and not p.endswith(" side")
        ]
    )
)


def _damage_areas(text: str) -> Hit | None:
    found: list[tuple[int, int, str]] = []
    for part in sorted(_ALL_PARTS, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(part) + r"s?\b", text, I):
            after = text[m.end() : m.end() + 24]
            if re.match(r"('s| is| are| looks?| seems?)? (fine|okay|ok|intact|good|est correct|va bien)", after, I):
                continue  # "the roof is fine": not damaged
            if _negated(text, m.start()):
                continue  # "no damage to the hood"
            if not any(a <= m.start() < b or m.start() <= a < m.end() for a, b, _ in found):
                found.append((m.start(), m.end(), part))
    if not found:
        return None
    found.sort()
    names: list[str] = []
    for _, _, p in found:
        if p not in names:
            names.append(p)
    return Hit(", ".join(names), (found[0][0], found[-1][1]), 0.85)


def _drivable(text: str) -> Hit | None:
    no = _rx(
        r"\b(won't start|doesn't start|can't (be )?driv(e|en)( it)?|not drivable|undrivable|isn't drivable|had to be "
        r"towed|got towed|was towed|being towed|it's totaled|written off|tow truck|towed it|totall?ed|write-off|"
        r"not safe to drive|won't move|leaking (oil|coolant|fluid))\b",
        r"\b(ne roule plus|ne démarre plus|ne démarre pas|remorqu\w+|pas en état de rouler|une remorqueuse|"
        r"perte totale|peut pas (rouler|la conduire|le conduire))\b",
    )
    yes = _rx(
        r"\b(it drives|still drives|it's drivable|is drivable|can (still )?drive (it)?|i drove (it )?(home|here)|"
        r"driving it|it runs fine|it still runs|drives fine|drives okay|it's driveable|still driveable|it starts)\b",
        r"\b(elle roule|il roule|ça roule|elle est en état de rouler|je peux (encore )?la conduire|"
        r"je suis revenue? avec|elle démarre)\b",
    )
    m = no.search(text)
    if m:
        return Hit(False, m.span())
    m = yes.search(text)
    if m:
        return Hit(True, m.span())
    return None


def _airbags(text: str) -> Hit | None:
    m = re.search(r"\bairbags? (went off|deployed|came out)|coussins? gonflables? (se sont )?déployés?", text, I)
    if m:
        return Hit(True, m.span())
    m = re.search(r"\bairbags? (didn't|did not) (go off|deploy)|pas de coussins?", text, I)
    if m:
        return Hit(False, m.span())
    return None


def _witnesses(text: str) -> Hit | None:
    m = re.search(r"\b(a witness|witnesses|someone saw it|people saw|un témoin|des témoins)\b", text, I)
    if m and not re.search(NEG + r"\W+(\w+\W+)?(witness|témoin)", text, I):
        return Hit(True, m.span())
    m = re.search(r"\b(no witnesses|nobody saw|no one saw|aucun témoin|personne n'a vu)\b", text, I)
    if m:
        return Hit(False, m.span())
    return None


_WATER_SOURCE_RX = [
    (re.compile(r"\b" + _alt([w]) + r"s?\b", I), v)
    for w, v in sorted((*lx.WATER_SOURCES_EN, *lx.WATER_SOURCES_FR), key=lambda p: len(p[0]), reverse=True)
    if w not in ("tuyau", "toit", "toiture", "sump")
]


def _water_source(text: str) -> Hit | None:
    """The specific rules first ("a frozen pipe burst"), then the first source named from the lexicon."""
    rules = _water_source_rules(text)
    if rules is not None:
        return rules
    best: Hit | None = None
    for pattern, value in _WATER_SOURCE_RX:
        for m in pattern.finditer(text):
            if _negated(text, m.start()):
                continue
            if best is None or m.start() < best.span[0]:
                best = Hit(value, m.span(), 0.8)
            break
    return best


def _water_source_rules(text: str) -> Hit | None:
    return _first(
        [
            (
                _rx(
                    r"\b(burst|broken|frozen|split|cracked) pipe",
                    r"\bpipe (burst|froze|broke|split|cracked)",
                    r"\btuyau (a )?(éclaté|gelé|fendu|brisé)",
                    r"\b(le )?tuyau a (éclaté|gelé)",
                ),
                "burst_pipe",
            ),
            (_rx(r"\bsewer", r"\b(drain|toilet) backed up", r"\brefoulement", r"\bégout"), "sewer_backup"),
            (_rx(r"\b(river|creek|overland|surface water)", r"\bcrue\b", r"\brivière\b"), "overland"),
            (_rx(r"\broof leak", r"\bleak(ing)? (through|from) the roof", r"\bfuite (du|par le) toit"), "roof"),
            (
                _rx(
                    r"\b(washer|washing machine|dishwasher|water heater|hot water tank|fridge)",
                    r"\b(laveuse|lave-vaisselle|chauffe-eau|réfrigérateur)",
                ),
                "appliance",
            ),
        ],
        text,
    )


def _water_entering(text: str) -> Hit | None:
    no = _rx(
        r"\b(it's |it has |water's |water has )?(stopped|no longer (coming|leaking|dripping))",
        r"\b(shut|turned) (off )?(the )?(main|water|valve)( off)?",
        r"\bn'entre plus\b",
        r"\bne coule plus\b",
        r"\bfermé l'(entrée|eau)",
        r"\b(c'est|ça a|ça s'est|ça a) arrêté\b",
        r"\bit('s| has)? stopped\b",
        r"\b(not (anymore|any more)|dried up|it's dry now|nothing's coming in)\b",
        r"\b(a l'air d'avoir|semble avoir|a|ont) arrêté\b",
    )
    yes = _rx(
        r"\bstill (coming in|coming down|leaking|entering|running|pouring|dripping|seeping|going|trickling)",
        r"\bkeeps (coming|leaking|dripping)",
        r"\b(hasn't|has not|won't|didn't) stop",
        r"\b(entre|coule|dégoutte|s'infiltre) (encore|toujours)",
        r"\bça (n'arrête pas|arrête pas|a pas arrêté)",
    )
    m = yes.search(text)
    if m:
        return Hit(True, m.span())
    m = no.search(text)
    if m:
        return Hit(False, m.span())
    return None


def _mitigation(text: str) -> Hit | None:
    m = _rx(
        r"\b(shut|turned) (off )?(the )?(main|water|valve|gas|power)",
        r"\b(tarp(ed)?|taped|covered|boarded( up)?|put a (bucket|tarp|garbage bag|plastic)|towels|pumped|"
        r"shop vac|wet vac|mopped|moved (everything|things|stuff)|dried|buckets?|fans|dehumidifier|sandbags?)\b",
        r"\b(fermé l'(entrée|eau)|fermer l'eau|coupé l'eau|couper l'eau|bâche|recouvert|seaux?|serviettes|pompé|"
        r"épongé|déshumidificateur|ventilateurs)\b",
    ).search(text)
    if m:
        return Hit(True, m.span())
    return None


_ROOMS = (
    "kitchen",
    "basement",
    "living room",
    "family room",
    "rec room",
    "laundry",
    "laundry room",
    "bedroom",
    "bathroom",
    "garage",
    "dining room",
    "hallway",
    "office",
    "cuisine",
    "sous-sol",
    "salon",
    "salle familiale",
    "buanderie",
    "chambre",
    "salle de bain",
    "salle à manger",
    "corridor",
    "bureau",
)


def _rooms(text: str) -> Hit | None:
    m = re.search(
        r"\b("
        + r"|".join(["one", "two", "three", "four", "five", "\\d+", "deux", "trois", "quatre"])
        + r") rooms?\b|\b(deux|trois|quatre|\d+) pièces\b",
        text,
        I,
    )
    if m:
        n = word_number(m.group(1) or m.group(2))
        if n:
            return Hit(n, m.span(), 0.85)
    found: list[tuple[int, int, str]] = []
    for room in sorted(_ROOMS_ALL, key=len, reverse=True):
        for mm in re.finditer(r"\b" + re.escape(room) + r"s?\b", text, I):
            if not any(a <= mm.start() < b for a, b, _ in found):
                found.append((mm.start(), mm.end(), _ROOM_SAME.get(room, room)))
    if not found:
        return None
    rooms = {r for _, _, r in found}
    if len(rooms) > 1:
        rooms.discard("basement")
        rooms.discard("sous-sol")
    found.sort()
    return Hit(len(rooms), (found[0][0], found[-1][1]), 0.8)


_ROOMS_ALL = tuple(dict.fromkeys([*_ROOMS, *lx.ROOMS_EN, *lx.ROOMS_FR]))
_ROOM_SAME = {"laundry": "laundry room", "salle de bains": "salle de bain", "couloir": "corridor"}
_ROOF_WORDS = (
    r"(roof|roofing|shingles?|skylights?|windows?|flashing|toit|toiture|bardeaux|puits de lumière|lucarne|fenêtres?)"
)


def _roof_window(text: str) -> Hit | None:
    neg = re.search(r"\b(the )?" + _ROOF_WORDS + r"('s| is| are| look| looks)? (fine|okay|ok|intact)\b", text, I)
    if neg:
        return Hit(False, neg.span())
    for m in re.finditer(r"\b" + _ROOF_WORDS + r"\b", text, I):
        if _negated(text, m.start()):
            return Hit(False, m.span(), 0.8)
        return Hit(True, m.span())
    return None


_SIDING_WORDS = (
    r"(siding|fences?|fencing|eavestroughs?|gutters?|soffits?|fascia|downspouts?|stucco|revêtement|parement|crépi|"
    r"clôtures?|gouttières?|soffites?)"
)


def _siding_fence(text: str) -> Hit | None:
    neg = re.search(
        r"\b(the )?" + _SIDING_WORDS + r"('s| is| are| look| looks| seems?)? (fine|okay|ok|intact|good)\b"
        r"|\b(no|not the) " + _SIDING_WORDS + r"\b",
        text,
        I,
    )
    if neg:
        return Hit(False, neg.span())
    for m in re.finditer(r"\b" + _SIDING_WORDS + r"\b", text, I):
        if _negated(text, m.start()):
            return Hit(False, m.span(), 0.8)
        return Hit(True, m.span())
    return None


def _open_to_weather(text: str) -> Hit | None:
    covered = _rx(
        r"\b(tarp(ed)?|taped|covered|boarded( it)?( up)?|sealed|plastic over|garbage bag over|bag over|"
        r"it's dry|nothing('s| is) open|no holes?|not leaking|isn't leaking|nothing's leaking|not open|isn't open)\b",
        r"\b(bâche|recouvert|bouché|c'est sec|rien d'ouvert|pas de trou|pas ouvert)\b",
    ).search(text)
    if covered:
        return Hit(False, covered.span())
    opened = _rx(
        r"\b(hole in the|open to the|wind('s| is) (coming|blowing) in|snow('s| is) coming in|rain('s| is) coming "
        r"in|wide open|smashed|shattered|broken|there's a (big )?hole|you can see the (sky|boards))\b",
        r"\b(un trou|ouvert|fracassé|cassé|brisé)\b",
    ).search(text)
    if opened:
        return Hit(True, opened.span(), 0.75)
    return None


def _debris_source(text: str) -> Hit | None:
    m = re.search(
        r"\b(?:blown|blew|came|flew|ripped|torn) (?:off|from|over from|in from) ((?:the |my |a |our )?[\w' ]{2,40}?)"
        r"(?=[.,;!?]|$| and | that )",
        text,
        I,
    )
    if m:
        v = m.group(1).strip()
        return Hit(v, m.span(1))
    m = re.search(
        r"\b(?:debris|something|a piece) (?:from|off) ((?:the |my |a )?[\w' ]{2,40}?)(?=[.,;!?]|$| and )", text, I
    )
    if m:
        v = m.group(1).strip()
        return Hit(v, m.span(1))
    m = re.search(r"\b(a (?:tree|branch|tree branch|limb)|une branche|un arbre)\b", text, I)
    if m:
        return Hit(m.group(1), m.span(1), 0.8)
    m = re.search(r"\b(?:venu|venue|tombé|tombée)e? (?:de|du|de la|des) ([\w' ]{2,40}?)(?=[.,;!?]|$)", text, I)
    if m:
        return Hit(m.group(1).strip(), m.span(1))
    return None


def _livable(text: str) -> Hit | None:
    no = _rx(
        r"\b(can't|cannot|can not) (stay|live) (here|there|in it)",
        r"\b(not livable|unlivable|have to leave|had to leave|staying (at|with) )",
        r"\b(inhabitable|on ne peut pas (rester|y vivre)|on doit partir)\b",
    )
    yes = _rx(
        r"\b(we |i )?can (still )?(live|stay) (here|there|in it|home)",
        r"\b(we |i )?can (still )?stay\b",
        r"\b(still livable|livable|we're (fine|okay) (staying|here|to stay)|we're staying|we'll stay|staying put)\b",
        r"\b(we're|we are|i'm|i am) (fine|okay|ok|good|alright) (in|at) (the|our|my) (house|home|place)\b",
        r"\b(on peut (encore )?(y )?(vivre|rester)|c'est (encore )?habitable)\b",
    )
    m = no.search(text)
    if m:
        return Hit(False, m.span())
    m = yes.search(text)
    if m:
        return Hit(True, m.span())
    return None


def _lodging(text: str) -> Hit | None:
    m = re.search(r"\b(need (a )?(place|somewhere) to stay|hotel|besoin d'un (hébergement|endroit))\b", text, I)
    if m:
        return Hit(True, m.span())
    return None


def _fire_out(text: str) -> Hit | None:
    m = re.search(
        r"\b(fire('s| is| was) (all |completely )?out|put it out|put out|it's (all |completely )?out( now)?|"
        r"extinguished|feu est éteint|c'est éteint|on l'a éteint|il est éteint|(a été|est) éteint)",
        text,
        I,
    )
    if m and not re.search(r"\b(not|isn't|pas) (completely |all )?(out|éteint)", text, I):
        return Hit(True, m.span())
    return None


def _fire_dept(text: str) -> Hit | None:
    m = re.search(
        r"\b(fire (department|trucks?|fighters|crew|engines?)|firefighters|firemen|pompiers|service d'incendie)\b",
        text,
        I,
    )
    if m and not _negated(text, m.start()) and not re.search(r"\b(no|didn't|pas de|pas les) (fire|pompiers)", text, I):
        return Hit(True, m.span())
    return None


def _items_stolen(text: str) -> Hit | None:
    m = re.search(
        r"\b(?:they took|took|stole|stolen:?|missing:?|ils ont pris|on a volé|ils ont volé) "
        r"((?:my |the |our |a |mon |ma |mes |le |la |les )?[\w' ,-]{2,60}?)(?=[.;!?]|$)",
        text,
        I,
    )
    if m:
        return Hit(m.group(1).strip(), m.span(1), 0.8)
    return None


def _forced(text: str) -> Hit | None:
    no = _rx(
        r"\b(no|without|nothing) (sign of |signs of )?(forced entry|break-?in|damage to the (lock|door|window))",
        r"\b(was|were|been|left) (unlocked|open)\b",
        r"\b(c'était|c'est|était) (pas barré|débarré|ouvert)\b",
        r"\bpas d'effraction\b",
    ).search(text)
    if no:
        return Hit(False, no.span(), 0.8)
    for m in re.finditer(
        r"\b(smashed|broken|broke|kicked in|pried|forced|jimmied|fracass\w*|forcé\w*|brisé\w*|défonc\w*|cassé\w*)\b",
        text,
        I,
    ):
        if _negated(text, m.start()):
            return Hit(False, m.span(), 0.8)  # "nothing broken"
        return Hit(True, m.span(), 0.75)
    return None


def _place(text: str) -> Hit | None:
    pats = [
        r"\bat (?:the corner of )?([A-Z0-9][\w']+(?: [A-Z][\w']+)? and [A-Z0-9][\w']+(?: [A-Z][\w']+)?)",
        r"\b(?:on|along) ([A-Z][\w']+ (?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Trail|Way|Highway|Hwy)"
        r"(?: [A-Z][\w']+)?)",
        r"\b(?:on|at) ([A-Z][\w']+(?: [A-Z][\w']+)?)(?= (?:near|by|at|and|,|\.))",
        r"\b(?:in|at) (?:the |a )?([A-Z][\w' ]+? (?:parking lot|parkade|mall|lot|garage))",
        r"\b(in (?:my|the|our) (?:driveway|garage|parking spot|back yard|yard))",
        r"\b(at (?:home|my house|our house|the house|work))\b",
        r"\bau coin (?:de la |du |de )?([\w' -]+? et [\w' -]+?)(?=[.,]|$)",
        r"\bsur (?:la rue|le boulevard|l'avenue|la route) ([\w' -]+?)(?=[.,]|$| près)",
        r"\b(à la maison|chez (?:moi|nous))\b",
        r"\b(?:dans le|au) stationnement (?:du |de la |de l'|de )?([\w' -]+?)(?=[.,]|$)",
    ]
    for p in pats:
        m = re.search(p, text, I if "[A-Z]" not in p else 0)
        if m:
            return Hit(m.group(1).strip(), m.span(1), 0.85)
    return None


def _relationship(text: str) -> Hit | None:
    m = re.search(
        r"\b(calling (for|on behalf of)|my client|i'm (his|her|their) (lawyer|representative|agent|brother|sister|"
        r"friend|son|daughter)|j'appelle pour|au nom de)\b",
        text,
        I,
    )
    if m:
        return Hit("other", m.span())
    m = re.search(
        r"\b(my (husband|wife|partner)'s|it's my (husband|wife|partner)|mon (mari|conjoint)|ma (femme|conjointe))\b",
        text,
        I,
    )
    if m:
        return Hit("spouse", m.span(), 0.8)
    return None


def _estimate(text: str) -> Hit | None:
    hit = find_money(text)
    if hit:
        amount, span = hit
        return Hit(money_band(amount), span, 0.85)
    return None


def _emergency(text: str) -> Hit | None:
    m = re.search(r"\b(called 911|ambulance (came|is coming)|paramedics|appelé le 911|ambulanciers)\b", text, I)
    if m:
        return Hit(True, m.span())
    return None


EXTRACTORS: dict[str, Callable[[str], Hit | None]] = {
    "loss_type": loss_type,
    "injury_reported": _injury,
    "injury_detail": _injury_detail,
    "danger_now": _danger,
    "power_out": _power_out,
    "emergency_services_called": _emergency,
    "other_party_involved": _other_party,
    "other_party_insurer": _insurer,
    "other_party_name": _other_name,
    "other_party_plate": _plate,
    "police_report_filed": _police_filed,
    "police_report_number": _report_number,
    "damage_areas": _damage_areas,
    "vehicle_drivable": _drivable,
    "airbags_deployed": _airbags,
    "witnesses": _witnesses,
    "water_source": _water_source,
    "water_still_entering": _water_entering,
    "mitigation_taken": _mitigation,
    "rooms_affected": _rooms,
    "roof_or_window_damage": _roof_window,
    "siding_or_fence_damage": _siding_fence,
    "open_to_weather": _open_to_weather,
    "debris_source": _debris_source,
    "home_livable": _livable,
    "temporary_lodging_needed": _lodging,
    "fire_out": _fire_out,
    "fire_department_attended": _fire_dept,
    "items_stolen": _items_stolen,
    "forced_entry": _forced,
    "loss_place": _place,
    "caller_relationship": _relationship,
    "caller_damage_estimate_band": _estimate,
}

_FILLER = re.compile(
    r"^\s*(?:(?:um+|uh+|well|so|oh|okay|ok|yeah|yes|sure|euh|ben|bon|alors|oui|ah)[,.!]?\s+)+", re.IGNORECASE
)


_NOT_KNOWN = re.compile(
    r"\b(don't know|do not know|not sure|no idea|didn't get|did not get|can't remember|don't remember|"
    r"je ne sais pas|je sais pas|aucune idée|pas sûre?|je ne me souviens pas|je l'ai pas)\b|^\s*(nothing|none|rien)\b",
    re.IGNORECASE,
)


def _whole(text: str) -> Hit | None:
    if _NOT_KNOWN.search(text) or NO.search(text):
        return None  # "I don't know" is not an answer to a free-text question
    m = _FILLER.match(text)
    start = m.end() if m else 0
    body = text[start:].strip()
    if len(body) < 2:
        return None
    end = start + len(text[start:].rstrip())
    return Hit(text[start:end].rstrip(" .!"), (start, end), 0.65)


def extract_values(
    text: str,
    language: str,
    expecting: Sequence[SlotSpec],
    *,
    asked: str | None,
    now: datetime,
    filled: Mapping[str, Any],
    region: str | None = None,
    correcting: bool = False,
) -> list[SlotValue]:
    """Values heard in `text` for the expected fields. Spans index into `text` (the redacted utterance)."""
    out: list[SlotValue] = []
    today = now.date()
    prior_time = time.fromisoformat(filled["loss_time"]) if isinstance(filled.get("loss_time"), str) else None
    time_hit = None
    keys = {s.key: s for s in expecting}

    def add(key: str, hit: Hit | None) -> None:
        if hit is None or hit.value in (None, ""):
            return
        old = filled.get(key)
        corrects = old is not None and old != hit.value
        if corrects and not (correcting or key == asked or key in UPDATABLE):
            return  # a passing re-mention never silently overwrites a value
        if old is not None and old == hit.value and key != asked:
            return
        out.append(
            SlotValue(key, hit.value, display(key, hit.value, language), hit.confidence, hit.span, corrects=corrects)
        )

    if "loss_time" in keys:
        th = find_time(text, now=now, prior=prior_time)
        if th is not None:
            time_hit = th
            add("loss_time", Hit(th.value.strftime("%H:%M"), th.span, 0.9 if th.explicit_half else 0.75))
    if "loss_date" in keys:
        dh = find_date(text, today=today, loss_time=time_hit.value if time_hit else None)
        if dh is not None and dh.value <= today:
            add("loss_date", Hit(dh.value.isoformat(), dh.span))
        elif time_hit is not None and time_hit.relative_minutes is not None:
            when = (now.replace(second=0, microsecond=0)).date()
            add("loss_date", Hit(when.isoformat(), time_hit.span, 0.85))
    if "date_of_birth" in keys:
        dh = find_date(text, today=date(today.year + 1, 1, 1), loss_time=None)
        if dh is not None and dh.has_year and dh.value.year < today.year - 14:
            out.append(SlotValue("date_of_birth", dh.value.isoformat(), "", 0.9, dh.span))
    if "postal_code" in keys:
        ph = find_postal(text)
        if ph is not None:
            out.append(SlotValue("postal_code", ph[0], ph[0], 0.9, ph[1]))
    if "policy_number" in keys:
        pn = find_policy_number(text, region)
        if pn is not None:
            out.append(SlotValue("policy_number", pn[0], pn[0], 0.95, pn[1]))
    for key in ("callback_number", "photo_number"):
        if key in keys:
            phone = find_phone(text)
            if phone is not None:
                out.append(SlotValue(key, phone[0], phone[0], 0.9, phone[1]))
    for spec in expecting:
        fn = EXTRACTORS.get(spec.key)
        if fn is None:
            continue
        hit = fn(text)
        if hit is None and spec.key == asked and spec.key in NAME_FIELDS:
            name = re.match(r"^\s*(?:it's |it is |c'est )?((?:[A-Z][\w&'-]*\s?){1,5}?)\s*[.!]?\s*$", text)
            if name:
                hit = Hit(name.group(1).strip(), name.span(1), 0.8)
        if hit is None and spec.key == asked == "police_report_number":
            hit = _bare_report_number(text)
        if hit is None and spec.key == asked:
            if spec.kind == "yes_no" and not correcting:
                hit = yes_no(text)
                if hit is not None:
                    hit = Hit(hit.value, hit.span, 0.85)
            elif spec.kind in ("text", "address") and spec.key in FREE_TEXT:
                hit = _whole(text)
        add(spec.key, hit)
    if asked and asked not in {v.key for v in out} and asked in keys and asked not in EXTRACTORS:
        spec = keys[asked]
        if spec.kind == "yes_no" and not correcting:
            yn = yes_no(text)
            if yn is not None:
                add(asked, yn)
        elif spec.kind in ("text", "address") and asked in FREE_TEXT:
            add(asked, _whole(text))
    return out
