"""Larkspur Mutual's book of business: the demo policy book (the scripted callers' policies, seeded exactly) plus a
deterministic synthetic book to about 200 policies and 170 policyholders. Synthetic people only."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from claimvoice.policies.models import Coverage, InsuredItem, Policy, Policyholder
from claimvoice.seed.plan import BOOK

DEMO_BOOK = Path(__file__).resolve().parents[1] / "dialogue" / "data" / "demo_policies.json"
DEMO_DAY = date(2026, 1, 8)  # the demo book's dates are written for this day and shift with the demo clock

PRODUCT_CODES = {
    "Auto Plus": "auto_plus",
    "Home Comprehensive": "home_comprehensive",
    "Home Standard": "home_standard",
    "Condo": "condo",
}

FIRST_EN = [
    "Avery",
    "Blake",
    "Cora",
    "Darren",
    "Elena",
    "Farid",
    "Gemma",
    "Hector",
    "Ingrid",
    "Jonah",
    "Keira",
    "Liam",
    "Maya",
    "Nolan",
    "Olivia",
    "Parker",
    "Quinn",
    "Rosa",
    "Silas",
    "Tara",
    "Umar",
    "Vera",
    "Wes",
    "Yasmin",
    "Zane",
    "Brooke",
    "Caleb",
    "Dina",
    "Ethan",
    "Fiona",
    "Grant",
    "Holly",
    "Isaac",
    "Jade",
    "Kurt",
    "Lucy",
    "Mateo",
    "Nina",
    "Owen",
    "Paige",
    "Reid",
    "Sana",
    "Trent",
    "Una",
    "Victor",
    "Willa",
]
LAST_EN = [
    "Anderson",
    "Bergstrom",
    "Chow",
    "Dubois",
    "Eriksen",
    "Fitzgerald",
    "Gill",
    "Hartley",
    "Ivanova",
    "Jensen",
    "Kaur",
    "Larsen",
    "MacDonald",
    "Nakamura",
    "Olsen",
    "Petrov",
    "Quill",
    "Rasmussen",
    "Sandhu",
    "Thorson",
    "Underwood",
    "Vasquez",
    "Whitfield",
    "Yellowhorn",
    "Zimmer",
    "Abbott",
    "Brennan",
    "Castillo",
    "Delgado",
    "Ellis",
    "Fraser",
    "Grewal",
    "Hughes",
    "Iqbal",
    "Janssen",
    "Kowalczyk",
    "Lindgren",
    "Morales",
    "Novak",
    "Ortega",
    "Pearson",
    "Ramirez",
    "Schultz",
    "Tran",
    "Wong",
]
FIRST_FR = [
    "Amélie",
    "Benoît",
    "Camille",
    "Denis",
    "Élise",
    "François",
    "Geneviève",
    "Hugo",
    "Isabelle",
    "Julien",
    "Karine",
    "Luc",
    "Manon",
    "Nicolas",
    "Odile",
    "Philippe",
    "Rémi",
    "Sylvie",
    "Thierry",
    "Valérie",
    "Yannick",
    "Chantal",
    "Mathieu",
    "Josée",
]
LAST_FR = [
    "Arsenault",
    "Bouchard",
    "Côté",
    "Desjardins",
    "Émond",
    "Fortier",
    "Gauthier",
    "Hébert",
    "Ouellet",
    "Lapointe",
    "Morin",
    "Nadeau",
    "Paquette",
    "Rousseau",
    "Simard",
    "Thibault",
    "Vachon",
    "Gagné",
    "Bélanger",
    "Leclerc",
]

PLACES: dict[str, list[tuple[str, str, str, str]]] = {
    # (city, postal prefix, phone prefix, neighbourhood/street pool key)
    "CA-AB": [
        ("Calgary", "T3J", "+1403555", "NE"),
        ("Calgary", "T2E", "+1403555", "NE"),
        ("Calgary", "T3H", "+1403555", "SW"),
        ("Calgary", "T2Z", "+1403555", "SE"),
        ("Airdrie", "T4B", "+1587555", ""),
        ("Okotoks", "T1S", "+1403555", ""),
    ],
    "US-CO": [
        ("Denver", "80206", "+1720555", ""),
        ("Denver", "80211", "+1303555", ""),
        ("Aurora", "80012", "+1720555", ""),
        ("Lakewood", "80226", "+1303555", ""),
    ],
    "CA-QC": [
        ("Montréal", "H2G", "+1514555", ""),
        ("Montréal", "H1V", "+1514555", ""),
        ("Laval", "H7N", "+1450555", ""),
    ],
}
STREETS = {
    "CA-AB": [
        "Saddlecrest Blvd",
        "Taradale Dr",
        "Cityscape Dr",
        "Copperfield Way",
        "Mahogany Blvd",
        "Evanston Dr",
        "Bridlewood Ave",
        "Kingsbury Cres",
        "Sheep River Dr",
        "Coopers Blvd",
    ],
    "US-CO": ["E Colfax Ave", "Josephine St", "Tennyson St", "E 17th Ave", "S Pearl St", "W 32nd Ave"],
    "CA-QC": [
        "rue Saint-Denis",
        "boulevard Rosemont",
        "rue Beaubien",
        "boulevard des Laurentides",
        "rue Masson",
        "avenue Papineau",
    ],
}
VEHICLES = [
    ("Toyota", "RAV4"),
    ("Honda", "Civic"),
    ("Ford", "F-150"),
    ("Subaru", "Outback"),
    ("Hyundai", "Tucson"),
    ("Mazda", "CX-5"),
    ("Chevrolet", "Silverado"),
    ("Kia", "Sorento"),
    ("Volkswagen", "Jetta"),
    ("Nissan", "Rogue"),
    ("Tesla", "Model 3"),
    ("Jeep", "Grand Cherokee"),
]


@dataclass
class Book:
    holders: list[Policyholder]
    policies: list[Policy]
    by_number: dict[str, Policy]
    demo: dict[str, dict[str, Any]]  # policy number -> demo book record


def demo_records() -> list[dict[str, Any]]:
    return list(json.loads(DEMO_BOOK.read_text(encoding="utf-8"))["policies"])


def _coverages(product: str, rng: random.Random, currency: str) -> list[tuple[str, bool, Any, Any]]:
    if product == "auto_plus":
        ded = rng.choice([250, 500, 500, 1000])
        return [
            ("liability", True, 1_000_000 if currency == "USD" else 2_000_000, 0),
            ("collision", True, None, ded),
            ("comprehensive", True, None, rng.choice([250, 300, 500])),
            ("rental", rng.random() < 0.7, 1500, 0),
        ]
    ded = rng.choice([500, 1000, 1000, 2500])
    dwelling = rng.choice([420_000, 510_000, 640_000, 780_000]) if product != "condo" else 80_000
    out: list[tuple[str, bool, Any, Any]] = [
        ("dwelling", True, dwelling, ded),
        ("contents", True, rng.choice([90_000, 150_000, 220_000]), ded),
        ("wind_hail", True, None, ded),
        ("water_escape", True, None, ded),
    ]
    if product == "home_comprehensive":
        out += [
            ("sewer_backup", rng.random() < 0.75, 25_000, ded),
            ("overland_water", rng.random() < 0.4, 50_000, ded),
            ("fence", True, 5000, ded),
            ("additional_living_expenses", True, 40_000, 0),
        ]
    elif product == "home_standard":
        out += [("sewer_backup", False, None, ded), ("fence", True, 2500, ded)]
    return out


def build(org_id: str, today: date) -> Book:
    """All rows for the book (not yet added to a session). Deterministic for a given demo day."""
    rng = random.Random(20260108)  # noqa: S311  (deterministic demo data, not security)
    shift = today - DEMO_DAY
    holders: list[Policyholder] = []
    policies: list[Policy] = []
    by_number: dict[str, Policy] = {}
    demo: dict[str, dict[str, Any]] = {}
    counts: dict[tuple[str, str], int] = {}

    def add_policy(
        holder: Policyholder,
        number: str,
        line: str,
        product: str,
        region: str,
        status: str,
        start: date,
        changed: date | None,
        coverages: list[tuple[str, bool, float | None, float | None]],
        item_label: str,
        item_details: dict[str, Any],
        premium: float,
    ) -> Policy:
        currency = "USD" if region.startswith("US-") else "CAD"
        term_start = start
        while term_start + timedelta(days=365) <= today:
            term_start += timedelta(days=365)
        p = Policy(
            org_id=org_id,
            policy_number=number,
            holder_id=holder.id,
            line=line,
            product=product,
            region=region,
            status=status,
            effective_from=start,
            effective_to=term_start + timedelta(days=365),
            premium=premium,
            currency=currency,
            coverage_changed_at=changed,
            is_sample=True,
        )
        from claimvoice.platform.db import new_id

        p.id = new_id()
        p.coverages = [
            Coverage(org_id=org_id, policy_id=p.id, position=i, key=k, included=inc, limit=lim, deductible=ded)
            for i, (k, inc, lim, ded) in enumerate(coverages)
        ]
        p.items = [
            InsuredItem(
                org_id=org_id,
                policy_id=p.id,
                kind="vehicle" if line == "auto" else "property",
                label=item_label,
                details=item_details,
            )
        ]
        policies.append(p)
        by_number[number] = p
        counts[(region, line)] = counts.get((region, line), 0) + 1
        return p

    from claimvoice.platform.db import new_id

    for rec in demo_records():
        region = rec["region"]
        city = rec.get("place", "").split(",")[-1].strip() or "Calgary"
        h = Policyholder(
            id=new_id(),
            org_id=org_id,
            full_name=rec["holderName"],
            phone_e164=rec["phone"],
            email=_email(rec["holderName"], rng),
            date_of_birth=date.fromisoformat(rec["dateOfBirth"]),
            postal_code=rec["postalCode"],
            city=city,
            region=region,
            preferred_language=rec["preferredLanguage"],
            customer_since=date.fromisoformat(rec["effectiveFrom"]) + shift,
            is_sample=True,
        )
        holders.append(h)
        changed = date.fromisoformat(rec["coverageChangedAt"]) + shift if rec.get("coverageChangedAt") else None
        currency = "USD" if region.startswith("US-") else "CAD"
        covs = [(c["key"], bool(c["included"]), c.get("limit"), c.get("deductible")) for c in rec["coverages"]]
        item = rec.get("insuredItem") or ("Vehicle" if rec["line"] == "auto" else "Home")
        details: dict[str, Any] = {"place": rec.get("place")}
        if rec["line"] == "auto" and item[:4].isdigit():
            details |= {"year": int(item[:4]), "makeModel": item[5:]}
        add_policy(
            h,
            rec["policyNumber"],
            rec["line"],
            PRODUCT_CODES.get(rec["product"], "auto_plus"),
            region,
            rec.get("status", "active"),
            date.fromisoformat(rec["effectiveFrom"]) + shift,
            changed,
            covs,
            item,
            details,
            round(rng.uniform(900, 2400) if currency == "CAD" else rng.uniform(700, 2000), 2),
        )
        demo[rec["policyNumber"]] = rec

    used_numbers = set(by_number)
    used_names = {h.full_name for h in holders}
    for (region, line), target in BOOK.items():
        while counts.get((region, line), 0) < target:
            french = region == "CA-QC"
            for _ in range(50):
                name = f"{rng.choice(FIRST_FR if french else FIRST_EN)} {rng.choice(LAST_FR if french else LAST_EN)}"
                if name not in used_names:
                    break
            used_names.add(name)
            city, postal, phone, _area = rng.choice(PLACES[region])
            postal_code = (
                postal
                if region == "US-CO"
                else f"{postal} {rng.randint(0, 9)}{chr(65 + rng.randint(0, 25))}{rng.randint(0, 9)}"
            )
            dob = date(rng.randint(1948, 2002), rng.randint(1, 12), rng.randint(1, 28))
            since = today - timedelta(days=rng.randint(200, 365 * 18))
            h = Policyholder(
                id=new_id(),
                org_id=org_id,
                full_name=name,
                phone_e164=f"{phone}{rng.randint(1000, 9999)}",
                email=_email(name, rng),
                date_of_birth=dob,
                postal_code=postal_code,
                city=city,
                region=region,
                preferred_language="fr" if french else "en",
                customer_since=since,
                is_sample=True,
            )
            holders.append(h)
            lines = [line]
            other = "property" if line == "auto" else "auto"
            if rng.random() < 0.22 and counts.get((region, other), 0) < BOOK[(region, other)]:
                lines.append(other)
            for ln in lines:
                prefix = region.split("-")[1]
                while True:
                    number = f"LM-{prefix}-{rng.randint(100000, 299999)}"
                    if number not in used_numbers:
                        break
                used_numbers.add(number)
                start = since + timedelta(days=rng.randint(0, 120))
                if start > today - timedelta(days=60):
                    start = today - timedelta(days=rng.randint(60, 400))
                status = "active" if rng.random() > 0.04 else rng.choice(["lapsed", "cancelled"])
                changed = today - timedelta(days=rng.randint(60, 700)) if rng.random() < 0.18 else None
                if ln == "auto":
                    make, model = rng.choice(VEHICLES)
                    year = rng.randint(2011, 2025)
                    label, details = (
                        f"{year} {make} {model}",
                        {"year": year, "makeModel": f"{make} {model}", "plateLast3": f"{rng.randint(100, 999)}"},
                    )
                    product = "auto_plus"
                else:
                    product = rng.choice(["home_comprehensive", "home_comprehensive", "home_standard", "condo"])
                    street = rng.choice(STREETS[region])
                    kind = "Condo" if product == "condo" else "House"
                    label = f"{kind}, {rng.randint(10, 299)} {street}"
                    details = {"type": kind.lower(), "yearBuilt": rng.randint(1958, 2021), "place": city}
                currency = "USD" if region.startswith("US-") else "CAD"
                add_policy(
                    h,
                    number,
                    ln,
                    product,
                    region,
                    status,
                    start,
                    changed,
                    _coverages(product, rng, currency),
                    label,
                    details,
                    round(rng.uniform(800, 2600), 2),
                )
    return Book(holders, policies, by_number, demo)


def _email(name: str, rng: random.Random) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    user = plain.replace(" ", ".").replace("'", "")
    return f"{user}{rng.randint(1, 99)}@mail.example"
