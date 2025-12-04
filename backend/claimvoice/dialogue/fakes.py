"""In-memory `PolicyDirectory` and `OrgPlaybook` for tests, the eval harness, scripted demo calls and the voice runtime
before the platform's database-backed versions are wired. Both read the bundled demo policy book
(`dialogue/data/demo_policies.json`) and the default scripts (`dialogue/scripts/*.yml`)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from claimvoice import clock
from claimvoice.contracts import (
    ConsentRule,
    CoverageLine,
    CoverageSummary,
    HandoffRules,
    PolicyMatch,
    Script,
)
from claimvoice.dialogue.scripts import load_default_scripts
from claimvoice.reference import REGIONS

POLICY_BOOK = Path(__file__).parent / "data" / "demo_policies.json"

ANNOUNCEMENT = {
    "en": "This call is recorded so we get your claim right.",
    "fr": "Cet appel est enregistré pour que nous traitions bien votre réclamation.",
}

# Which coverage answers which loss (water depends on where it came from; the engine passes the source along).
COVERAGE_FOR: dict[str, tuple[str, ...]] = {
    "wind": ("wind_hail", "dwelling", "fence", "comprehensive"),
    "hail": ("wind_hail", "dwelling", "comprehensive"),
    "water": ("dwelling", "sewer_backup", "overland_water"),
    "water:burst_pipe": ("dwelling",),
    "water:sewer_backup": ("sewer_backup",),
    "water:overland": ("overland_water",),
    "fire": ("dwelling", "contents", "additional_living_expenses"),
    "theft": ("contents", "comprehensive"),
    "collision": ("collision", "rental"),
}


@cache
def demo_policy_book() -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(POLICY_BOOK.read_text(encoding="utf-8"))["policies"])


def _norm_postal(text: str | None) -> str:
    return (text or "").replace(" ", "").upper()


def _money(amount: float | None, currency: str, language: str) -> str:
    if amount is None:
        return ""
    if language == "fr":
        return f"{amount:,.0f} $".replace(",", " ")
    return f"${amount:,.0f}"


def coverage_words(
    lines: Sequence[CoverageLine], loss_type: str, product: str, currency: str, in_force: bool
) -> dict[str, str]:
    if not in_force:
        return {
            "en": "Your policy doesn't show as active on that date, so an adjuster will look at that with you first.",
            "fr": "Votre police ne semble pas en vigueur à cette date; un expert en sinistres va vérifier cela avec "
            "vous en premier.",
        }
    included = [c for c in lines if c.included]
    missing = [c for c in lines if not c.included]
    out: dict[str, str] = {}
    for lang in ("en", "fr"):
        parts: list[str] = []
        if included:
            first = included[0]
            ded = _money(first.deductible, currency, lang)
            if lang == "en":
                names = " and ".join(c.label.lower() for c in included[:2])
                parts.append(f"Your {product} policy includes {names}")
                parts[-1] += f", with a {ded} deductible." if first.deductible else "."
            else:
                names = " et ".join(c.label.lower() for c in included[:2])
                parts.append(f"Votre police {product} comprend : {names}")
                parts[-1] += f", avec une franchise de {ded}." if first.deductible else "."
        if missing and loss_type == "water":
            label = missing[0].label.lower()
            parts.append(
                f"It doesn't include {label}, so the adjuster will look at the cause with you."
                if lang == "en"
                else f"Elle ne comprend pas : {label}; l'expert en sinistres va donc examiner la cause avec vous."
            )
        parts.append(
            "An adjuster confirms the details. I can't make a decision on the claim."
            if lang == "en"
            else "Un expert en sinistres confirmera les détails. Je ne peux pas prendre de décision sur la réclamation."
        )
        out[lang] = " ".join(parts)
    return out


@dataclass
class MemoryPolicyDirectory:
    """`PolicyDirectory` over the bundled demo policy book (or any list of the same shape)."""

    policies: Sequence[Mapping[str, Any]] = field(default_factory=demo_policy_book)
    delay_ms: float = 0.0  # simulated lookup time (latency tests)
    fail: bool = False  # simulate an outage (tool-failure tests)

    async def _wait(self) -> None:
        if self.fail:
            raise ConnectionError("policy directory unavailable")
        if self.delay_ms:
            import asyncio

            await asyncio.sleep(self.delay_ms / 1000)

    def _by_number(self, number: str) -> Mapping[str, Any] | None:
        return next((p for p in self.policies if p["policyNumber"].upper() == number.upper()), None)

    @staticmethod
    def _match(p: Mapping[str, Any]) -> PolicyMatch:
        return PolicyMatch(
            policy_id=p.get("id") or p["policyNumber"],
            holder_id=p.get("holderId") or "holder-" + p["policyNumber"],
            policy_number=p["policyNumber"],
            holder_name=p["holderName"],
            line=p["line"],
            region=p["region"],
            status=p["status"],
            preferred_language=p["preferredLanguage"],
            phone_on_file_masked="•••-•••-" + p["phone"][-4:] if p.get("phone") else None,
            insured_items=(
                {
                    "id": "item-" + p["policyNumber"],
                    "kind": "vehicle" if p["line"] == "auto" else "property",
                    "label": p["insuredItem"],
                },
            ),
        )

    async def find_policy(
        self,
        org_id: str,
        *,
        policy_number: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
        postal_code: str | None = None,
    ) -> PolicyMatch | None:
        await self._wait()
        p: Mapping[str, Any] | None = None
        if policy_number:
            p = self._by_number(policy_number)
        elif phone:
            digits = "".join(c for c in phone if c.isdigit())[-10:]
            p = next((x for x in self.policies if x.get("phone", "").endswith(digits)), None)
        return self._match(p) if p else None

    async def verify_identity(
        self, org_id: str, policy_id: str, *, date_of_birth: date | None = None, postal_code: str | None = None
    ) -> bool:
        await self._wait()
        p = self._by_number(policy_id) or next((x for x in self.policies if x.get("id") == policy_id), None)
        if p is None:
            return False
        if date_of_birth is not None and p.get("dateOfBirth") == date_of_birth.isoformat():
            return True
        return postal_code is not None and _norm_postal(postal_code) == _norm_postal(p.get("postalCode"))

    async def coverage(self, org_id: str, policy_id: str, loss_type: str, loss_date: date) -> CoverageSummary:
        await self._wait()
        p = self._by_number(policy_id) or next((x for x in self.policies if x.get("id") == policy_id), None)
        if p is None:
            raise LookupError(policy_id)
        keys = COVERAGE_FOR.get(loss_type, COVERAGE_FOR.get(loss_type.split(":")[0], ()))
        lines = [
            CoverageLine(c["key"], c["label"]["en"], c["included"], c["deductible"], c["limit"])
            for c in p["coverages"]
            if c["key"] in keys
        ]
        in_force = p["status"] == "active" and date.fromisoformat(p["effectiveFrom"]) <= loss_date
        currency = "USD" if p["region"].startswith("US") else "CAD"
        words = coverage_words(lines, loss_type.split(":")[0], p["product"], currency, in_force)
        if any(True for _ in lines):
            fr_lines = {c["key"]: c["label"]["fr"] for c in p["coverages"]}
            words["fr"] = coverage_words(
                [CoverageLine(x.key, fr_lines.get(x.key, x.label), x.included, x.deductible, x.limit) for x in lines],
                loss_type.split(":")[0],
                p["product"],
                currency,
                in_force,
            )["fr"]
        return CoverageSummary(p["policyNumber"], loss_type, in_force, tuple(lines), words)

    async def prior_claims(self, org_id: str, holder_id: str, *, months: int = 36) -> int:
        await self._wait()
        p = next((x for x in self.policies if "holder-" + x["policyNumber"] == holder_id), None)
        return int(p.get("priorClaims36m", 0)) if p else 0

    def record(self, policy_number: str) -> Mapping[str, Any] | None:
        """The raw policy record (tests and routing features: tenure, coverage changes)."""
        return self._by_number(policy_number)


@dataclass
class YamlPlaybook:
    """`OrgPlaybook` from the default scripts, the reference consent rules and the bundled weather snapshot."""

    scripts: Mapping[str, Script] = field(default_factory=load_default_scripts)
    rules: HandoffRules = field(default_factory=HandoffRules)
    surge_questions_on: bool = False
    surge_region: str | None = "CA-AB"  # the Chinook surge; None for no surge
    org_name: str = "Larkspur Mutual"

    async def script(self, org_id: str, loss_type: str) -> Script:
        return self.scripts[loss_type]

    async def consent_rule(self, org_id: str, region: str) -> ConsentRule:
        info = REGIONS.get(region)
        rule = info["consent"] if info else "all_party"  # unknown region: the strict rule
        return ConsentRule(region, rule, dict(ANNOUNCEMENT))

    async def handoff_rules(self, org_id: str) -> HandoffRules:
        return self.rules

    async def active_surge(self, org_id: str, region: str) -> Mapping[str, Any] | None:
        if self.surge_region is None or region != self.surge_region:
            return None
        return {
            "id": "surge-chinook",
            "kind": "wind",
            "title": "Chinook windstorm, Calgary",
            "region": region,
            "lossTypes": ["wind"],
            "surgeQuestionsOn": self.surge_questions_on,
            "startedAt": datetime.combine(clock.today(), datetime.min.time()).isoformat(),
        }
