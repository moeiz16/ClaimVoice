"""Plain-words labels for every code the web app shows (EN/FR). The web app never maps codes to words itself."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from claimvoice import reference
from claimvoice.platform.permissions import ROLE_LABELS, Role

Bi = dict[str, str]


def pick(labels: Bi | None, lang: str, fallback: str = "") -> str:
    if not labels:
        return fallback
    return labels.get(lang) or labels.get("en") or fallback


def t(lang: str, en: str, fr: str) -> str:
    return fr if lang == "fr" else en


LINE_STATES: dict[str, Bi] = {
    "ringing": {"en": "Ringing", "fr": "Sonnerie"},
    "with_line": {"en": "With ClaimVoice", "fr": "Avec ClaimVoice"},
    "waiting_for_person": {"en": "Waiting for a person", "fr": "En attente d'une personne"},
    "with_person": {"en": "With a person", "fr": "Avec une personne"},
    "wrapping_up": {"en": "Wrapping up", "fr": "Conclusion"},
    "ended": {"en": "Ended", "fr": "Terminé"},
}

OUTCOMES: dict[str, Bi] = {
    "claim_created": {"en": "Claim opened", "fr": "Réclamation ouverte"},
    "handed_off": {"en": "Handed to a person", "fr": "Transféré à une personne"},
    "abandoned": {"en": "Caller left", "fr": "L'appelant a raccroché"},
    "no_claim": {"en": "No claim", "fr": "Aucune réclamation"},
    "in_progress": {"en": "On the line", "fr": "En ligne"},
}

CLAIM_STATUSES: dict[str, Bi] = {
    "new": {"en": "New", "fr": "Nouvelle"},
    "assigned": {"en": "Assigned", "fr": "Assignée"},
    "in_review": {"en": "In review", "fr": "En examen"},
    "waiting_on_customer": {"en": "Waiting on the customer", "fr": "En attente du client"},
    "closed": {"en": "Closed", "fr": "Fermée"},
}

FLAGS: dict[str, Bi] = {
    "urgent_safety": {"en": "Urgent safety", "fr": "Sécurité urgente"},
    "distress": {"en": "Caller in distress", "fr": "Appelant en détresse"},
    "card_number_removed": {"en": "Card number removed", "fr": "Numéro de carte retiré"},
    "low_confidence": {"en": "Hard to understand", "fr": "Difficile à comprendre"},
    "siu_signal": {"en": "Sign worth a closer look", "fr": "Signe à examiner"},
    "consent_refused": {"en": "Recording declined", "fr": "Enregistrement refusé"},
    "surge": {"en": "Storm surge", "fr": "Afflux lié à la tempête"},
    "language_switched": {"en": "Language switched", "fr": "Langue changée"},
}

FLAG_SEVERITY: dict[str, str] = {
    "urgent_safety": "critical",
    "distress": "warning",
    "card_number_removed": "warning",
    "low_confidence": "warning",
    "siu_signal": "warning",
    "consent_refused": "info",
    "surge": "info",
    "language_switched": "info",
}

HANDOFF_REASONS: dict[str, Bi] = {
    "caller_asked": {"en": "Asked for a person", "fr": "A demandé une personne"},
    "urgent_safety": {"en": "Urgent safety", "fr": "Sécurité urgente"},
    "distress": {"en": "Caller in distress", "fr": "Appelant en détresse"},
    "low_confidence": {"en": "Hard to understand", "fr": "Difficile à comprendre"},
    "identity_unverified": {"en": "Identity not confirmed", "fr": "Identité non confirmée"},
    "tool_failed": {"en": "Policy lookup failed", "fr": "Recherche de police impossible"},
    "consent_refused": {"en": "Declined recording", "fr": "A refusé l'enregistrement"},
    "supervisor": {"en": "Supervisor took the call", "fr": "Prise en charge par un superviseur"},
}

HANDOFF_PRIORITY: dict[str, str] = {
    "urgent_safety": "urgent",
    "distress": "high",
    "identity_unverified": "high",
}

MOODS: dict[str, Bi] = {
    "calm": {"en": "Sounds calm", "fr": "Semble calme"},
    "unsettled": {"en": "Sounds unsettled", "fr": "Semble inquiet"},
    "shaken": {"en": "Sounds shaken", "fr": "Semble secoué"},
    "upset": {"en": "Sounds upset", "fr": "Semble bouleversé"},
}

CONSENT_ANSWERS: dict[str, Bi] = {
    "given": {"en": "Agreed to recording", "fr": "A accepté l'enregistrement"},
    "refused": {"en": "Declined recording", "fr": "A refusé l'enregistrement"},
    "not_required": {"en": "Recording announced", "fr": "Enregistrement annoncé"},
    "pending": {"en": "Not asked yet", "fr": "Pas encore demandé"},
}

CONSENT_RULES: dict[str, Bi] = {
    "one_party": {"en": "One-party consent", "fr": "Consentement d'une partie"},
    "all_party": {"en": "All-party consent", "fr": "Consentement de toutes les parties"},
}

SIU_STATUSES: dict[str, Bi] = {
    "open": {"en": "Waiting for review", "fr": "En attente d'examen"},
    "investigating": {"en": "Being looked at", "fr": "En cours d'examen"},
    "closed_no_concern": {"en": "Closed, no concern", "fr": "Fermé, aucune inquiétude"},
    "returned_to_adjuster": {"en": "Returned to the adjuster", "fr": "Renvoyé à l'expert"},
}

QA_BANDS: dict[str, Bi] = {
    "good": {"en": "Good", "fr": "Bon"},
    "needs_attention": {"en": "Needs attention", "fr": "À surveiller"},
    "failed": {"en": "Missed the rubric", "fr": "Grille non respectée"},
}

SIZE_BANDS: dict[str, Bi] = {
    "small": {"en": "Small", "fr": "Petite"},
    "moderate": {"en": "Moderate", "fr": "Moyenne"},
    "large": {"en": "Large", "fr": "Grande"},
}

FRAUD_BANDS: dict[str, Bi] = {
    "low": {"en": "Nothing stands out", "fr": "Rien de particulier"},
    "elevated": {"en": "Some signs worth a look", "fr": "Quelques signes à examiner"},
    "high": {"en": "Several signs worth a closer look", "fr": "Plusieurs signes à examiner"},
}

POLICY_STATUSES: dict[str, Bi] = {
    "active": {"en": "Active", "fr": "En vigueur"},
    "lapsed": {"en": "Lapsed", "fr": "Échue"},
    "cancelled": {"en": "Cancelled", "fr": "Annulée"},
}

LINES: dict[str, Bi] = {"auto": {"en": "Auto", "fr": "Auto"}, "property": {"en": "Home", "fr": "Habitation"}}

PRODUCTS: dict[str, Bi] = {
    "auto_plus": {"en": "Auto Plus", "fr": "Auto Plus"},
    "home_comprehensive": {"en": "Home Comprehensive", "fr": "Habitation tous risques"},
    "home_standard": {"en": "Home Standard", "fr": "Habitation de base"},
    "condo": {"en": "Condo", "fr": "Copropriété"},
}

COVERAGES: dict[str, Bi] = {
    "liability": {"en": "Liability", "fr": "Responsabilité civile"},
    "collision": {"en": "Collision", "fr": "Collision"},
    "comprehensive": {"en": "Comprehensive", "fr": "Tous risques"},
    "accident_benefits": {"en": "Accident benefits", "fr": "Indemnités d'accident"},
    "rental": {"en": "Rental car", "fr": "Voiture de location"},
    "dwelling": {"en": "Dwelling", "fr": "Bâtiment"},
    "contents": {"en": "Contents", "fr": "Biens meubles"},
    "wind_hail": {"en": "Wind and hail", "fr": "Vent et grêle"},
    "sewer_backup": {"en": "Sewer backup", "fr": "Refoulement d'égout"},
    "overland_water": {"en": "Overland water", "fr": "Inondation terrestre"},
    "water_escape": {"en": "Burst pipes and water escape", "fr": "Dégâts d'eau soudains"},
    "fences": {"en": "Fences and detached structures", "fr": "Clôtures et dépendances"},
    "additional_living": {"en": "Additional living expenses", "fr": "Frais de subsistance supplémentaires"},
}

TEAMS: dict[str, Bi] = {
    "intake": {"en": "Intake team", "fr": "Équipe d'accueil"},
    "adjusters": {"en": "Adjusters", "fr": "Experts en sinistres"},
    "siu": {"en": "Special investigations", "fr": "Enquêtes spéciales"},
}

SLOT_SOURCES: dict[str, Bi] = {
    "policy_record": {"en": "from the policy", "fr": "selon la police"},
    "tool": {"en": "looked up", "fr": "vérifié"},
}

SURGE_KINDS: dict[str, Bi] = {
    "hail": {"en": "Hail", "fr": "Grêle"},
    "flood": {"en": "Flood", "fr": "Inondation"},
    "wind": {"en": "Wind", "fr": "Vent"},
    "winter_storm": {"en": "Winter storm", "fr": "Tempête hivernale"},
    "rainfall": {"en": "Heavy rain", "fr": "Pluie abondante"},
    "wildfire": {"en": "Wildfire", "fr": "Feu de forêt"},
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    "admin": "Claims operations: people, settings and the activity log.",
    "supervisor": "Runs the line desk: listens, whispers, takes over, reviews quality, changes routes and signs "
    "routing checks for claims.",
    "intake_agent": "Takes hand-offs and the calls the line passes over.",
    "adjuster": "Works claims after the call; may change the route with a reason.",
    "siu_investigator": "Reviews closer-look referrals.",
    "compliance": "Quality reviews, the activity log, routing-check sign-off for model risk, privacy officer.",
}


def role_label(role: str) -> str:
    try:
        return ROLE_LABELS[Role(role)]
    except ValueError:
        return role


def loss_type(code: str | None, lang: str) -> str | None:
    return pick(reference.LOSS_TYPES.get(code), lang, code) if code else None


def region(code: str | None, lang: str) -> str | None:
    if not code:
        return None
    info = reference.REGIONS.get(code)
    return (info.get(lang) or info["en"]) if info else code


def route(code: str, lang: str) -> str:
    return pick(reference.ROUTES.get(code), lang, code)


def mask_phone(e164: str | None) -> str | None:
    if not e164:
        return None
    digits = [c for c in e164 if c.isdigit()]
    return "•••-•••-" + "".join(digits[-4:]) if len(digits) >= 4 else "•••"


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return f"{name[:1]}•••@{domain}"


def mask_postal(code: str | None) -> str:
    if not code:
        return "•••"
    return code.strip()[:3].upper() + " •••"


def clock_seconds(seconds: float | None) -> str:
    """'1:52' for the ▸ moment chip."""
    if seconds is None:
        return ""
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


_MONTHS = {
    "en": [
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
    ],
    "fr": [
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
    ],
}
_DAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
}


def day_label(d: date, lang: str) -> str:
    """'Thursday 8 January' / 'jeudi 8 janvier'."""
    key = lang if lang in _DAYS else "en"
    return f"{_DAYS[key][d.weekday()]} {d.day} {_MONTHS[key][d.month - 1]}"


def time_label(dt: datetime, tz: str, lang: str) -> str:
    """'7:42 a.m.' / '7 h 42'."""
    local = dt.astimezone(ZoneInfo(tz))
    if lang == "fr":
        return f"{local.hour} h {local.minute:02d}"
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'a.m.' if local.hour < 12 else 'p.m.'}"


def lit(value: Any) -> Any:
    """A stored code passed to a wire field typed as a closed set of codes (the database guarantees the set)."""
    return value
