"""The demo seed plan (docs/DATA.md "Seed plan"). Everything is dated relative to the demo clock's today."""

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


@dataclass(frozen=True, slots=True)
class Persona:
    role: str
    full_name: str
    email: str
    title: str
    language: str
    color: str


PERSONAS: tuple[Persona, ...] = (
    Persona("admin", "Priya Raman", "priya.raman@larkspur.example", "Claims operations lead", "en", "violet"),
    Persona(
        "supervisor", "Dana Whitford", "dana.whitford@larkspur.example", "Claims supervisor, Calgary", "en", "amber"
    ),
    Persona(
        "intake_agent", "Marc-André Gagnon", "marc-andre.gagnon@larkspur.example", "Intake agent (EN/FR)", "fr", "teal"
    ),
    Persona(
        "adjuster", "Tomás Reyes", "tomas.reyes@larkspur.example", "Property and auto adjuster, Denver", "en", "sky"
    ),
    Persona("siu_investigator", "Grace Okafor", "grace.okafor@larkspur.example", "Special investigator", "en", "rose"),
    Persona(
        "compliance",
        "Hélène Bouchard",
        "helene.bouchard@larkspur.example",
        "Compliance and quality; privacy officer",
        "fr",
        "lime",
    ),
)

COUNTS = {"policyholders": 170, "policies": 200, "historical_claims": 60, "historical_calls": 72}

# The three live demo lines (scripted callers; docs/DATA.md). `answered_minutes_ago` is relative to demo now.
LIVE_LINES = (
    {
        "scenario": "calgary-hail",
        "language": "en",
        "region": "CA-AB",
        "loss_type": "auto_hail",
        "caller": "Jordan Mercer",
        "stage": "loss_details",
        "answered_minutes_ago": 3,
        "in_surge": True,
    },
    {
        "scenario": "denver-rear-end",
        "language": "en",
        "region": "US-CO",
        "loss_type": "auto_collision",
        "caller": "Alicia Romero",
        "stage": "safety",
        "answered_minutes_ago": 5,
        "in_surge": False,
    },
    {
        "scenario": "montreal-basement",
        "language": "fr",
        "region": "CA-QC",
        "loss_type": "property_water",
        "caller": "Amélie Tremblay",
        "stage": "identity",
        "answered_minutes_ago": 1,
        "in_surge": False,
    },
)

SPECIAL = {
    "urgent_safety": {
        "scenario": "calgary-gas-smell",
        "region": "CA-AB",
        "loss_type": "property_hail_wind",
        "state": "waiting_for_person",
        "detail": "Caller smells gas after hail broke the furnace vent",
    },
    "siu_flagged_claim": {
        "region": "US-CO",
        "loss_type": "auto_theft",
        "days_ago": 6,
        "indicators": [
            "policy_started_19_days_before_loss",
            "reported_9_days_after_loss",
            "no_police_report",
            "coverage_raised_last_month",
        ],
    },
    "surge": {
        "kind": "hail",
        "region": "CA-AB",
        "area": "Calgary (northeast)",
        "alert_id": "eccc-ab-calgary-hail",
        "started_hours_ago": 3,
        "multiplier": 4.2,
    },
}
