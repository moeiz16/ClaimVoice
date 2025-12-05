"""Organisation settings: shipped defaults, reads and validated writes (docs/API_CONTRACT.md §1.11).

Hand-off rules, languages, retention and the privacy officer live in `organizations.settings` (camelCase keys, the
wire shape). Scripts are versioned rows; consent rules are one row per region."""

from __future__ import annotations

import copy
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock, reference
from claimvoice.platform.models import Organization
from claimvoice.settings.models import ConsentRuleRow, ScriptVersion

DEFAULT_HANDOFF: dict[str, Any] = {
    "urgentKeywords": [
        "gas",
        "smoke",
        "fire",
        "someone hurt",
        "trapped",
        "power line",
        "gaz",
        "fumée",
        "feu",
        "blessé",
    ],
    "askedTimes": 1,
    "lowConfidenceTurns": 2,
    "distressThreshold": 0.7,
    "identityAttempts": 3,
    "offerPersonOnConsentRefusal": True,
    "maxWaitSeconds": 90,
    "urgentSafetyAlways": True,
}
DEFAULT_LANGUAGES: dict[str, Any] = {
    "enabled": ["en", "fr"],
    "default": "en",
    "voices": {
        "en": {"voice": "Line voice, English (Canada)", "speed": 1.0},
        "fr": {"voice": "Line voice, French (Canada)", "speed": 1.0},
    },
    "detectAutomatically": True,
    "frenchFirstRegions": ["CA-QC"],
}
DEFAULT_RETENTION: dict[str, Any] = {
    "recordingsYears": 7,
    "transcriptsYears": 7,
    "photosYears": 7,
    "claimFilesYears": 7,
    "deletionRequestsWaiting": 0,
    "lastPurgeAt": None,
}
DEFAULT_PRIVACY: dict[str, Any] = {"privacyOfficerName": "", "privacyOfficerEmail": "", "privacyNoticeUrl": None}

ANNOUNCEMENTS: dict[str, dict[str, str]] = {
    "all_party": {
        "en": "This call is recorded to help with your claim. Is that okay with you?",
        "fr": "Cet appel est enregistré pour traiter votre réclamation. Êtes-vous d'accord?",
    },
    "one_party": {
        "en": "This call is recorded to help with your claim.",
        "fr": "Cet appel est enregistré pour traiter votre réclamation.",
    },
}
ON_REFUSAL = "Recording stops; notes only; a person is offered"
ON_REFUSAL_ONE_PARTY = "The line still offers a person and keeps notes only if the caller objects"

SECTIONS = ("handoffRules", "languages", "retention", "privacy")
_DEFAULTS = {
    "handoffRules": DEFAULT_HANDOFF,
    "languages": DEFAULT_LANGUAGES,
    "retention": DEFAULT_RETENTION,
    "privacy": DEFAULT_PRIVACY,
}


def section(org: Organization, name: str) -> dict[str, Any]:
    """A settings section with defaults filled in."""
    merged = copy.deepcopy(_DEFAULTS[name])
    merged.update((org.settings or {}).get(name) or {})
    return merged


def put_section(org: Organization, name: str, value: dict[str, Any]) -> None:
    settings = dict(org.settings or {})
    settings[name] = value
    org.settings = settings  # reassign so SQLAlchemy sees the JSON change


def next_purge_on(org: Organization) -> Any:
    return clock.today(org.timezone) + timedelta(days=1)


# ---------------------------------------------------------------- scripts


