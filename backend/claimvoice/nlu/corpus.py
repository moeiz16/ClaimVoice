"""Training sentences for the loss-type classifier: a seeded lexicon-and-template paraphrase generator, plus the turns
of the main scripted callers (eval/callers/*.yml, never the held-out sets).

Every generated sentence is a caller describing a loss (collision, hail, wind, water, fire, theft) or a turn that is
not a description at all (`none`: a yes, a date, a policy number, a safety answer, a question, a generic "I need to
open a claim"). Sentences are composed from an opener, a hedge, one or two clauses built from `nlu.lexicon`, and a
tail, in English and Canadian French. docs/NLU_CORPUS.md lists the templates and why each exists.

`split="train"` and `split="val"` divide every word list by a stable hash (one item in five goes to validation), so
the validation sentences use verbs, objects, causes and places the training sentences never contain. That is what
calibration and the thresholds are fitted on: wording the model has not seen, not a re-shuffle of the same phrases.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from claimvoice.nlu import lexicon as lx

SEED = 11
Split = str  # "train" | "val" | "all"


@dataclass(frozen=True, slots=True)
class Example:
    text: str
    label: str
    language: str
    source: str  # "generated" | "scripted"


def _in_split(item: str, split: Split) -> bool:
    if split == "all":
        return True
    bucket = int(hashlib.md5(item.encode("utf-8"), usedforsecurity=False).hexdigest(), 16) % 5
    return (bucket == 0) == (split == "val")


class _Pick:
    """Random choice from a word list, restricted to this split's share of the list."""

    def __init__(self, rng: random.Random, split: Split) -> None:
        self.rng = rng
        self.split = split
        self._cache: dict[tuple[str, ...], list[str]] = {}

    def __call__(self, items: Sequence[str]) -> str:
        key = tuple(items)
        pool = self._cache.get(key)
        if pool is None:
            pool = [i for i in items if i == "" or _in_split(i, self.split)] or list(items)
            self._cache[key] = pool
        return self.rng.choice(pool)

    def pair(self, items: Sequence[tuple[str, str]]) -> tuple[str, str]:
        return items[self.rng.randrange(len(items))] if self.split == "all" else self._pair(items)

    def _pair(self, items: Sequence[tuple[str, str]]) -> tuple[str, str]:
        pool = [p for p in items if _in_split(p[0], self.split)] or list(items)
        return self.rng.choice(pool)

    def maybe(self, p: float) -> bool:
        return self.rng.random() < p


def _cap(s: str) -> str:
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def _sentence(opener: str, hedge: str, body: str, tail: str, end: str = ".") -> str:
    body = (hedge + body).strip()
    text = opener + (body if opener.endswith((", ", "parce que ", "because ", "but ")) else _cap(body)) + tail + end
    return " ".join(text.split())


# ------------------------------------------------------------------ English clauses per loss type

_GOT_EN = ("rear-ended", "hit", "sideswiped", "t-boned", "clipped", "hit from behind", "cut off and hit", "bumped")
_ACCIDENT_EN = (
    "I was in an accident", "I had a fender bender", "there was a crash", "I got in a car accident",
    "I was in a collision", "I had a little accident with the car", "we had an accident on the way home",
)  # fmt: skip
_CAR_STATE_EN = (
    "the {part} is smashed", "the {part} is crushed", "the {part} is hanging off", "there's a big dent in the {part}",
    "the {part} is scraped up", "the {part} is caved in", "the {part} won't close",
)  # fmt: skip
_SOMEONE_EN = ("someone", "somebody", "a thief", "thieves", "some guys", "they", "a guy", "some kids", "whoever it was")
_FLOODED_EN = (
    "is flooded", "is under water", "is soaked", "has an inch of water in it", "took on water", "is full of water",
    "has water all over the floor", "is wet everywhere", "is ruined with water",
)  # fmt: skip
_WATER_LOC_EN = (
    "through the ceiling", "into the basement", "under the sink", "across the kitchen floor", "behind the drywall",
    "out of the light fixture", "around the toilet", "under the fridge", "into the crawl space", "down the stairs",
    "through the bathroom ceiling", "under the baseboards", "into the furnace room", "all over the laundry room",
)  # fmt: skip
_SOURCE_FAIL_EN = (
    "burst", "split", "let go", "failed", "overflowed", "backed up", "sprang a leak", "quit", "started leaking",
    "flooded everything", "gave out", "cracked", "blew", "busted",
)  # fmt: skip
_HAIL_STATE_EN = ("dented", "cracked", "smashed", "pitted", "destroyed", "beat up", "chipped", "wrecked", "damaged")
_HAIL_HIT_EN = (
    "we got hit by hail",
    "there's hail damage all over",
    "a hailstorm came through",
    "it hailed like crazy",
)
_IN_ROOM_EN = (
    "",
    " in the kitchen",
    " in the basement",
    " in the garage",
    " in the living room",
    " in the laundry room",
)


