"""`OrgPlaybook` for the dialogue engine: the active script per loss type, the consent rule per region, hand-off rules
and the active surge (docs/API_CONTRACT.md Part 3). Reads only; each call is one short query."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select

from claimvoice import contracts, reference
from claimvoice.calls.models import Surge
from claimvoice.platform import db
from claimvoice.platform.models import Organization
from claimvoice.settings import service
from claimvoice.settings.models import ConsentRuleRow, ScriptVersion


def _script(row: ScriptVersion) -> contracts.Script:
    questions = [
        contracts.ScriptQuestion(
            slot_key=q["slotKey"],
            kind=q.get("kind", "text"),
            prompt=dict(q.get("prompt") or {}),
            required=bool(q.get("required", True)),
            when=q.get("when"),
            choices=tuple(q.get("choices") or ()),
            label={"en": q.get("label", ""), "fr": q.get("labelFr") or q.get("label", "")},
            surge_only=bool(q.get("surgeOnly", False)),
        )
        for q in row.questions
    ]
    return contracts.Script(loss_type=row.loss_type, version=row.version, questions=questions)


class SqlPlaybook:
    async def script(self, org_id: str, loss_type: str) -> contracts.Script:
        async with db.sessionmaker()() as session:
            row = (
                await session.execute(
                    select(ScriptVersion)
                    .where(ScriptVersion.org_id == org_id, ScriptVersion.loss_type == loss_type)
                    .order_by(ScriptVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if row is None:
            defaults = service.default_scripts().get(loss_type) or {"questions": []}
            row = ScriptVersion(org_id=org_id, loss_type=loss_type, line="property", version=1, **defaults)
        return _script(row)

    async def consent_rule(self, org_id: str, region: str) -> contracts.ConsentRule:
        async with db.sessionmaker()() as session:
            row = (
                await session.execute(
                    select(ConsentRuleRow).where(ConsentRuleRow.org_id == org_id, ConsentRuleRow.region == region)
                )
            ).scalar_one_or_none()
        if row is not None:
            return contracts.ConsentRule(region=row.region, rule=row.rule, announcement=dict(row.announcement))
        # Unknown region: the strictest rule (nothing kept until the caller says yes).
        rule = reference.REGIONS.get(region, {}).get("consent", "all_party")
        return contracts.ConsentRule(region=region, rule=rule, announcement=dict(service.ANNOUNCEMENTS[rule]))

    async def handoff_rules(self, org_id: str) -> contracts.HandoffRules:
        async with db.sessionmaker()() as session:
            org = await session.get(Organization, org_id)
        rules = service.section(org, "handoffRules") if org else dict(service.DEFAULT_HANDOFF)
        langs = service.section(org, "languages") if org else dict(service.DEFAULT_LANGUAGES)
        return contracts.HandoffRules(
            low_confidence_turns=int(rules["lowConfidenceTurns"]),
            distress_threshold=float(rules["distressThreshold"]),
            identity_attempts=int(rules["identityAttempts"]),
            offer_person_on_consent_refusal=bool(rules["offerPersonOnConsentRefusal"]),
            max_wait_seconds=int(rules["maxWaitSeconds"]),
            french_first_regions=tuple(langs.get("frenchFirstRegions") or ("CA-QC",)),
            asked_times=int(rules["askedTimes"]),
            urgent_keywords=tuple(rules.get("urgentKeywords") or ()),
        )

    async def active_surge(self, org_id: str, region: str) -> Mapping[str, Any] | None:
        async with db.sessionmaker()() as session:
            row = (
                await session.execute(
                    select(Surge)
                    .where(Surge.org_id == org_id, Surge.region == region, Surge.ended_at.is_(None))
                    .order_by(Surge.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "kind": row.kind,
            "loss_type": row.loss_type,
            "title": row.title,
            "area_label": row.area_label,
            "region": row.region,
            "surge_questions_on": row.surge_questions_on,
            "alert_id": row.alert_id,
        }


_playbook: SqlPlaybook | None = None


def get_playbook() -> SqlPlaybook:
    global _playbook
    if _playbook is None:
        _playbook = SqlPlaybook()
    return _playbook
