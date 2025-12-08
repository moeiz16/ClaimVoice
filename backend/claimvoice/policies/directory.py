"""`PolicyDirectory` for the dialogue's mid-call tools (docs/API_CONTRACT.md Part 3): find a policy, check one
identity detail, read coverage in plain words (never a decision) and count prior claims. Tenant-scoped; each call is
one or two short queries, well inside the tool budgets."""

from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from claimvoice import contracts
from claimvoice.api import labels
from claimvoice.claims.models import Claim
from claimvoice.platform import db
from claimvoice.policies.models import Policy, Policyholder

_LOSS_COVERAGE: dict[str, tuple[str, ...]] = {
    "collision": ("collision", "liability", "rental"),
    "hail": ("wind_hail", "dwelling", "comprehensive"),
    "wind": ("wind_hail", "dwelling", "fence", "comprehensive"),
    "water": ("water_escape", "sewer_backup", "overland_water", "dwelling"),
    "fire": ("dwelling", "contents", "additional_living_expenses", "comprehensive"),
    "theft": ("comprehensive", "contents"),
}


def normalise_policy_number(value: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    m = re.fullmatch(r"LM([A-Z]{2})(\d{6})", compact)
    return f"LM-{m.group(1)}-{m.group(2)}" if m else value.strip().upper()


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _postal(value: str | None) -> str:
    return re.sub(r"\s", "", value or "").upper()


def _money(amount: float | None, currency: str, lang: str) -> str:
    from claimvoice.claims.views import money

    return money(amount or 0, currency, lang)


class SqlPolicyDirectory:
    async def find_policy(
        self,
        org_id: str,
        *,
        policy_number: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
        postal_code: str | None = None,
    ) -> contracts.PolicyMatch | None:
        async with db.sessionmaker()() as session:
            stmt = (
                select(Policy)
                .options(selectinload(Policy.holder), selectinload(Policy.items))
                .join(Policyholder, Policyholder.id == Policy.holder_id)
                .where(Policy.org_id == org_id)
            )
            if policy_number:
                stmt = stmt.where(Policy.policy_number == normalise_policy_number(policy_number))
            elif phone:
                digits = _digits(phone)[-10:]
                if len(digits) < 10:
                    return None
                stmt = stmt.where(Policyholder.phone_e164.like(f"%{digits}"))
            elif full_name and postal_code:
                stmt = stmt.where(
                    func.lower(Policyholder.full_name) == full_name.strip().lower(),
                    func.replace(func.upper(Policyholder.postal_code), " ", "") == _postal(postal_code),
                )
            else:
                return None
            policy = (await session.execute(stmt.order_by(Policy.status, Policy.policy_number))).scalars().first()
        if policy is None:
            return None
        holder = policy.holder
        return contracts.PolicyMatch(
            policy_id=policy.id,
            holder_id=holder.id,
            policy_number=policy.policy_number,
            holder_name=holder.full_name,
            line=policy.line,
            region=policy.region,
            status=policy.status,
            preferred_language=holder.preferred_language,
            phone_on_file_masked=labels.mask_phone(holder.phone_e164),
            insured_items=[{"id": i.id, "kind": i.kind, "label": i.label} for i in policy.items],
        )

    async def verify_identity(
        self, org_id: str, policy_id: str, *, date_of_birth: date | None = None, postal_code: str | None = None
    ) -> bool:
        async with db.sessionmaker()() as session:
            policy = await session.get(Policy, policy_id)
            if policy is None or policy.org_id != org_id:
                return False
            holder = await session.get(Policyholder, policy.holder_id)
        if holder is None:
            return False
        if date_of_birth is not None and holder.date_of_birth == date_of_birth:
            return True
        if postal_code:
            given, on_file = _postal(postal_code), _postal(holder.postal_code)
            # A US ZIP or the first half of a Canadian postal code is enough for one identity detail.
            return bool(given) and (given == on_file or (len(given) == 3 and on_file.startswith(given)))
        return False

    async def coverage(self, org_id: str, policy_id: str, loss_type: str, loss_date: date) -> contracts.CoverageSummary:
        async with db.sessionmaker()() as session:
            policy = (
                await session.execute(
                    select(Policy).options(selectinload(Policy.coverages)).where(Policy.id == policy_id)
                )
            ).scalar_one_or_none()
        if policy is None or policy.org_id != org_id:
            return contracts.CoverageSummary(policy_id, loss_type, False, [], {"en": "", "fr": ""})
        in_force = policy.status == "active" and policy.effective_from <= loss_date <= policy.effective_to
        wanted = _LOSS_COVERAGE.get(loss_type, ())
        lines = [
            contracts.CoverageLine(
                key=c.key,
                label=labels.pick(labels.COVERAGES.get(c.key), "en", c.key),
                included=c.included,
                deductible=c.deductible,
                limit=c.limit,
            )
            for c in policy.coverages
            if c.key in wanted
        ]
        first = next((ln for ln in lines if ln.included), None)
        if not in_force:
            words = {
                "en": "I can't see this policy in force on that date, so a person will look at coverage with you.",
                "fr": "Je ne vois pas cette police en vigueur à cette date; une personne verra la couverture "
                "avec vous.",
            }
        elif first is None:
            words = {
                "en": "I don't see coverage for this kind of loss on the policy. An adjuster will go over it with you.",
                "fr": "Je ne vois pas de couverture pour ce type de sinistre. Un expert la verra avec vous.",
            }
        else:
            label_fr = labels.pick(labels.COVERAGES.get(first.key), "fr", first.key)
            ded_en = _money(first.deductible, policy.currency, "en")
            ded_fr = _money(first.deductible, policy.currency, "fr")
            words = {
                "en": f"Your policy includes {first.label.lower()} coverage with a {ded_en} deductible. "
                "An adjuster confirms what's covered; nothing is decided on this call.",
                "fr": f"Votre police comprend la garantie {label_fr.lower()} avec une franchise de {ded_fr}. "
                "Un expert confirmera ce qui est couvert; rien n'est décidé pendant cet appel.",
            }
        return contracts.CoverageSummary(policy.id, loss_type, in_force, lines, words)

    async def prior_claims(self, org_id: str, holder_id: str, *, months: int = 36) -> int:
        from claimvoice import clock

        since = clock.now() - timedelta(days=months * 30)
        async with db.sessionmaker()() as session:
            return int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(Claim)
                        .where(Claim.org_id == org_id, Claim.holder_id == holder_id, Claim.reported_at >= since)
                    )
                ).scalar_one()
            )


_directory: SqlPolicyDirectory | None = None


def get_directory() -> SqlPolicyDirectory:
    global _directory
    if _directory is None:
        _directory = SqlPolicyDirectory()
    return _directory
