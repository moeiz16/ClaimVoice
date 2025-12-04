"""Claim-file fields (docs/API_CONTRACT.md §5.4): section, kind, labels and how a value reads in English and French.

The platform builds `ClaimFile.sections` from `SLOT_CATALOG`; the engine uses `display()` so a value reads the same in
the claim file, the read-back and the summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any

SECTIONS: dict[str, dict[str, str]] = {
    "caller": {"en": "Caller", "fr": "Appelant"},
    "policy": {"en": "Policy", "fr": "Police"},
    "loss": {"en": "What happened", "fr": "Ce qui s'est passé"},
    "details": {"en": "Details", "fr": "Détails"},
    "safety": {"en": "Safety", "fr": "Sécurité"},
    "photos": {"en": "Photos", "fr": "Photos"},
    "coverage": {"en": "Coverage", "fr": "Couverture"},
    "next_steps": {"en": "Next steps", "fr": "Prochaines étapes"},
}


@dataclass(frozen=True, slots=True)
class SlotDef:
    key: str
    section: str
    kind: str  # text | date | time | yes_no | phone | number | choice | address | policy_number | money_band
    en: str
    fr: str
    choices: tuple[str, ...] = ()

    def label(self, language: str) -> str:
        return self.fr if language == "fr" else self.en


_DEFS: tuple[SlotDef, ...] = (
    # caller
    SlotDef("caller_name", "caller", "text", "Caller", "Appelant"),
    SlotDef(
        "caller_relationship",
        "caller",
        "choice",
        "Relationship to the policy",
        "Lien avec la police",
        ("policyholder", "spouse", "driver", "other"),
    ),
    SlotDef("callback_number", "caller", "phone", "Call-back number", "Numéro de rappel"),
    SlotDef("preferred_language", "caller", "choice", "Language", "Langue", ("en", "fr")),
    # policy
    SlotDef("policy_number", "policy", "policy_number", "Policy", "Police"),
    SlotDef("identity_check", "policy", "choice", "Identity checked", "Identité vérifiée", ("passed", "failed")),
    SlotDef("insured_item", "policy", "text", "Insured item", "Bien assuré"),
    # loss
    SlotDef(
        "loss_type",
        "loss",
        "choice",
        "What happened",
        "Type de sinistre",
        ("collision", "hail", "wind", "water", "fire", "theft"),
    ),
    SlotDef("loss_date", "loss", "date", "Date of loss", "Date du sinistre"),
    SlotDef("loss_time", "loss", "time", "Time of loss", "Heure du sinistre"),
    SlotDef("loss_place", "loss", "address", "Where", "Lieu"),
    SlotDef("loss_description", "loss", "text", "In the caller's words", "Dans les mots de l'appelant"),
    SlotDef(
        "caller_damage_estimate_band",
        "loss",
        "money_band",
        "Caller's estimate",
        "Estimation de l'appelant",
        ("under_2k", "2k_10k", "10k_50k", "over_50k"),
    ),
    # details (auto)
    SlotDef("vehicle_drivable", "details", "yes_no", "Vehicle can be driven", "Véhicule en état de rouler"),
    SlotDef("damage_areas", "details", "text", "Damage", "Dommages"),
    SlotDef("other_party_involved", "details", "yes_no", "Another party involved", "Autre partie en cause"),
    SlotDef("other_party_name", "details", "text", "Other party", "Autre partie"),
    SlotDef("other_party_insurer", "details", "text", "Other party's insurer", "Assureur de l'autre partie"),
    SlotDef("other_party_plate", "details", "text", "Other party's plate", "Plaque de l'autre partie"),
    SlotDef("police_report_filed", "details", "yes_no", "Police report", "Rapport de police"),
    SlotDef("police_report_number", "details", "text", "Police report number", "Numéro du rapport de police"),
    SlotDef("witnesses", "details", "yes_no", "Witnesses", "Témoins"),
    SlotDef("airbags_deployed", "details", "yes_no", "Airbags deployed", "Coussins gonflables déployés"),
    # details (property)
    SlotDef(
        "water_source",
        "details",
        "choice",
        "Where the water came from",
        "Source de l'eau",
        ("burst_pipe", "sewer_backup", "overland", "roof", "appliance", "other"),
    ),
    SlotDef("water_still_entering", "details", "yes_no", "Water still coming in", "L'eau entre encore"),
    SlotDef("rooms_affected", "details", "number", "Rooms affected", "Pièces touchées"),
    SlotDef("mitigation_taken", "details", "yes_no", "Steps taken to limit damage", "Mesures prises"),
    SlotDef("roof_or_window_damage", "details", "yes_no", "Roof, window or skylight damage", "Toit ou fenêtres"),
    SlotDef("siding_or_fence_damage", "details", "yes_no", "Siding or fence damage", "Revêtement ou clôture"),
    SlotDef("open_to_weather", "details", "yes_no", "Open to the weather", "Ouvert aux intempéries"),
    SlotDef("debris_source", "details", "text", "What hit it", "Ce qui a frappé"),
    SlotDef("home_livable", "details", "yes_no", "Home can be lived in", "Logement habitable"),
    SlotDef(
        "temporary_lodging_needed", "details", "yes_no", "Needs somewhere to stay", "Besoin d'un hébergement temporaire"
    ),
    SlotDef("fire_out", "details", "yes_no", "Fire is out", "Le feu est éteint"),
    SlotDef("fire_department_attended", "details", "yes_no", "Fire department came", "Pompiers sur place"),
    SlotDef("items_stolen", "details", "text", "What was taken", "Ce qui a été volé"),
    SlotDef("forced_entry", "details", "yes_no", "Signs of forced entry", "Entrée par effraction"),
    SlotDef("extra_notes", "details", "text", "Also noted", "Aussi noté"),
    # safety
    SlotDef("injury_reported", "safety", "yes_no", "Someone hurt", "Personne blessée"),
    SlotDef("injury_detail", "safety", "text", "Injury", "Blessure"),
    SlotDef("danger_now", "safety", "yes_no", "Danger right now", "Danger immédiat"),
    SlotDef("emergency_services_called", "safety", "yes_no", "Emergency services called", "Services d'urgence appelés"),
    SlotDef("power_out", "safety", "yes_no", "Power out", "Panne de courant"),
    # photos
    SlotDef("photos_promised", "photos", "yes_no", "Photos coming", "Photos à venir"),
    SlotDef("photo_link_sent_to", "photos", "phone", "Photo link texted to", "Lien texté au"),
    # coverage
    SlotDef("coverage_lines_mentioned", "coverage", "text", "Coverage explained", "Couverture expliquée"),
    SlotDef("deductible_mentioned", "coverage", "text", "Deductible", "Franchise"),
    # next steps
    SlotDef("next_steps_given", "next_steps", "text", "Next steps given", "Prochaines étapes données"),
    SlotDef("adjuster_contact_window", "next_steps", "text", "We'll call by", "Nous rappellerons d'ici"),
)

SLOT_CATALOG: dict[str, SlotDef] = {d.key: d for d in _DEFS}

# Facts whose change during a call counts as a "story change" sign (date, place or sequence of events).
KEY_FACTS: frozenset[str] = frozenset(
    {"loss_date", "loss_time", "loss_place", "loss_description", "other_party_involved"}
)

_WEEKDAYS = {
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
}
_MONTHS = {
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    "fr": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
}
_CHOICE_WORDS: dict[str, dict[str, str]] = {
    "burst_pipe": {"en": "a burst pipe", "fr": "un tuyau éclaté"},
    "sewer_backup": {"en": "a sewer backup", "fr": "un refoulement d'égout"},
    "overland": {"en": "water from outside", "fr": "de l'eau venue de l'extérieur"},
    "roof": {"en": "the roof", "fr": "le toit"},
    "appliance": {"en": "an appliance", "fr": "un appareil"},
    "other": {"en": "something else", "fr": "autre chose"},
    "policyholder": {"en": "the policyholder", "fr": "le titulaire"},
    "spouse": {"en": "spouse or partner", "fr": "conjoint"},
    "driver": {"en": "the driver", "fr": "le conducteur"},
    "passed": {"en": "Checked", "fr": "Vérifiée"},
    "failed": {"en": "Not confirmed", "fr": "Non confirmée"},
    "under_2k": {"en": "under $2,000", "fr": "moins de 2 000 $"},
    "2k_10k": {"en": "$2,000 to $10,000", "fr": "de 2 000 $ à 10 000 $"},
    "10k_50k": {"en": "$10,000 to $50,000", "fr": "de 10 000 $ à 50 000 $"},
    "over_50k": {"en": "over $50,000", "fr": "plus de 50 000 $"},
    "en": {"en": "English", "fr": "anglais"},
    "fr": {"en": "French", "fr": "français"},
}
LOSS_WORDS: dict[str, dict[str, str]] = {
    "collision": {"en": "a collision", "fr": "une collision"},
    "hail": {"en": "hail damage", "fr": "des dommages causés par la grêle"},
    "wind": {"en": "wind damage", "fr": "des dommages causés par le vent"},
    "water": {"en": "water damage", "fr": "un dégât d'eau"},
    "fire": {"en": "a fire", "fr": "un incendie"},
    "theft": {"en": "a theft or break-in", "fr": "un vol ou une entrée par effraction"},
}


def format_date(d: date, language: str) -> str:
    wd = _WEEKDAYS["fr" if language == "fr" else "en"][d.weekday()]
    month = _MONTHS["fr" if language == "fr" else "en"][d.month - 1]
    if language == "fr":
        day = "1er" if d.day == 1 else str(d.day)
        return f"{wd} {day} {month}"
    return f"{wd} {d.day} {month}"


def format_time(t: time, language: str) -> str:
    if language == "fr":
        return f"vers {t.hour} h {t.minute:02d}" if t.minute else f"vers {t.hour} h"
    hour = t.hour % 12 or 12
    half = "a.m." if t.hour < 12 else "p.m."
    if t.hour == 0 and t.minute == 0:
        return "about midnight"
    return f"about {hour}:{t.minute:02d} {half}" if t.minute else f"about {hour} {half}"


def yes_no_words(value: bool, language: str) -> str:
    if language == "fr":
        return "Oui" if value else "Non"
    return "Yes" if value else "No"


def display(key: str, value: Any, language: str) -> str:
    """How a value reads in the claim file, in the call's language. Never shows a code."""
    spec = SLOT_CATALOG.get(key)
    kind = spec.kind if spec else "text"
    if value is None:
        return ""
    if kind == "date" and isinstance(value, str):
        return format_date(date.fromisoformat(value), language)
    if kind == "time" and isinstance(value, str):
        return format_time(time.fromisoformat(value), language)
    if kind == "yes_no" and isinstance(value, bool):
        return yes_no_words(value, language)
    if key == "loss_type" and isinstance(value, str):
        from claimvoice.reference import LOSS_TYPES

        return LOSS_TYPES.get(value, {}).get(language, value)
    if kind in ("choice", "money_band") and isinstance(value, str) and value in _CHOICE_WORDS:
        return _CHOICE_WORDS[value]["fr" if language == "fr" else "en"]
    if kind == "number" and isinstance(value, int | float):
        return str(int(value))
    return str(value)


def required_keys(script_keys: list[str]) -> list[str]:
    """Fields every claim needs whatever the loss type, plus the script's required fields."""
    base = ["policy_number", "loss_type", "loss_date", "injury_reported"]
    return base + [k for k in script_keys if k not in base]