def _fallback_scripts() -> dict[str, dict[str, Any]]:
    """Used only when the bilingual script files are not available (a stripped-down checkout)."""
    from claimvoice.dialogue.slots import SLOT_CATALOG

    keys = {
        "collision": [
            "loss_date",
            "loss_time",
            "loss_place",
            "vehicle_drivable",
            "other_party_involved",
            "police_report_filed",
            "damage_areas",
        ],
        "hail": ["loss_date", "roof_or_window_damage", "open_to_weather", "home_livable"],
        "wind": [
            "loss_date",
            "loss_time",
            "roof_or_window_damage",
            "siding_or_fence_damage",
            "debris_source",
            "open_to_weather",
            "home_livable",
        ],
        "water": [
            "loss_date",
            "water_source",
            "water_still_entering",
            "rooms_affected",
            "mitigation_taken",
            "home_livable",
        ],
        "fire": ["loss_date", "fire_out", "fire_department_attended", "home_livable"],
        "theft": ["loss_date", "loss_place", "items_stolen", "forced_entry", "police_report_filed"],
    }
    out: dict[str, dict[str, Any]] = {}
    for loss, slot_keys in keys.items():
        questions = []
        for k in slot_keys:
            spec = SLOT_CATALOG[k]
            questions.append(
                {
                    "slotKey": k,
                    "label": spec.en,
                    "labelFr": spec.fr,
                    "kind": spec.kind if spec.kind != "address" else "address",
                    "prompt": {"en": f"{spec.en}?", "fr": f"{spec.fr}?"},
                    "required": True,
                    "when": None,
                    "choices": list(spec.choices),
                    "surgeOnly": False,
                }
            )
        out[loss] = {"line": "auto" if loss == "collision" else "property", "questions": questions}
    return out


def default_scripts() -> dict[str, dict[str, Any]]:
    """{loss_type: {line, questions: [wire ScriptQuestion dicts]}} from the shipped bilingual scripts."""
    try:
        from claimvoice.dialogue.scripts import load_default_scripts
    except ImportError:
        return _fallback_scripts()
    loaded = load_default_scripts()
    out: dict[str, dict[str, Any]] = {}
    for loss, script in loaded.items():
        line = getattr(script, "line", None) or ("auto" if loss == "collision" else "property")
        questions = []
        for q in script.questions:
            label = dict(getattr(q, "label", {}) or {})
            questions.append(
                {
                    "slotKey": q.slot_key,
                    "label": label.get("en") or q.slot_key,
                    "labelFr": label.get("fr") or label.get("en") or q.slot_key,
                    "kind": q.kind,
                    "prompt": {"en": q.prompt.get("en", ""), "fr": q.prompt.get("fr", "")},
                    "required": bool(q.required),
                    "when": q.when,
                    "choices": list(q.choices),
                    "surgeOnly": bool(getattr(q, "surge_only", False)),
                }
            )
        out[loss] = {"line": line, "questions": questions}
    return out or _fallback_scripts()


async def latest_scripts(db: AsyncSession, org_id: str) -> dict[str, ScriptVersion]:
    sub = (
        select(ScriptVersion.loss_type, func.max(ScriptVersion.version).label("v"))
        .where(ScriptVersion.org_id == org_id)
        .group_by(ScriptVersion.loss_type)
        .subquery()
    )
    rows = (
        (
            await db.execute(
                select(ScriptVersion)
                .join(sub, (ScriptVersion.loss_type == sub.c.loss_type) & (ScriptVersion.version == sub.c.v))
                .where(ScriptVersion.org_id == org_id)
            )
        )
        .scalars()
        .all()
    )
    return {r.loss_type: r for r in rows}


# ---------------------------------------------------------------- consent rules


def default_consent_rules() -> list[dict[str, Any]]:
    return [
        {
            "region": code,
            "rule": info["consent"],
            "announcement": dict(ANNOUNCEMENTS[info["consent"]]),
            "basis": info["basis"],
        }
        for code, info in reference.REGIONS.items()
    ]


async def install_defaults(db: AsyncSession, org: Organization, *, user_id: str | None = None) -> None:
    """Shipped scripts, consent rules and settings for a new organisation (idempotent)."""
    have_scripts = set((await latest_scripts(db, org.id)).keys())
    for loss, script in default_scripts().items():
        if loss in have_scripts:
            continue
        db.add(
            ScriptVersion(
                org_id=org.id,
                loss_type=loss,
                line=script["line"],
                version=1,
                questions=script["questions"],
                updated_by=user_id,
                note="Shipped script",
            )
        )
    have_rules = set(
        (await db.execute(select(ConsentRuleRow.region).where(ConsentRuleRow.org_id == org.id))).scalars().all()
    )
    for rule in default_consent_rules():
        if rule["region"] in have_rules:
            continue
        db.add(ConsentRuleRow(org_id=org.id, is_default=True, **rule))
    settings = dict(org.settings or {})
    for name in SECTIONS:
        settings.setdefault(name, copy.deepcopy(_DEFAULTS[name]))
    org.settings = settings
    await db.flush()