def _collision_en(p: _Pick) -> str:
    r = p.rng.random()
    if r < 0.42:
        clause = f"{p(lx.OTHER_VEHICLES_EN)} {p(lx.COLLISION_VERBS_EN)} {p(lx.COLLISION_OBJECTS_EN)}"
    elif r < 0.6:
        clause = p(lx.SINGLE_VEHICLE_EN)
    elif r < 0.75:
        clause = f"I got {p(_GOT_EN)}"
    elif r < 0.87:
        clause = f"my {p(lx.VEHICLES_EN)} got {p(lx.COLLISION_VERBS_EN)} by {p(lx.OTHER_VEHICLES_EN)}"
    else:
        clause = p(_ACCIDENT_EN)
    clause += p(lx.COLLISION_PLACES_EN)
    if p.maybe(0.12):
        clause += p((" and just drove off", " and took off", " and kept going", " and didn't stop"))
    if p.maybe(0.3):
        clause += ", and " + p(_CAR_STATE_EN).format(part=p(lx.VEHICLE_PARTS_EN))
    return clause


def _water_en(p: _Pick) -> str:
    source, _ = p.pair(lx.WATER_SOURCES_EN)
    r = p.rng.random()
    if r < 0.3:
        clause = f"there's water {p(lx.WATER_VERBS_EN)} {p(_WATER_LOC_EN)}"
    elif r < 0.55:
        clause = f"the {source} {p(_SOURCE_FAIL_EN)}"
    elif r < 0.72:
        clause = f"my {p(lx.ROOMS_EN)} {p(_FLOODED_EN)}"
    elif r < 0.86:
        clause = f"water is {p(lx.WATER_VERBS_EN)} {p(_WATER_LOC_EN)} from the {source}"
    else:
        clause = p(
            (
                f"we've got a leak in the {p(lx.ROOMS_EN)}",
                f"there's a leak in the {p(lx.HOME_PARTS_EN)}",
                "the basement flooded",
                "sewage came up through the floor drain",
                f"the {p(lx.HOME_PARTS_EN)} is soaked",
                "we have water damage",
                f"there's a {p(('brown', 'water', 'big wet', 'yellow'))} stain on the {p(('ceiling', 'wall'))} that "
                f"{p(('keeps growing', 'showed up overnight', 'is getting bigger'))}",
                f"the {p(('drywall', 'paint', 'ceiling'))} is {p(('bubbling', 'sagging', 'wet and soft'))}",
                f"the {p(('hardwood', 'laminate', 'carpet'))} is {p(('warped', 'buckling', 'soaking wet'))}",
            )
        )
    if p.maybe(0.3):
        clause += f" and the {p(lx.ROOMS_EN)} {p(_FLOODED_EN)}"
    return clause


def _wind_en(p: _Pick) -> str:
    r = p.rng.random()
    if r < 0.6:
        clause = f"{p(lx.WIND_CAUSES_EN)} {p(lx.WIND_VERBS_EN)} {p(lx.WIND_TARGETS_EN)}"
    elif r < 0.85:
        clause = p(lx.WIND_FALLS_EN) + p(("", " in the wind", " during the storm", " with all that wind"))
    else:
        clause = f"we've got wind damage to the {p(lx.HOME_PARTS_EN)}"
    if p.maybe(0.3):
        clause += f" and {p(lx.WIND_VERBS_EN)} {p(lx.WIND_TARGETS_EN)}"
    return clause


