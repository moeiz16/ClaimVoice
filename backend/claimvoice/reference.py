"""Reference data shared by the API (`GET /meta`), the seed, the dialogue scripts and the models. Labels are the words
people see (EN/FR)."""

from __future__ import annotations

# Loss types are about what happened, not which policy line; one loss can touch a home and a vehicle
# (the policy and insured items say which). Scripts exist per loss type (Settings › Scripts).
LOSS_TYPES: dict[str, dict[str, str]] = {
    "collision": {"en": "Collision", "fr": "Collision"},
    "hail": {"en": "Hail", "fr": "Grêle"},
    "wind": {"en": "Wind", "fr": "Vent"},
    "water": {"en": "Water", "fr": "Dégât d'eau"},
    "fire": {"en": "Fire or smoke", "fr": "Incendie ou fumée"},
    "theft": {"en": "Theft or break-in", "fr": "Vol ou introduction par effraction"},
}

ROUTES: dict[str, dict[str, str]] = {
    "fast_track": {"en": "Fast-track", "fr": "Traitement rapide"},
    "adjuster": {"en": "Adjuster", "fr": "Expert en sinistres"},
    "special_investigation": {"en": "Closer look", "fr": "Examen approfondi"},
}

CHECKS: dict[str, dict[str, str]] = {
    "size": {"en": "Size check", "fr": "Vérification de l'ampleur"},
    "closer_look": {"en": "Closer-look check", "fr": "Vérification d'examen approfondi"},
}

# Recording consent per region. All-party regions need a yes before anything is kept. Canada: provincial and federal
# privacy law (Alberta PIPA, Québec's private-sector act as amended by Law 25, PIPEDA) require notice and consent for
# recorded business calls, so Canadian regions are treated as all-party.
REGIONS: dict[str, dict[str, str]] = {
    "CA-AB": {
        "en": "Alberta",
        "fr": "Alberta",
        "country": "CA",
        "consent": "all_party",
        "basis": "Alberta Personal Information Protection Act: notice and consent",
    },
    "CA-QC": {
        "en": "Québec",
        "fr": "Québec",
        "country": "CA",
        "consent": "all_party",
        "basis": "Québec private-sector privacy act (Law 25): consent; French first",
    },
    "CA-ON": {
        "en": "Ontario",
        "fr": "Ontario",
        "country": "CA",
        "consent": "all_party",
        "basis": "PIPEDA: notice and consent",
    },
    "US-CO": {
        "en": "Colorado",
        "fr": "Colorado",
        "country": "US",
        "consent": "one_party",
        "basis": "C.R.S. 18-9-303 (one-party consent); the line still announces recording",
    },
    "US-CA": {
        "en": "California",
        "fr": "Californie",
        "country": "US",
        "consent": "all_party",
        "basis": "California Penal Code §632 (all-party consent)",
    },
    "US-WA": {
        "en": "Washington",
        "fr": "Washington",
        "country": "US",
        "consent": "all_party",
        "basis": "RCW 9.73.030 (all-party consent)",
    },
    "US-FL": {
        "en": "Florida",
        "fr": "Floride",
        "country": "US",
        "consent": "all_party",
        "basis": "Fla. Stat. 934.03 (all-party consent)",
    },
    "US-IL": {
        "en": "Illinois",
        "fr": "Illinois",
        "country": "US",
        "consent": "all_party",
        "basis": "720 ILCS 5/14-2 (all-party consent)",
    },
}

DEMO_SCENARIOS: dict[str, dict[str, str]] = {
    "calgary-windstorm": {"en": "Chinook wind damage to a home, Calgary", "fr": "Dommages causés par le vent, Calgary"},
    "denver-rear-end": {"en": "Rear-ended at a light, Denver", "fr": "Collision arrière à un feu, Denver"},
    "montreal-basement": {
        "en": "Burst pipe, basement flooded, Montréal",
        "fr": "Tuyau éclaté, sous-sol inondé, Montréal",
    },
}
