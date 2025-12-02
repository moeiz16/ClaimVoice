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
    surge_only: bool  # asked only while a surge's questions are switched on


class Script(Model):
    loss_type: str
    loss_type_label: str
    line: Literal["auto", "property"]
    version: int
    questions: list[ScriptQuestion]
    updated_at: datetime
    updated_by: PersonRef | None


class SurgeScript(Model):
    loss_type: str  # the loss type whose extra questions switch on in a surge ("wind")
    on: bool


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
    on_refusal: str  # "Recording stops; notes only; a person is offered"
    is_default: bool  # shipped default vs changed by this org


class ConsentRuleIn(Model):
    rule: Literal["one_party", "all_party"]
    announcement: Bilingual


class HandoffRules(Model):
    """Shown as sentences with editable blanks ("If the caller mentions [gas, smoke], bring in a person now")."""

    urgent_keywords: list[str]  # EN and FR words that bring in a person now
    asked_times: int  # caller asks for a person this many times -> bring in a person (default 1)
    low_confidence_turns: int  # 1-5
    distress_threshold: float  # 0.5-0.95
    identity_attempts: int  # 1-5
    offer_person_on_consent_refusal: bool
    max_wait_seconds: int  # then offer a call-back
    urgent_safety_always: bool  # read-only true: urgent safety always reaches a person


class Languages(Model):
    enabled: list[Lang]
    voices: dict[str, VoiceSetting]  # per language
    default: Lang
    detect_automatically: bool
    french_first_regions: list[str]  # Quebec: French first (Law 25 / Charter of the French language)


class Retention(Model):
    """Written as sentences with editable blanks: "Keep recordings for [7 years]"."""

    recordings_years: int  # 1-10, default 7
    transcripts_years: int  # 1-10, default 7
    photos_years: int  # 1-10, default 7
    claim_files_years: int  # read-only 7 (claims records)
    card_number_moments: Literal["always_removed"]  # read-only: cannot be turned off
    refused_consent_transcripts: Literal["not_kept"]  # read-only
    deletion_requests_waiting: int  # privacy deletion requests in the queue
    last_purge_at: datetime | None
    next_purge_on: date | None


class VoiceSetting(Model):
    voice: str  # speechSynthesis / cloud voice name, e.g. "Amélie (fr-CA)"
    speed: float  # 0.8-1.2


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