def _hail_en(p: _Pick) -> str:
    r = p.rng.random()
    if r < 0.55:
        clause = f"{p(lx.HAIL_CAUSES_EN)} {p(lx.HAIL_VERBS_EN)} {p(lx.HAIL_TARGETS_EN)}"
    elif r < 0.75:
        clause = f"{p(lx.HAIL_TARGETS_EN)} got {p(lx.HAIL_VERBS_EN)} by {p(lx.HAIL_CAUSES_EN)}"
    else:
        clause = p(_HAIL_HIT_EN)
    if p.maybe(0.35):
        clause += f" and {p(lx.HAIL_TARGETS_EN)} is {p(_HAIL_STATE_EN)}"
    return clause


def _fire_en(p: _Pick) -> str:
    clause = p(lx.FIRE_EVENTS_EN) + p(_IN_ROOM_EN)
    if p.maybe(0.5):
        clause += ", " + p(lx.FIRE_AFTER_EN)
    return clause


def _theft_en(p: _Pick) -> str:
    r = p.rng.random()
    if r < 0.4:
        clause = f"{p(_SOMEONE_EN)} {p(lx.THEFT_VERBS_EN)} {p(lx.THEFT_ITEMS_EN)}"
        clause += p(("", " from the driveway", " out of the garage", " from the shed", " out of my car", " overnight"))
    elif r < 0.7:
        clause = f"{p(_SOMEONE_EN)} {p(lx.THEFT_ENTRY_EN)} {p(lx.THEFT_PLACES_EN)}"
        if p.maybe(0.6):
            clause += f" and {p(lx.THEFT_VERBS_EN)} {p(lx.THEFT_ITEMS_EN)}"
    else:
        clause = p(lx.THEFT_PASSIVE_EN)
    return clause


# ------------------------------------------------------------------ French clauses per loss type

_FLOODED_FR = ("est inondé", "est plein d'eau", "est trempé", "a pris l'eau", "a de l'eau partout", "est sous l'eau")
_WATER_LOC_FR = (
    "par le plafond", "dans le sous-sol", "sous l'évier", "le long des murs", "dans la cuisine", "par le luminaire",
    "autour de la toilette", "sous le frigo", "dans la salle de bain", "par la fondation", "dans la buanderie",
)  # fmt: skip
_SOURCE_FAIL_FR = ("a éclaté", "a fendu", "a débordé", "a coulé", "a fui", "a brisé", "a gelé", "a sauté", "a refoulé")
_SOMEONE_FR = ("quelqu'un", "des voleurs", "un voleur", "des jeunes", "ils")
_IN_ROOM_FR = ("", " dans la cuisine", " au sous-sol", " dans le garage", " dans le salon")


def _collision_fr(p: _Pick) -> str:
    r = p.rng.random()
    if r < 0.45:
        clause = f"{p(lx.OTHER_VEHICLES_FR)} {p(lx.COLLISION_VERBS_FR)} {p(lx.COLLISION_OBJECTS_FR)}"
    elif r < 0.65:
        clause = p(lx.SINGLE_VEHICLE_FR)
    elif r < 0.8:
        clause = p(
            ("j'ai eu un accident", "j'ai eu un accrochage", "on a eu un accident d'auto", "il y a eu une collision")
        )
    else:
        clause = f"je me suis fait {p(('emboutir', 'frapper', 'accrocher', 'rentrer dedans', 'couper'))}"
    clause += p(lx.COLLISION_PLACES_FR)
    if p.maybe(0.3):
        clause += f", le {p(('pare-chocs', 'capot', 'coffre', 'phare'))} est {p(('défoncé', 'enfoncé', 'brisé'))}"
    return clause


