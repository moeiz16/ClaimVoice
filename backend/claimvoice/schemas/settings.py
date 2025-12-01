"""§1.11 settings: scripts per loss type, consent rules per state/province, hand-off rules, languages, retention."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from claimvoice.schemas.base import Lang, Model, PersonRef


class Bilingual(Model):
    en: str
    fr: str


class ScriptQuestion(Model):
    slot_key: str
    label: str  # claim-file label
    kind: Literal[
        "text", "date", "time", "yes_no", "phone", "number", "choice", "address", "policy_number", "money_band"
    ]
    prompt: Bilingual
    required: bool
    when: str | None  # "other_party_involved == true"
    choices: list[str]


class Script(Model):
    loss_type: str
    loss_type_label: str
    line: Literal["auto", "property"]
    version: int
    questions: list[ScriptQuestion]
    updated_at: datetime
    updated_by: PersonRef | None


class ScriptIn(Model):
    questions: list[ScriptQuestion]
    note: str  # change note for the audit trail


class ConsentRule(Model):
    region: str  # ISO 3166-2
    region_label: str
    rule: Literal["one_party", "all_party"]
    rule_label: str
    announcement: Bilingual
    basis: str  # plain citation, e.g. "California Penal Code §632 (all-party consent)"
    is_default: bool  # shipped default vs changed by this org


class ConsentRuleIn(Model):
    rule: Literal["one_party", "all_party"]
    announcement: Bilingual


class HandoffRules(Model):
    low_confidence_turns: int  # 1-5
    distress_threshold: float  # 0.5-0.95
    identity_attempts: int  # 1-5
    offer_person_on_consent_refusal: bool
    max_wait_seconds: int  # then offer a call-back
    urgent_safety_always: bool  # read-only true: urgent safety always reaches a person


class Languages(Model):
    enabled: list[Lang]
    default: Lang
    detect_automatically: bool
    french_first_regions: list[str]  # Quebec: French first (Law 25 / Charter of the French language)


class Retention(Model):
    recordings_days: int  # 30-730
    transcripts_days: int
    photos_days: int
    claim_files_years: int  # read-only 7 (claims records)
    refused_consent_transcripts: Literal["not_kept"]  # read-only
    last_purge_at: datetime | None
    next_purge_on: date | None


class Privacy(Model):
    privacy_officer_name: str  # Quebec Law 25 / PIPEDA accountability
    privacy_officer_email: str
    privacy_notice_url: str | None


class SettingsOverview(Model):
    languages: Languages
    retention: Retention
    handoff_rules: HandoffRules
    privacy: Privacy
    consent_rules: int
    scripts: int
