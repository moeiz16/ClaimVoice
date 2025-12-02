"""The demo seed plan (docs/DATA.md "Seed plan"). Everything is dated relative to the demo clock: the default demo
moment is Thursday 8 January 2026, 7:42 a.m. Calgary time, the morning after an overnight Chinook windstorm."""

from __future__ import annotations

from dataclasses import dataclass

ORG = {
    "name": "Larkspur Mutual",
    "slug": "larkspur-mutual",
    "timezone": "America/Edmonton",
    "regions": ["CA-AB", "CA-QC", "US-CO"],
    "languages": ["en", "fr"],
}

DEMO_PASSWORD = "larkspur-demo-2026"  # sample org only; shown on the sign-in page as a demo hint
DEMO_TIME = "07:42"  # America/Edmonton, with CLAIMVOICE_DEMO_TODAY=2026-01-08


@dataclass(frozen=True, slots=True)
class Persona:
    role: str
    full_name: str
    email: str
    title: str
    language: str
    color: str
    demo: bool = False  # the person `POST /auth/demo {role}` signs in as


PERSONAS: tuple[Persona, ...] = (
    Persona(
        "supervisor",
        "Renée Kowalchuk",
        "renee.kowalchuk@larkspur.example",
        "Intake supervisor, Calgary",
        "en",
        "orchid",
        demo=True,
    ),
    Persona("adjuster", "Lena Ortiz", "lena.ortiz@larkspur.example", "Adjuster, Denver", "en", "cobalt", demo=True),
    Persona(
        "siu_investigator",
        "Dev Malhotra",
        "dev.malhotra@larkspur.example",
        "Special investigator",
        "en",
        "amber",
        demo=True,
    ),
    Persona(
        "compliance",
        "Priya Sandhu",
        "priya.sandhu@larkspur.example",
        "Model risk and privacy officer",
        "en",
        "plum",
        demo=True,
    ),
    Persona("compliance", "Owen Fairweather", "owen.fairweather@larkspur.example", "Call quality lead", "en", "teal"),
    Persona(
        "admin",
        "Nadia Kassem",
        "nadia.kassem@larkspur.example",
        "Claims operations administrator",
        "en",
        "slate",
        demo=True,
    ),
    Persona("intake_agent", "Jamal Haddad", "jamal.haddad@larkspur.example", "Intake agent", "en", "green", demo=True),
    Persona("intake_agent", "Sofía Herrera", "sofia.herrera@larkspur.example", "Intake agent (EN/ES)", "en", "rose"),
    Persona("intake_agent", "Aurélie Fortin", "aurelie.fortin@larkspur.example", "Intake agent (FR/EN)", "fr", "sky"),
)

COUNTS = {"policyholders": 170, "policies": 200, "historical_claims": 60, "historical_calls": 72}

SURGE = {
    "kind": "wind",
    "title": "Chinook windstorm, Calgary",
    "headline": "Gusts over 100 km/h overnight: roofs, fences and siding",
    "region": "CA-AB",
    "area": "Calgary and Airdrie",
    "alert_id": "eccc-ab-calgary-chinook-wind",
    "started": "06:00",  # local, demo day; the wind warning itself began the evening before
    "multiplier": 3.4,
    "usual_calls_per_hour": 4.0,
    "standby_available": 2,
    "wait_for_person_seconds": 60,
    "surge_questions": "wind",
}

