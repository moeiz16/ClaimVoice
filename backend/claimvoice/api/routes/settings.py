"""§1.11 settings: scripts per loss type, consent rules per state or province, hand-off rules, languages, retention
and the privacy officer. Every change is audited and applies to calls answered after it."""

from __future__ import annotations

import io
import wave
from typing import Any

from litestar import Response, Router, get, put
from sqlalchemy import select

from claimvoice import clock, reference
from claimvoice.api import labels
from claimvoice.api.context import Ctx, not_found
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.models import User
from claimvoice.schemas.base import PersonRef
from claimvoice.schemas.settings import (
    Bilingual,
    ConsentRule,
    ConsentRuleIn,
    HandoffRules,
    Languages,
    Privacy,
    Retention,
    Script,
    ScriptIn,
    ScriptQuestion,
    SettingsOverview,
    VoiceSetting,
)
from claimvoice.settings import service
from claimvoice.settings.models import ConsentRuleRow, ScriptVersion

QUESTION_KINDS = {
    "text",
    "date",
    "time",
    "yes_no",
    "phone",
    "number",
    "choice",
    "address",
    "policy_number",
    "money_band",
}


def _invalid(field: str, message: str) -> ProblemError:
    return ProblemError(
        422,
        "validation_error",
        "Validation failed",
        "One or more fields are invalid.",
        errors=[{"field": field, "message": message}],
    )


async def _person(ctx: Ctx, user_id: str | None) -> PersonRef | None:
    if not user_id:
        return None
    user = await ctx.db.get(User, user_id)
    return PersonRef(id=user.id, name=user.full_name) if user else None


async def _script_out(ctx: Ctx, row: ScriptVersion) -> Script:
    return Script(
        loss_type=row.loss_type,
        loss_type_label=labels.loss_type(row.loss_type, ctx.lang) or row.loss_type,
        line=labels.lit(row.line),
        version=row.version,
        questions=[
            ScriptQuestion(
                slot_key=q["slotKey"],
                label=(q.get("labelFr") if ctx.lang == "fr" else None) or q.get("label") or q["slotKey"],
                kind=q.get("kind", "text"),
                prompt=Bilingual(en=q.get("prompt", {}).get("en", ""), fr=q.get("prompt", {}).get("fr", "")),
                required=bool(q.get("required", True)),
                when=q.get("when"),
                choices=list(q.get("choices") or []),
                surge_only=bool(q.get("surgeOnly", False)),
            )
            for q in row.questions
        ],
        updated_at=row.created_at,
        updated_by=await _person(ctx, row.updated_by),
    )


def _consent_out(ctx: Ctx, row: ConsentRuleRow) -> ConsentRule:
    region_label = labels.region(row.region, ctx.lang) or row.region
    return ConsentRule(
        region=row.region,
        region_label=region_label,
        rule=labels.lit(row.rule),
        rule_label=f"{labels.pick(labels.CONSENT_RULES[row.rule], ctx.lang)} ({region_label})",
        announcement=Bilingual(en=row.announcement.get("en", ""), fr=row.announcement.get("fr", "")),
        basis=row.basis,
        on_refusal=service.ON_REFUSAL if row.rule == "all_party" else service.ON_REFUSAL_ONE_PARTY,
        is_default=row.is_default,
    )


def _handoff_out(org: Any) -> HandoffRules:
    r = service.section(org, "handoffRules")
    return HandoffRules(
        urgent_keywords=list(r["urgentKeywords"]),
        asked_times=int(r["askedTimes"]),
        low_confidence_turns=int(r["lowConfidenceTurns"]),
        distress_threshold=float(r["distressThreshold"]),
        identity_attempts=int(r["identityAttempts"]),
        offer_person_on_consent_refusal=bool(r["offerPersonOnConsentRefusal"]),
        max_wait_seconds=int(r["maxWaitSeconds"]),
        urgent_safety_always=True,
    )


def _languages_out(org: Any) -> Languages:
    r = service.section(org, "languages")
    return Languages(
        enabled=list(r["enabled"]),
        voices={k: VoiceSetting(voice=v["voice"], speed=float(v["speed"])) for k, v in r["voices"].items()},
        default=r["default"],
        detect_automatically=bool(r["detectAutomatically"]),
        french_first_regions=list(r["frenchFirstRegions"]),
    )


