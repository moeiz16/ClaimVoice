"""Historical calls for the seed (1 December to this morning): transcripts with real character spans, claim-file
values, timelines and consent, written straight to the database (fast), then closed through the same
`calls.closing.finalize` a live call uses, so every route, sign and quality score comes from the scorers.

Transcripts are built from bilingual templates per loss type. Times are offsets from the demo moment."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from claimvoice.calls.models import Call, CallEvent, CallSlot, CallTurn, Handoff
from claimvoice.dialogue.slots import display
from claimvoice.platform.db import new_id
from claimvoice.policies.models import Policy, Policyholder

LINE_MS_PER_CHAR = 58
CALLER_MS_PER_CHAR = 66


@dataclass
class Say:
    speaker: str  # caller | line | system
    stage: str
    text: str
    slots: list[tuple[str, Any, str | None]] = field(default_factory=list)  # (key, value, phrase in text)
    redactions: int = 0
    flags: list[str] = field(default_factory=list)


@dataclass
class Story:
    """Everything one historical call needs."""

    holder: Policyholder
    policy: Policy
    loss_type: str
    answered_at: datetime
    loss_date: date
    language: str
    variant: str = "normal"  # normal | missed_consent | late_handoff | card_number | no_safety | short | abandoned
    injury: bool = False
    facts: dict[str, Any] = field(default_factory=dict)
    claim_number: str | None = None
    caller_name: str | None = None
    caller_relationship: str = "policyholder"
    extra: dict[str, Any] = field(default_factory=dict)


def _t(lang: str, en: str, fr: str) -> str:
    return fr if lang == "fr" else en


def _when(d: date, today: date, lang: str) -> str:
    days = (today - d).days
    if days == 0:
        return _t(lang, "this morning", "ce matin")
    if days == 1:
        return _t(lang, "yesterday", "hier")
    from claimvoice.dialogue.slots import format_date

    return _t(lang, "on ", "le ") + format_date(d, lang)


# ---------------------------------------------------------------- loss-type details (question, answer, slots)

Detail = tuple[str, str, list[tuple[str, Any, str | None]]]


def collision_details(rng: random.Random, s: Story) -> tuple[str, list[Detail]]:
    lang = s.language
    where = rng.choice(
        [
            ("in a parking lot", "dans un stationnement"),
            ("at a red light", "à un feu rouge"),
            ("merging onto the highway", "en m'engageant sur l'autoroute"),
            ("on my street", "dans ma rue"),
        ]
    )
    how = rng.choice(
        [
            ("Someone backed into my car", "Quelqu'un a reculé dans ma voiture"),
            ("I was rear-ended", "On m'a embouti par l'arrière"),
            (
                "Another car clipped my side mirror and door",
                "Une autre voiture a accroché mon rétroviseur et ma portière",
            ),
        ]
    )
    desc = f"{how[0 if lang == 'en' else 1]} {where[0 if lang == 'en' else 1]}"
    other = rng.random() < 0.8
    police = other and rng.random() < 0.55
    drivable = rng.random() < 0.8
    areas = rng.choice(
        [
            ("rear bumper", "pare-chocs arrière"),
            ("driver's door", "portière du conducteur"),
            ("front bumper and headlight", "pare-chocs avant et phare"),
        ]
    )
    area = areas[0 if lang == "en" else 1]
    details: list[Detail] = [
        (
            _t(lang, "Can the vehicle still be driven safely?", "Le véhicule peut-il encore rouler en sécurité?"),
            _t(
                lang,
                "Yes, it drives fine." if drivable else "No, it isn't safe to drive.",
                "Oui, il roule bien." if drivable else "Non, il n'est pas sécuritaire.",
            ),
            [("vehicle_drivable", drivable, None)],
        ),
        (
            _t(lang, "Where is the damage?", "Où sont les dommages?"),
            _t(lang, f"Mostly the {area}.", f"Surtout le {area}."),
            [("damage_areas", area, area)],
        ),
        (
            _t(
                lang,
                "Was another vehicle or person involved?",
                "Une autre personne ou un autre véhicule était-il en cause?",
            ),
            _t(
                lang,
                "Yes, the other driver stopped and we swapped information." if other else "No, they drove off.",
                "Oui, l'autre conducteur s'est arrêté et on a échangé nos informations."
                if other
                else "Non, il est parti.",
            ),
            [("other_party_involved", other, None)],
        ),
        (
            _t(
                lang,
                "Did the police come, or did you file a report?",
                "La police est-elle venue, ou avez-vous fait un rapport?",
            ),
            _t(
                lang,
                "Yes, there's a police report." if police else "No, we didn't call the police.",
                "Oui, il y a un rapport de police." if police else "Non, on n'a pas appelé la police.",
            ),
            [("police_report_filed", police, None)],
        ),
    ]
    return desc, details


def water_details(rng: random.Random, s: Story) -> tuple[str, list[Detail]]:
    lang = s.language
    source = rng.choice(["burst_pipe", "burst_pipe", "sewer_backup", "appliance"])
    phrase = {
        "burst_pipe": ("a pipe burst in the cold", "un tuyau a éclaté avec le froid"),
        "sewer_backup": ("the floor drain backed up", "le drain de plancher a refoulé"),
        "appliance": ("the washing machine hose split", "le boyau de la laveuse a fendu"),
    }[source]
    room = rng.choice(
        [("the basement", "le sous-sol"), ("the kitchen", "la cuisine"), ("the laundry room", "la salle de lavage")]
    )
    desc = _t(
        lang, f"Water damage: {phrase[0]} and flooded {room[0]}", f"Dégât d'eau : {phrase[1]} et a inondé {room[1]}"
    )
    entering = rng.random() < 0.25
    rooms = rng.choice([1, 1, 2, 3])
    details: list[Detail] = [
        (
            _t(lang, "Where did the water come from?", "D'où venait l'eau?"),
            _t(lang, f"It looks like {phrase[0]}.", f"On dirait que {phrase[1]}."),
            [("water_source", source, None)],
        ),
        (
            _t(lang, "Is water still coming in right now?", "L'eau entre-t-elle encore en ce moment?"),
            _t(
                lang,
                "Yes, it's still dripping." if entering else "No, I shut the water off.",
                "Oui, ça coule encore." if entering else "Non, j'ai fermé l'eau.",
            ),
            [("water_still_entering", entering, None)],
        ),
        (
            _t(lang, "How many rooms are affected?", "Combien de pièces sont touchées?"),
            _t(lang, f"{rooms} room{'s' if rooms > 1 else ''}.", f"{rooms} pièce{'s' if rooms > 1 else ''}."),
            [("rooms_affected", rooms, str(rooms))],
        ),
        (
            _t(lang, "Have you been able to do anything to limit the damage?", "Avez-vous pu limiter les dommages?"),
            _t(lang, "I moved things out and put towels down.", "J'ai sorti les choses et mis des serviettes."),
            [("mitigation_taken", True, None)],
        ),
        (
            _t(lang, "Can you still live in the home?", "Pouvez-vous encore habiter le logement?"),
            _t(lang, "Yes, we're fine upstairs.", "Oui, ça va en haut."),
            [("home_livable", True, None)],
        ),
    ]
    s.extra["room"] = room[0 if lang == "en" else 1]
    return desc, details


def theft_details(rng: random.Random, s: Story) -> tuple[str, list[Detail]]:
    lang = s.language
    auto = s.policy.line == "auto"
    items = (
        rng.choice(
            [
                ("my catalytic converter", "mon convertisseur catalytique"),
                ("tools from the truck", "des outils du camion"),
            ]
        )
        if auto
        else rng.choice(
            [
                ("a laptop and a bike", "un portable et un vélo"),
                ("my snowblower from the garage", "ma souffleuse du garage"),
            ]
        )
    )
    desc = _t(lang, f"Someone stole {items[0]}", f"Quelqu'un a volé {items[1]}")
    police = rng.random() < 0.7
    forced = rng.random() < 0.6
    item = items[0 if lang == "en" else 1]
    details: list[Detail] = [
        (
            _t(lang, "What was taken?", "Qu'est-ce qui a été volé?"),
            _t(lang, f"They took {item}.", f"Ils ont pris {item}."),
            [("items_stolen", item, item)],
        ),
        (
            _t(lang, "Were there signs of forced entry?", "Y avait-il des signes d'entrée par effraction?"),
            _t(
                lang,
                "Yes, the lock was broken." if forced else "No, nothing was broken.",
                "Oui, la serrure était brisée." if forced else "Non, rien n'était brisé.",
            ),
            [("forced_entry", forced, None)],
        ),
        (
            _t(lang, "Have you reported it to the police?", "L'avez-vous signalé à la police?"),
            _t(
                lang,
                "Yes, I filed a report online." if police else "Not yet.",
                "Oui, j'ai fait un rapport en ligne." if police else "Pas encore.",
            ),
            [("police_report_filed", police, None)],
        ),
    ]
    return desc, details


def wind_details(rng: random.Random, s: Story) -> tuple[str, list[Detail]]:
    lang = s.language
    what = rng.choice(
        [
            ("the wind took shingles off the roof", "le vent a arraché des bardeaux du toit", True, False),
            ("the wind blew our fence down", "le vent a renversé notre clôture", False, True),
            (
                "a gust tore the siding off the north wall",
                "une rafale a arraché le revêtement du mur nord",
                False,
                True,
            ),
        ]
    )
    desc = _t(lang, f"Wind damage: {what[0]}", f"Dommages causés par le vent : {what[1]}")
    debris = rng.choice(
        [("a branch from the neighbour's tree", "une branche de l'arbre du voisin"), ("nothing hit it", "rien")]
    )
    details: list[Detail] = [
        (
            _t(
                lang,
                "Is there damage to the roof, windows or skylights?",
                "Le toit, les fenêtres ou les puits de lumière sont-ils endommagés?",
            ),
            _t(
                lang,
                "Yes, the roof." if what[2] else "No, the roof looks fine.",
                "Oui, le toit." if what[2] else "Non, le toit semble correct.",
            ),
            [("roof_or_window_damage", what[2], None)],
        ),
        (
            _t(lang, "Any damage to siding or fences?", "Des dommages au revêtement ou aux clôtures?"),
            _t(lang, "Yes." if what[3] else "No.", "Oui." if what[3] else "Non."),
            [("siding_or_fence_damage", what[3], None)],
        ),
        (
            _t(lang, "Did something hit it?", "Quelque chose l'a-t-il frappé?"),
            _t(lang, f"I think {debris[0]}.", f"Je pense que c'est {debris[1]}."),
            [("debris_source", debris[0 if lang == "en" else 1], debris[0 if lang == "en" else 1])],
        ),
        (
            _t(
                lang,
                "Is any part of the home open to the weather?",
                "Une partie du logement est-elle exposée aux intempéries?",
            ),
            _t(lang, "No, it's closed up.", "Non, c'est fermé."),
            [("open_to_weather", False, None)],
        ),
        (
            _t(lang, "Can you still live in the home?", "Pouvez-vous encore habiter le logement?"),
            _t(lang, "Yes.", "Oui."),
            [("home_livable", True, None)],
        ),
    ]
    return desc, details


def fire_details(rng: random.Random, s: Story) -> tuple[str, list[Detail]]:
    lang = s.language
    desc = _t(lang, "A small kitchen fire from the stove", "Un petit feu de cuisine causé par la cuisinière")
    details: list[Detail] = [
        (
            _t(lang, "Is the fire completely out?", "Le feu est-il complètement éteint?"),
            _t(lang, "Yes, it's out.", "Oui, il est éteint."),
            [("fire_out", True, None)],
        ),
        (
            _t(lang, "Did the fire department come?", "Les pompiers sont-ils venus?"),
            _t(lang, "Yes, they checked everything.", "Oui, ils ont tout vérifié."),
            [("fire_department_attended", True, None)],
        ),
        (
            _t(lang, "Can you still live in the home?", "Pouvez-vous encore habiter le logement?"),
            _t(lang, "Yes, just the smell is bad.", "Oui, c'est surtout l'odeur."),
            [("home_livable", True, None)],
        ),
    ]
    return desc, details


DETAILS: dict[str, Callable[[random.Random, Story], tuple[str, list[Detail]]]] = {
    "collision": collision_details,
    "water": water_details,
    "theft": theft_details,
    "wind": wind_details,
    "fire": fire_details,
}
OPENERS = {
    "collision": ("Hi, I need to report a car accident.", "Bonjour, je dois déclarer un accident de voiture."),
    "water": ("Hi, we've got water damage in the house.", "Bonjour, on a un dégât d'eau dans la maison."),
    "theft": ("Hello, I need to report a theft.", "Bonjour, je dois déclarer un vol."),
    "wind": ("Hi, the wind damaged our house.", "Bonjour, le vent a endommagé notre maison."),
    "fire": ("Hi, we had a small fire at home.", "Bonjour, on a eu un petit feu à la maison."),
}


def build_turns(rng: random.Random, s: Story, today: date) -> list[Say]:
    lang = s.language
    t = _t
    out: list[Say] = []
    greeting = Say(
        "line",
        "greeting",
        t(
            lang,
            "Larkspur Mutual claims, this is ClaimVoice. I can help in English or French. What happened?",
            "Mutuelle Larkspur, réclamations, ici ClaimVoice. Je peux vous "
            "aider en français ou en anglais. Que s'est-il passé?",
        ),
    )
    out.append(greeting)
    out.append(Say("caller", "greeting", OPENERS[s.loss_type][0 if lang == "en" else 1]))
    consent = [
        Say(
            "line",
            "consent",
            t(
                lang,
                "I'm sorry to hear that. This call is recorded to help with your claim. Is that okay with you?",
                "Désolé d'entendre ça. Cet appel est enregistré pour traiter votre réclamation. Êtes-vous d'accord?",
            ),
        ),
        Say("caller", "consent", t(lang, "Yes, that's fine.", "Oui, c'est correct.")),
    ]
    if s.variant == "abandoned":
        return out + consent[:1]
    if s.variant != "missed_consent":
        out += consent
    number = s.policy.policy_number
    out.append(
        Say(
            "line", "identity", t(lang, "Thanks. What's your policy number?", "Merci. Quel est votre numéro de police?")
        )
    )
    out.append(
        Say("caller", "identity", t(lang, f"It's {number}.", f"C'est {number}."), [("policy_number", number, number)])
    )
    out.append(
        Say(
            "line",
            "identity",
            t(
                lang,
                "Thank you. To make sure it's you, what's your date of birth?",
                "Merci. Pour confirmer votre identité, quelle est votre date de naissance?",
            ),
        )
    )
    from claimvoice.dialogue.slots import format_date

    dob = s.holder.date_of_birth
    dob_words = format_date(dob, lang).split(" ", 1)[1] + f" {dob.year}"
    out.append(
        Say("caller", "identity", t(lang, f"{dob_words}.", f"Le {dob_words}."), [("identity_check", "passed", None)])
    )
    if s.variant == "card_number":
        out.append(
            Say(
                "caller",
                "identity",
                t(
                    lang,
                    "Do you need my card to pay the deductible? It's [card number removed].",
                    "Vous voulez ma carte pour la franchise? C'est [card number removed].",
                ),
                redactions=1,
                flags=["card_number_removed"],
            )
        )
        out.append(
            Say(
                "line",
                "identity",
                t(
                    lang,
                    "For your security, please don't share card numbers on this line. "
                    "We never take payment on this call.",
                    "Pour votre sécurité, ne donnez pas de numéro de carte sur cette ligne. "
                    "Nous ne prenons jamais de paiement pendant cet appel.",
                ),
            )
        )
    if s.variant != "no_safety":
        out.append(
            Say(
                "line",
                "safety",
                t(
                    lang,
                    "Before anything else: is everyone safe, and is anything dangerous right now?",
                    "Avant tout : tout le monde est-il en sécurité, et y a-t-il un danger en ce moment?",
                ),
            )
        )
        if s.injury:
            sore = t(lang, "a sore back", "mal au dos")
            out.append(
                Say(
                    "caller",
                    "safety",
                    t(lang, f"I've got {sore}, but nothing dangerous.", f"J'ai {sore}, mais pas de danger."),
                    [("injury_reported", True, None), ("injury_detail", sore, sore), ("danger_now", False, None)],
                )
            )
            out.append(
                Say(
                    "line",
                    "safety",
                    t(
                        lang,
                        "I'm sorry you're hurt. Please look after yourself first.",
                        "Je suis désolé que vous soyez blessé. Prenez soin de vous d'abord.",
                    ),
                )
            )
        else:
            out.append(
                Say(
                    "caller",
                    "safety",
                    t(lang, "Everyone's fine, nothing dangerous.", "Tout le monde va bien, aucun danger."),
                    [("injury_reported", False, None), ("danger_now", False, None)],
                )
            )
    desc, details = DETAILS[s.loss_type](rng, s)
    when = _when(s.loss_date, today, lang)
    hour = rng.choice([7, 8, 11, 14, 16, 18, 21, 23])
    tm = f"{hour:02d}:{rng.choice(['00', '15', '30', '45'])}"
    from claimvoice.dialogue.slots import format_time

    tm_words = format_time(datetime.strptime(tm, "%H:%M").time(), lang)
    out.append(
        Say(
            "line",
            "loss_type",
            t(lang, "Thank you. Tell me what happened, and when.", "Merci. Dites-moi ce qui s'est passé, et quand."),
        )
    )
    out.append(
        Say(
            "caller",
            "loss_type",
            f"{desc}, {when}, {tm_words}.",
            [
                ("loss_type", s.loss_type, None),
                ("loss_description", desc, desc),
                ("loss_date", s.loss_date.isoformat(), when),
                ("loss_time", tm, tm_words),
                ("loss_place", s.holder.city, None),
            ],
        )
    )
    if s.variant == "missed_consent":
        out += consent
    if s.variant == "late_handoff":
        out.append(
            Say(
                "caller",
                "loss_details",
                t(
                    lang,
                    "Actually, can I talk to a real person please?",
                    "En fait, est-ce que je peux parler à une vraie personne?",
                ),
            )
        )
    for i, (q, a, slots) in enumerate(details):
        if s.variant == "short" and i >= 1:
            break
        out.append(Say("line", "loss_details", q))
        out.append(Say("caller", "loss_details", a, slots))
        if s.variant == "late_handoff" and i == 1:
            out.append(
                Say(
                    "line",
                    "handoff",
                    t(
                        lang,
                        "Of course. I'm connecting you with a person now; they'll have everything you told me.",
                        "Bien sûr. Je vous mets en contact avec une personne; elle aura tout ce que vous m'avez dit.",
                    ),
                )
            )
            return out
    if s.variant == "short":
        out.append(
            Say(
                "caller",
                "loss_details",
                t(lang, "Sorry, I have to go, I'll call back.", "Désolé, je dois y aller, je rappellerai."),
            )
        )
        return out
    out.append(
        Say(
            "line",
            "photos",
            t(
                lang,
                "Can I text you a link so you can send photos of the damage?",
                "Puis-je vous texter un lien pour envoyer des photos des dommages?",
            ),
        )
    )
    out.append(
        Say("caller", "photos", t(lang, "Yes please.", "Oui, s'il vous plaît."), [("photos_promised", True, None)])
    )
    cov = s.extra.get("coverage_words") or t(
        lang,
        "Your policy includes coverage for this kind of loss. An adjuster confirms "
        "what's covered; nothing is decided on this call.",
        "Votre police comprend une garantie pour ce type de sinistre. Un expert confirmera ce qui "
        "est couvert; rien n'est décidé pendant cet appel.",
    )
    out.append(Say("line", "coverage", cov, [("coverage_lines_mentioned", s.extra.get("coverage_label", ""), None)]))
    out.append(Say("caller", "coverage", t(lang, "Okay, thanks.", "D'accord, merci.")))
    out.append(
        Say(
            "line",
            "read_back",
            t(
                lang,
                f"Let me read that back: {desc.lower()}, {when}. Is that right?",
                f"Je relis : {desc.lower()}, {when}. Est-ce exact?",
            ),
        )
    )
    out.append(Say("caller", "read_back", t(lang, "Yes, that's right.", "Oui, c'est exact.")))
    number_words = s.claim_number or ""
    out.append(
        Say(
            "line",
            "wrap_up",
            t(
                lang,
                f"Your claim number is {number_words}. Someone will call you within one business day. "
                "Is there anything else?",
                f"Votre numéro de réclamation est {number_words}. Quelqu'un vous rappellera d'ici un jour "
                "ouvrable. Autre chose?",
            ),
            [("next_steps_given", t(lang, "A call within one business day", "Un appel d'ici un jour ouvrable"), None)],
        )
    )
    out.append(Say("caller", "wrap_up", t(lang, "No, that's everything. Thank you.", "Non, c'est tout. Merci.")))
    s.extra["description"] = f"{desc}, {when}."
    return out


def write_call(
    session: Any, org_id: str, s: Story, turns: list[Say], *, reference: str, rng: random.Random
) -> tuple[Call, list[Any]]:
    """Rows for one finished call (not yet closed): the call, turns, slots, timeline. Returns (call, rows)."""
    call = Call(
        id=new_id(),
        org_id=org_id,
        reference=reference,
        mode="voice",
        channel="phone",
        language=s.language,
        state="ended",
        stage="ended",
        answered_at=s.answered_at,
        caller_phone_e164=s.holder.phone_e164,
        caller_name=s.caller_name or s.holder.full_name,
        caller_verified=True,
        region=s.policy.region,
        place=s.holder.city,
        loss_type=s.loss_type,
        policy_id=s.policy.id,
        holder_id=s.holder.id,
        outcome="in_progress",
        is_sample=True,
        claim_number=s.claim_number,
        facts=dict(s.facts),
        mood={"key": "calm", "detail": None},
    )
    rows: list[Any] = []
    at = 0
    stage_seen: list[str] = []
    events: list[CallEvent] = [
        CallEvent(
            org_id=org_id,
            call_id=call.id,
            at=s.answered_at,
            at_ms=0,
            kind="answered",
            label="ClaimVoice answered",
            data={},
        )
    ]
    seq = 0
    prev_stage = "greeting"
    flags: list[dict[str, Any]] = []
    for say in turns:
        seq += 1
        dur = len(say.text) * (CALLER_MS_PER_CHAR if say.speaker == "caller" else LINE_MS_PER_CHAR)
        at += rng.randint(350, 900)
        if say.stage not in stage_seen:
            stage_seen.append(say.stage)
            if say.stage != "greeting":
                events.append(
                    CallEvent(
                        org_id=org_id,
                        call_id=call.id,
                        at=s.answered_at + timedelta(milliseconds=at),
                        at_ms=at,
                        kind="stage",
                        label=say.stage.replace("_", " ").capitalize(),
                        data={"stage": say.stage, "previous": prev_stage, "event": "seeded"},
                    )
                )
                prev_stage = say.stage
        turn_id = new_id()
        rows.append(
            CallTurn(
                id=turn_id,
                org_id=org_id,
                call_id=call.id,
                seq=seq,
                speaker=say.speaker,
                text=say.text,
                text_en=None,
                language=s.language,
                at_ms=at,
                end_ms=at + dur,
                stage=say.stage,
                confidence=round(rng.uniform(0.86, 0.98), 2) if say.speaker == "caller" else None,
                redactions=say.redactions,
                flags=list(say.flags),
                created_at=s.answered_at + timedelta(milliseconds=at),
            )
        )
        if say.stage == "consent" and say.speaker == "caller":
            call.consent = {
                "rule": "all_party" if s.policy.region != "US-CO" else "one_party",
                "region": s.policy.region,
                "answer": "given",
                "recording": True,
                "askedAt": (s.answered_at + timedelta(milliseconds=at)).isoformat(),
                "turnId": turn_id,
            }
            events.append(
                CallEvent(
                    org_id=org_id,
                    call_id=call.id,
                    at=s.answered_at + timedelta(milliseconds=at),
                    at_ms=at,
                    kind="consent",
                    label="Agreed to recording",
                    data={
                        "rule": call.consent["rule"],
                        "answer": "given",
                        "recording": True,
                        "region": s.policy.region,
                        "turnId": turn_id,
                    },
                )
            )
        if say.flags:
            for kind in say.flags:
                detail = "A card number was removed before anything was stored."
                flags.append(
                    {
                        "kind": kind,
                        "detail": detail,
                        "at": (s.answered_at + timedelta(milliseconds=at)).isoformat(),
                        "turnId": turn_id,
                    }
                )
                events.append(
                    CallEvent(
                        org_id=org_id,
                        call_id=call.id,
                        at=s.answered_at + timedelta(milliseconds=at),
                        at_ms=at,
                        kind="flag",
                        label="Card number removed",
                        data={"kind": kind, "detail": detail, "turnId": turn_id},
                    )
                )
        for key, value, phrase in say.slots:
            span = None
            if phrase:
                i = say.text.find(phrase)
                span = (i, i + len(phrase)) if i >= 0 else None
            source = "heard" if say.speaker == "caller" else "tool"
            if key == "identity_check":
                source = "tool"
            rows.append(
                CallSlot(
                    org_id=org_id,
                    call_id=call.id,
                    key=key,
                    value=value,
                    display=display(key, value, s.language),
                    confidence=0.93 if source == "heard" else None,
                    source=source,
                    turn_id=turn_id if source == "heard" else None,
                    span_start=span[0] if span else None,
                    span_end=span[1] if span else None,
                    at_ms=at if source == "heard" else None,
                    confirmed=True,
                    created_at=s.answered_at + timedelta(milliseconds=at),
                )
            )
        if say.stage == "identity" and say.speaker == "caller" and any(k == "policy_number" for k, _, _ in say.slots):
            events.append(
                CallEvent(
                    org_id=org_id,
                    call_id=call.id,
                    at=s.answered_at + timedelta(milliseconds=at + dur),
                    at_ms=at + dur,
                    kind="tool",
                    label=f"Policy found in 0.{rng.randint(1, 3)} s",
                    data={"tool": "policy_lookup", "ok": True, "timedOut": False},
                )
            )
        if say.stage == "photos" and say.speaker == "caller":
            events.append(
                CallEvent(
                    org_id=org_id,
                    call_id=call.id,
                    at=s.answered_at + timedelta(milliseconds=at + dur),
                    at_ms=at + dur,
                    kind="photo_link",
                    label="Photo link texted",
                    data={"toMasked": "•••-•••-" + s.holder.phone_e164[-4:]},
                )
            )
        if say.stage == "handoff":
            events.append(
                CallEvent(
                    org_id=org_id,
                    call_id=call.id,
                    at=s.answered_at + timedelta(milliseconds=at),
                    at_ms=at,
                    kind="handoff",
                    label="Hand-off asked: Asked for a person",
                    data={"reason": "caller_asked", "priority": "normal", "atMs": at, "state": "waiting"},
                )
            )
            rows.append(
                Handoff(
                    org_id=org_id,
                    call_id=call.id,
                    reason="caller_asked",
                    detail="Asked for a person partway through the details.",
                    priority="normal",
                    state="accepted",
                    requested_at=s.answered_at + timedelta(milliseconds=at),
                    accepted_at=s.answered_at + timedelta(milliseconds=at + 35_000),
                    summary=f"{s.holder.full_name}, policy {s.policy.policy_number}.",
                    actions=[],
                )
            )
            events.append(
                CallEvent(
                    org_id=org_id,
                    call_id=call.id,
                    at=s.answered_at + timedelta(milliseconds=at + 35_000),
                    at_ms=at + 35_000,
                    kind="handoff",
                    label="A person joined the call",
                    data={"reason": "caller_asked", "priority": "normal", "state": "accepted"},
                )
            )
            at += 35_000 + 90_000
        at += dur
    call.flags = flags
    heard_keys = {k for say in turns for k, _, _ in say.slots}
    if "loss_type" not in heard_keys:
        call.loss_type = None
    if "policy_number" not in heard_keys:
        call.policy_id = call.holder_id = None
        call.caller_verified = False
        call.caller_name = None
    end = s.answered_at + timedelta(milliseconds=at + 1500)
    call.ended_at = end
    call.end_reason = "completed" if turns[-1].stage == "wrap_up" else "caller_hung_up"
    call.recording_seconds = round((at + 1500) / 1000, 1)
    call.resume_stage = turns[-1].stage
    call.summary = s.extra.get("description")
    if s.language == "fr" and call.summary:
        call.summary_en = s.extra.get("description_en")
    call.turn_count = seq
    if not call.consent:
        rule = "all_party" if s.policy.region != "US-CO" else "one_party"
        call.consent = {"rule": rule, "region": s.policy.region, "answer": "pending", "recording": False}
        if rule == "all_party":  # nothing is kept before the caller says yes
            for row in rows:
                if isinstance(row, CallTurn):
                    row.retained = False
    rows.extend(events)
    rows.append(
        CallEvent(
            org_id=org_id,
            call_id=call.id,
            at=end,
            at_ms=at + 1500,
            kind="ended",
            label="Call ended",
            data={"reason": call.end_reason},
        )
    )
    return call, rows