def _water_fr(p: _Pick) -> str:
    source, _ = p.pair(lx.WATER_SOURCES_FR)
    r = p.rng.random()
    if r < 0.3:
        clause = f"il y a de l'eau qui {p(lx.WATER_VERBS_FR)} {p(_WATER_LOC_FR)}"
    elif r < 0.55:
        if source == "refoulé":
            source = "drain"
        clause = f"{p(('le', 'la', 'mon', 'ma'))} {source} {p(_SOURCE_FAIL_FR)}"
    elif r < 0.75:
        clause = f"mon {p(('sous-sol', 'salon', 'bureau', 'garage', 'corridor'))} {p(_FLOODED_FR)}"
    else:
        clause = p(
            ("on a un dégât d'eau", "on a une infiltration d'eau", "il y a une fuite d'eau", "le sous-sol a été inondé")
        )
    return clause


def _wind_fr(p: _Pick) -> str:
    if p.maybe(0.65):
        return f"{p(lx.WIND_CAUSES_FR)} {p(lx.WIND_VERBS_FR)} {p(lx.WIND_TARGETS_FR)}"
    return p(lx.WIND_FALLS_FR)


def _hail_fr(p: _Pick) -> str:
    if p.maybe(0.7):
        return f"{p(lx.HAIL_CAUSES_FR)} {p(lx.HAIL_VERBS_FR)} {p(lx.HAIL_TARGETS_FR)}"
    return p(
        ("on a eu de la grêle", "il a grêlé fort", "une tempête de grêle est passée", "on a des dommages de grêle")
    )


def _fire_fr(p: _Pick) -> str:
    clause = p(lx.FIRE_EVENTS_FR) + p(_IN_ROOM_FR)
    if p.maybe(0.5):
        clause += ", " + p(lx.FIRE_AFTER_FR)
    return clause


def _theft_fr(p: _Pick) -> str:
    if p.maybe(0.6):
        item = p(lx.THEFT_ITEMS_FR)
        return p(lx.THEFT_FR).format(item=item, item_subj=item)
    clause = p(lx.THEFT_ENTRY_FR)
    if p.maybe(0.4):
        clause += f" et {p(_SOMEONE_FR)} ont pris {p(lx.THEFT_ITEMS_FR)}"
    return clause


# ------------------------------------------------------------------ turns that are not a description (`none`)