def _retention_out(org: Any) -> Retention:
    from datetime import datetime

    r = service.section(org, "retention")
    last = r.get("lastPurgeAt")
    return Retention(
        recordings_years=int(r["recordingsYears"]),
        transcripts_years=int(r["transcriptsYears"]),
        photos_years=int(r["photosYears"]),
        claim_files_years=7,
        card_number_moments="always_removed",
        refused_consent_transcripts="not_kept",
        deletion_requests_waiting=int(r.get("deletionRequestsWaiting") or 0),
        last_purge_at=datetime.fromisoformat(last) if last else None,
        next_purge_on=service.next_purge_on(org),
    )


def _privacy_out(org: Any) -> Privacy:
    r = service.section(org, "privacy")
    return Privacy(
        privacy_officer_name=r["privacyOfficerName"],
        privacy_officer_email=r["privacyOfficerEmail"],
        privacy_notice_url=r.get("privacyNoticeUrl"),
    )


@get("/settings")
async def overview(ctx: Ctx) -> SettingsOverview:
    ctx.require("settings:read")
    rules = (await ctx.db.execute(select(ConsentRuleRow.id).where(ConsentRuleRow.org_id == ctx.org_id))).all()
    scripts = await service.latest_scripts(ctx.db, ctx.org_id)
    return SettingsOverview(
        languages=_languages_out(ctx.org),
        retention=_retention_out(ctx.org),
        handoff_rules=_handoff_out(ctx.org),
        privacy=_privacy_out(ctx.org),
        consent_rules=len(rules),
        scripts=len(scripts),
    )


_SCRIPT_ORDER = list(reference.LOSS_TYPES)


@get("/settings/scripts")
async def list_scripts(ctx: Ctx) -> list[Script]:
    ctx.require("settings:read")
    rows = await service.latest_scripts(ctx.db, ctx.org_id)
    ordered = sorted(
        rows.values(), key=lambda r: _SCRIPT_ORDER.index(r.loss_type) if r.loss_type in _SCRIPT_ORDER else 99
    )
    return [await _script_out(ctx, r) for r in ordered]


async def _latest(ctx: Ctx, loss_type: str) -> ScriptVersion:
    row = (await service.latest_scripts(ctx.db, ctx.org_id)).get(loss_type)
    if row is None:
        raise not_found()
    return row


@get("/settings/scripts/{loss_type:str}")
async def get_script(ctx: Ctx, loss_type: str) -> Script:
    ctx.require("settings:read")
    return await _script_out(ctx, await _latest(ctx, loss_type))


@put("/settings/scripts/{loss_type:str}")
async def put_script(ctx: Ctx, loss_type: str, data: ScriptIn) -> Script:
    ctx.require("settings:manage")
    current = await _latest(ctx, loss_type)
    if not data.note.strip():
        raise _invalid("note", "Say what changed and why.")
    if not data.questions:
        raise _invalid("questions", "A script needs at least one question.")
    from claimvoice.dialogue.slots import SLOT_CATALOG

    seen: set[str] = set()
    questions = []
    for i, q in enumerate(data.questions):
        if q.slot_key not in SLOT_CATALOG:
            raise _invalid(f"questions[{i}].slotKey", "This question doesn't fill a claim-file field.")
        if q.slot_key in seen:
            raise _invalid(f"questions[{i}].slotKey", "Each field is asked once.")
        if not q.prompt.en.strip() or not q.prompt.fr.strip():
            raise _invalid(f"questions[{i}].prompt", "Write the question in English and French.")
        if len(q.prompt.en) > 300 or len(q.prompt.fr) > 300:
            raise _invalid(f"questions[{i}].prompt", "Keep each question under 300 characters.")
        seen.add(q.slot_key)
        spec = SLOT_CATALOG[q.slot_key]
        questions.append(
            {
                "slotKey": q.slot_key,
                "label": spec.en,
                "labelFr": spec.fr,
                "kind": q.kind,
                "prompt": {"en": q.prompt.en.strip(), "fr": q.prompt.fr.strip()},
                "required": q.required,
                "when": q.when,
                "choices": list(q.choices),
                "surgeOnly": q.surge_only,
            }
        )
    row = ScriptVersion(
        org_id=ctx.org_id,
        loss_type=loss_type,
        line=current.line,
        version=current.version + 1,
        questions=questions,
        updated_by=ctx.user.id,
        note=data.note.strip()[:500],
    )
    ctx.db.add(row)
    await ctx.db.commit()
    label = labels.loss_type(loss_type, "en")
    await ctx.audit(
        "settings.script_changed",
        f"{ctx.user.full_name} saved version {row.version} of the {label} script.",
        target_type="script",
        target_id=loss_type,
        target_label=f"{label} script",
        details={"version": row.version, "note": row.note},
    )
    return await _script_out(ctx, row)