# Live at the demo moment: 3 with the line, 2 waiting for a person. `answered` = minutes before demo now.
LIVE_LINES = (
    {
        "line": 1,
        "scenario": "calgary-windstorm",
        "caller": "Gord Lindqvist",
        "language": "en",
        "region": "CA-AB",
        "place": "Saddle Ridge, Calgary",
        "loss_type": "wind",
        "stage": "loss_details",
        "answered": 3.2,
        "heard": ["Roof shingles torn off", "Siding damaged", "Skylight smashed by debris"],
        "mood": "unsettled",
        "in_surge": True,
    },
    {
        "line": 2,
        "scenario": "denver-rear-end",
        "caller": "Kiara Booker",
        "language": "en",
        "region": "US-CO",
        "place": "Colfax Ave, Denver",
        "loss_type": "collision",
        "stage": "loss_details",
        "answered": 4.5,
        "heard": ["Rear-ended at a light", "Other driver stopped", "Sore neck"],
        "mood": "shaken",
        "in_surge": False,
    },
    {
        "line": 3,
        "scenario": "montreal-basement",
        "caller": "Martine Gagnon",
        "language": "fr",
        "region": "CA-QC",
        "place": "Rosemont, Montréal",
        "loss_type": "water",
        "stage": "photos",
        "answered": 6.1,
        "heard": ["Tuyau éclaté", "Sous-sol inondé", "Eau coupée"],
        "mood": "calm",
        "in_surge": False,
    },
    {
        "line": 4,
        "scenario": "airdrie-gas",
        "caller": "Hal Petrenko",
        "language": "en",
        "region": "CA-AB",
        "place": "Airdrie",
        "loss_type": "wind",
        "stage": "handoff",
        "answered": 2.4,
        "handoff": "urgent_safety",
        "detail": "Smells gas after the wind tore the cover off his gas meter.",
        "actions": ["Told him to leave the house and call 911", "He is outside and still on the line"],
        "mood": "upset",
        "in_surge": True,
    },
    {
        "line": 5,
        "scenario": "calgary-fence",
        "caller": "Wendy Arsenault",
        "language": "en",
        "region": "CA-AB",
        "place": "Bridgeland, Calgary",
        "loss_type": "wind",
        "stage": "handoff",
        "answered": 5.0,
        "handoff": "caller_asked",
        "detail": "Asked for a person about a fallen fence and a damaged neighbour's car.",
        "actions": ["Took her policy and the address", "Fence and car details are in the claim file"],
        "mood": "calm",
        "in_surge": True,
    },
)

# "Finished this morning" tickets (claim numbers as the design shows them), plus the SIU-flagged claim.
FINISHED_THIS_MORNING = (
    {
        "claim": "CV-26-01842",
        "place": "Calgary",
        "time": "02:14",
        "caller": "Dana Whitcombe",
        "loss_type": "wind",
        "route": "fast_track",
        "note": "Skylight smashed by blown debris; the landing page's recorded call",
    },
    {
        "claim": "CV-26-01851",
        "place": "Calgary",
        "time": "06:21",
        "caller": "Arjun Bains",
        "loss_type": "wind",
        "route": "adjuster",
    },
    {
        "claim": "CV-26-01853",
        "place": "Okotoks",
        "time": "06:38",
        "caller": "Leah Moreau",
        "loss_type": "wind",
        "route": "fast_track",
    },
    {
        "claim": "CV-26-01856",
        "place": "Denver",
        "time": "06:47",
        "caller": "Tomás Reyes",
        "loss_type": "collision",
        "route": "adjuster",
        "siu": True,
    },
    {
        "claim": "CV-26-01858",
        "place": "Laval",
        "time": "07:05",
        "caller": "Sophie Tremblay",
        "loss_type": "water",
        "route": "adjuster",
    },
)

SIU_FLAGGED = {
    "claim": "CV-26-01856",
    "caller": "Tomás Reyes",
    "summary": "Rear-ended at a light, Denver",
    "loss_at": "-1d 17:52",  # Wednesday 7 January, 5:52 p.m. Denver time; reported Thursday 6:47 a.m.
    "model_route": "special_investigation",
    "route_after_review": "adjuster",  # Lena Ortiz changed it: "Police report confirms the SUV."
    "referral": "open",  # the closer-look referral stays open for Dev Malhotra
    "signs": ["policy_started_19_days_before_loss", "coverage_raised_last_month", "third_party_caller_pressure"],
    "signs_checked": 14,
}