_POLICY_REGIONS = ("AB", "CO", "QC", "CA")
_MONTHS_EN = ("January", "March", "April", "June", "July", "August", "September", "October", "November", "December")
_MONTHS_FR = ("janvier", "mars", "avril", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


def _policy(p: _Pick) -> str:
    return f"LM-{p(_POLICY_REGIONS)}-{p.rng.randint(100000, 399999)}"


def _none_en(p: _Pick) -> str:
    day = p.rng.randint(1, 28)
    year = p.rng.randint(1940, 2004)
    kinds: list[Callable[[], str]] = [
        lambda: p(("Yes.", "Sure.", "Yeah, that's fine.", "Okay.", "Go ahead.", "That's okay.", "Yep, no problem.",
                   "Sure, that's fine.", "Of course.", "Fine by me.", "Yes, you can record.", "Uh, sure.")),
        lambda: p(("No, I'd rather you didn't.", "No thanks.", "Please don't record this.", "No.", "Nope.")),
        lambda: p(("It's ", "My policy is ", "Policy number ", "", "Sure, it's ")) + _policy(p) + ".",
        lambda: f"{p(_MONTHS_EN)} {day}, {year}.",
        lambda: f"My postal code is T{p.rng.randint(1, 9)}X {p.rng.randint(1, 9)}A{p.rng.randint(1, 9)}.",
        lambda: p(("We're all fine here, nothing dangerous.", "Nobody's hurt.", "Everyone's okay.", "I'm fine, thanks.",
                   "Yes, everyone's safe.", "No one was hurt, no gas, no smoke.", "We're okay, the power's on.",
                   "I'm a bit shaken but okay.", "Nobody got hurt, luckily.", "All good, nothing dangerous.")),
        lambda: p(("Maybe an hour ago.", "Last night around eleven.", "Yesterday afternoon.", "This morning at six.",
                   "Around two in the morning.", "Maybe twenty minutes ago.", "On Tuesday.", "A couple of days ago.",
                   "Sometime overnight.", "Just after supper.", "Around seven thirty.", "I noticed it this morning.")),
        lambda: p(("In our driveway.", "At home.", "On Crowchild near the university.",
                   "At the corner of 17th and Main.", "Out front of the house.", "In the parking garage at work.",
                   "On Highway 1 near Canmore.")),
        lambda: p(("I need to make a claim.", "I'd like to report a claim.", "I want to open a claim on my policy.",
                   "Hi, I'm calling about my insurance.", "Hello, I need some help.", "Hi, I have a claim to report.",
                   "Something happened and I need to file a claim.", "Hi, is this the claims line?",
                   "I'm calling to start a claim.", "Hello, I was told to call this number.",
                   "I need to report some damage.", "There's some damage I need to report.",
                   "Something happened at the house.",
                   "Something happened to my car.", "I have a problem with my house.", "Hi, I have damage to report.",
                   "We had some damage overnight.", "I'm not sure if this is covered but I need to report something.")),
        lambda: p(("Will my rates go up?", "Is this going to be covered?", "How long will this take?",
                   "Are you a robot?", "What happens next?", "Do I need to get quotes?", "Can I use my own shop?")),
        lambda: p(("Can I talk to a person?", "I want to speak to a real person.", "Put me through to an agent.")),
        lambda: p(("Yes please, text me the link.", "That's right.", "No, that's all for now, thanks.", "Sounds good.",
                   "That's everything.", "Yes, that's all correct.", "Okay, thank you.", "Got it.", "Sorry, what?",
                   "Can you repeat that?", "I'm not sure.", "I don't know.", "Hold on a second.")),
    ]  # fmt: skip
    return p.rng.choice(kinds)()


def _none_fr(p: _Pick) -> str:
    day = p.rng.randint(1, 28)
    year = p.rng.randint(1940, 2004)
    kinds: list[Callable[[], str]] = [
        lambda: p(("Oui.", "Oui, allez-y.", "D'accord.", "Pas de problème.", "Oui, c'est correct.", "Bien sûr.",
                   "Ben oui.", "Correct.", "Oui, ça me convient.", "J'accepte.")),
        lambda: p(("Non, je préfère pas.", "Non merci.", "N'enregistrez pas, s'il vous plaît.", "Non.")),
        lambda: p(("C'est le ", "Mon numéro de police, c'est ", "", "Oui, c'est ")) + _policy(p) + ".",
        lambda: f"Le {day} {p(_MONTHS_FR)} {year}.",
        lambda: f"Mon code postal, c'est H{p.rng.randint(1, 9)}J {p.rng.randint(1, 9)}K{p.rng.randint(1, 9)}.",
        lambda: p(("Personne n'est blessé.", "Tout le monde va bien.", "Oui, ça va, rien de dangereux.",
                   "On va bien, merci.", "Personne de blessé, pas d'odeur de gaz.", "Non, aucun danger.")),
        lambda: p(("Il y a une heure.", "Hier soir vers dix heures.", "Ce matin.", "Cette nuit.", "Mardi passé.",
                   "Hier après-midi.", "Vers sept heures et demie.", "Il y a deux jours.")),
        lambda: p(("Devant chez nous.", "À la maison.", "Sur la rue Saint-Denis.",
                   "Dans le stationnement du travail.")),
        lambda: p(("J'appelle pour faire une réclamation.", "Je voudrais ouvrir un dossier.",
                   "Bonjour, c'est pour une réclamation.", "J'ai besoin d'aide avec mon assurance.",
                   "Bonjour, je dois déclarer un sinistre.",
                   "J'ai des dommages à déclarer.", "Il est arrivé quelque chose à mon auto.",
                   "On a eu des dommages à la maison.", "J'ai un problème avec ma maison.")),
        lambda: p(("Est-ce que ma prime va augmenter?", "Est-ce que c'est couvert?", "Combien de temps ça va prendre?",
                   "Êtes-vous un robot?", "C'est quoi la suite?")),
        lambda: p(("Je veux parler à quelqu'un.", "Je voudrais parler à une vraie personne.")),
        lambda: p(("Oui, envoyez le lien.", "C'est exact.", "Non, c'est tout, merci.", "Parfait.", "Je sais pas.",
                   "Pouvez-vous répéter?", "Un instant.", "Oui, c'est ça.")),
    ]  # fmt: skip
    return p.rng.choice(kinds)()


_CLAUSES: dict[str, dict[str, Callable[[_Pick], str]]] = {
    "en": {
        "collision": _collision_en,
        "water": _water_en,
        "wind": _wind_en,
        "hail": _hail_en,
        "fire": _fire_en,
        "theft": _theft_en,
    },
    "fr": {
        "collision": _collision_fr,
        "water": _water_fr,
        "wind": _wind_fr,
        "hail": _hail_fr,
        "fire": _fire_fr,
        "theft": _theft_fr,
    },
}
PER_LABEL = {"en": 1100, "fr": 550}
NONE_SHARE = 1.6  # `none` gets this many times one loss type's count: it is the most varied class


def generate(*, seed: int = SEED, split: Split = "all", scale: float = 1.0) -> list[Example]:
    """The generated corpus. Same seed and split, same sentences, in the same order."""
    out: list[Example] = []
    for lang in ("en", "fr"):
        rng = random.Random(f"{seed}:{lang}:{split}")  # noqa: S311  (seeded training sentences, not security)
        p = _Pick(rng, split)
        openers = lx.OPENERS_EN if lang == "en" else lx.OPENERS_FR
        hedges = lx.HEDGES_EN if lang == "en" else lx.HEDGES_FR
        tails = lx.TAILS_EN if lang == "en" else lx.TAILS_FR
        n = max(1, int(PER_LABEL[lang] * scale))
        seen: set[str] = set()
        for label, clause_of in _CLAUSES[lang].items():
            made = tries = 0
            while made < n and tries < n * 6:
                tries += 1
                text = _sentence(p(openers), p(hedges), clause_of(p), p(tails))
                if text in seen:
                    continue
                seen.add(text)
                out.append(Example(text, label, lang, "generated"))
                made += 1
        none_fn = _none_en if lang == "en" else _none_fr
        made = tries = 0
        target = int(n * NONE_SHARE)
        while made < target and tries < target * 8:
            tries += 1
            text = none_fn(p)
            key = f"{text}#{made // 40}"  # short fixed answers repeat a little, as they do on real calls
            if key in seen:
                continue
            seen.add(key)
            out.append(Example(text, lx.NONE, lang, "generated"))
            made += 1
    return out


# ------------------------------------------------------------------ the main scripted callers' turns

NOT_DESCRIBING = frozenset({"consent", "identity", "safety", "photos", "coverage", "read_back", "wrap_up"})


def scripted_turns(callers_dir: Path | None = None) -> list[Example]:
    """Turns of the main scripted callers, labelled from the call itself: the opening turn takes the caller's
    expected loss type; turns the rules-only reader placed in consent, identity, safety, photos, coverage, read-back
    or wrap-up are `none` (unless the rules hear a loss type in them). Turns about the loss itself are left out.
    The held-out folders are never read: `load_callers` only globs the top level of eval/callers/."""
    import asyncio

    from claimvoice.contracts import MemoryCallSink
    from claimvoice.dialogue.simulate import load_callers, run_scenario
    from claimvoice.nlu.extract import loss_type
    from claimvoice.nlu.fake import FakeUnderstanding

    out: list[Example] = []
    callers = load_callers(str(callers_dir) if callers_dir else None)
    for key, caller in callers.items():
        res = asyncio.run(
            run_scenario(caller, MemoryCallSink(), call_id=f"corpus-{key}", nlu=FakeUnderstanding(), hang_up_after=True)
        )
        want = (caller.expect.get("slots") or {}).get("loss_type")
        caller_turns = [t for t in res.engine.turns if t.speaker.value == "caller"]
        for i, t in enumerate(caller_turns):
            if i == 0:
                if want:
                    out.append(Example(t.text, str(want), caller.language, "scripted"))
                continue
            if t.stage in NOT_DESCRIBING and loss_type(t.text) is None:
                out.append(Example(t.text, lx.NONE, t.language, "scripted"))
    return out