@get("/settings/scripts/{loss_type:str}/preview")
async def preview_script(ctx: Ctx, loss_type: str, language: str = "en", index: int = 0) -> Response[bytes]:
    """ "▸ Hear it": the question in the line's voice (a quiet tone with the right length offline)."""
    ctx.require("settings:read")
    row = await _latest(ctx, loss_type)
    if not 0 <= index < len(row.questions):
        raise not_found()
    text = row.questions[index].get("prompt", {}).get("fr" if language == "fr" else "en", "")
    from claimvoice.voice.adapters import FakeTextToSpeech

    tts = FakeTextToSpeech()
    pcm = b"".join([chunk async for chunk in tts.synthesize(text, language="fr" if language == "fr" else "en")])
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tts.sample_rate)
        w.writeframes(pcm)
    return Response(buf.getvalue(), media_type="audio/wav")


@get("/settings/consent-rules")
async def list_consent_rules(ctx: Ctx) -> list[ConsentRule]:
    ctx.require("settings:read")
    rows = (await ctx.db.execute(select(ConsentRuleRow).where(ConsentRuleRow.org_id == ctx.org_id))).scalars().all()
    order = list(reference.REGIONS)
    rows = sorted(rows, key=lambda r: order.index(r.region) if r.region in order else 99)
    return [_consent_out(ctx, r) for r in rows]


@put("/settings/consent-rules/{region:str}")
async def put_consent_rule(ctx: Ctx, region: str, data: ConsentRuleIn) -> ConsentRule:
    ctx.require("settings:manage")
    row = (
        await ctx.db.execute(
            select(ConsentRuleRow).where(ConsentRuleRow.org_id == ctx.org_id, ConsentRuleRow.region == region)
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    shipped = reference.REGIONS.get(region, {}).get("consent", "all_party")
    if shipped == "all_party" and data.rule != "all_party":
        raise _invalid("rule", "This region's law needs every party's consent. It can't be weakened.")
    if not data.announcement.en.strip() or not data.announcement.fr.strip():
        raise _invalid("announcement", "Write the announcement in English and French.")
    before = row.rule
    row.rule = data.rule
    row.announcement = {"en": data.announcement.en.strip(), "fr": data.announcement.fr.strip()}
    row.is_default = False
    row.updated_by = ctx.user.id
    row.updated_at = clock.now()
    await ctx.db.commit()
    await ctx.audit(
        "settings.consent_rule_changed",
        f"{ctx.user.full_name} changed the recording announcement for {labels.region(region, 'en')}.",
        target_type="consent_rule",
        target_id=region,
        target_label=labels.region(region, "en"),
        details={"from": before, "to": row.rule},
    )
    return _consent_out(ctx, row)


@get("/settings/handoff-rules")
async def get_handoff(ctx: Ctx) -> HandoffRules:
    ctx.require("settings:read")
    return _handoff_out(ctx.org)


@put("/settings/handoff-rules")
async def put_handoff(ctx: Ctx, data: HandoffRules) -> HandoffRules:
    ctx.require("settings:manage")
    if not 1 <= data.low_confidence_turns <= 5:
        raise _invalid("lowConfidenceTurns", "Choose between 1 and 5.")
    if not 0.5 <= data.distress_threshold <= 0.95:
        raise _invalid("distressThreshold", "Choose between 0.5 and 0.95.")
    if not 1 <= data.identity_attempts <= 5:
        raise _invalid("identityAttempts", "Choose between 1 and 5.")
    if not 1 <= data.asked_times <= 3:
        raise _invalid("askedTimes", "Choose between 1 and 3.")
    if not 15 <= data.max_wait_seconds <= 600:
        raise _invalid("maxWaitSeconds", "Choose between 15 seconds and 10 minutes.")
    keywords = [k.strip() for k in data.urgent_keywords if k.strip()][:40]
    service.put_section(
        ctx.org,
        "handoffRules",
        {
            "urgentKeywords": keywords,
            "askedTimes": data.asked_times,
            "lowConfidenceTurns": data.low_confidence_turns,
            "distressThreshold": data.distress_threshold,
            "identityAttempts": data.identity_attempts,
            "offerPersonOnConsentRefusal": data.offer_person_on_consent_refusal,
            "maxWaitSeconds": data.max_wait_seconds,
            "urgentSafetyAlways": True,
        },
    )
    await ctx.db.commit()
    await ctx.audit(
        "settings.handoff_rules_changed",
        f"{ctx.user.full_name} changed the hand-off rules.",
        target_type="settings",
        target_id="handoff-rules",
        target_label="Hand-off rules",
    )
    return _handoff_out(ctx.org)


@get("/settings/languages")
async def get_languages(ctx: Ctx) -> Languages:
    ctx.require("settings:read")
    return _languages_out(ctx.org)


@put("/settings/languages")
async def put_languages(ctx: Ctx, data: Languages) -> Languages:
    ctx.require("settings:manage")
    if not data.enabled:
        raise _invalid("enabled", "Keep at least one language.")
    if data.default not in data.enabled:
        raise _invalid("default", "The default language must be switched on.")
    if "CA-QC" in (ctx.org.regions or []) and "fr" not in data.enabled:
        raise _invalid("enabled", "French must stay on while you serve Québec.")
    for lang, v in data.voices.items():
        if not 0.8 <= v.speed <= 1.2:
            raise _invalid(f"voices.{lang}.speed", "Choose a speed between 0.8 and 1.2.")
    service.put_section(
        ctx.org,
        "languages",
        {
            "enabled": list(dict.fromkeys(data.enabled)),
            "default": data.default,
            "voices": {k: {"voice": v.voice[:80], "speed": v.speed} for k, v in data.voices.items()},
            "detectAutomatically": data.detect_automatically,
            "frenchFirstRegions": list(dict.fromkeys(data.french_first_regions)),
        },
    )
    await ctx.db.commit()
    await ctx.audit(
        "settings.languages_changed",
        f"{ctx.user.full_name} changed the line's languages.",
        target_type="settings",
        target_id="languages",
        target_label="Languages",
    )
    return _languages_out(ctx.org)


@get("/settings/retention")
async def get_retention(ctx: Ctx) -> Retention:
    ctx.require("settings:read")
    return _retention_out(ctx.org)


@put("/settings/retention")
async def put_retention(ctx: Ctx, data: Retention) -> Retention:
    ctx.require("settings:manage")
    for name, value in (
        ("recordingsYears", data.recordings_years),
        ("transcriptsYears", data.transcripts_years),
        ("photosYears", data.photos_years),
    ):
        if not 1 <= value <= 10:
            raise _invalid(name, "Choose between 1 and 10 years.")
    current = service.section(ctx.org, "retention")
    current.update(
        recordingsYears=data.recordings_years,
        transcriptsYears=data.transcripts_years,
        photosYears=data.photos_years,
    )
    service.put_section(ctx.org, "retention", current)
    await ctx.db.commit()
    await ctx.audit(
        "settings.retention_changed",
        f"{ctx.user.full_name} set retention to {data.recordings_years} years for recordings, "
        f"{data.transcripts_years} for transcripts and {data.photos_years} for photos.",
        target_type="settings",
        target_id="retention",
        target_label="Retention",
    )
    return _retention_out(ctx.org)


@get("/settings/privacy")
async def get_privacy(ctx: Ctx) -> Privacy:
    ctx.require("settings:read")
    return _privacy_out(ctx.org)


@put("/settings/privacy")
async def put_privacy(ctx: Ctx, data: Privacy) -> Privacy:
    ctx.require("settings:manage")
    if not data.privacy_officer_name.strip():
        raise _invalid("privacyOfficerName", "Name the privacy officer.")
    if "@" not in data.privacy_officer_email:
        raise _invalid("privacyOfficerEmail", "Enter a valid email address.")
    if data.privacy_notice_url and not data.privacy_notice_url.startswith(("https://", "http://")):
        raise _invalid("privacyNoticeUrl", "Use a full web address.")
    service.put_section(
        ctx.org,
        "privacy",
        {
            "privacyOfficerName": data.privacy_officer_name.strip()[:160],
            "privacyOfficerEmail": data.privacy_officer_email.strip()[:254],
            "privacyNoticeUrl": data.privacy_notice_url,
        },
    )
    await ctx.db.commit()
    await ctx.audit(
        "settings.privacy_changed",
        f"{ctx.user.full_name} named {data.privacy_officer_name.strip()} as privacy officer.",
        target_type="settings",
        target_id="privacy",
        target_label="Privacy officer",
    )
    return _privacy_out(ctx.org)


ROUTER = Router(
    path="/api/v1",
    route_handlers=[
        overview,
        list_scripts,
        get_script,
        put_script,
        preview_script,
        list_consent_rules,
        put_consent_rule,
        get_handoff,
        put_handoff,
        get_languages,
        put_languages,
        get_retention,
        put_retention,
        get_privacy,
        put_privacy,
    ],
)
