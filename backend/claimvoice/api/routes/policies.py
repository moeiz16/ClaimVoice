"""§1.5 policies and policyholders. Personal data is masked in lists and detail alike; date of birth never leaves."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import msgspec
from litestar import Router, get
from litestar.params import Parameter
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from claimvoice import clock
from claimvoice.api import labels
from claimvoice.api.context import Ctx, paged
from claimvoice.claims import views as claim_views
from claimvoice.claims.models import Claim
from claimvoice.policies.models import Policy, Policyholder
from claimvoice.schemas.base import Page
from claimvoice.schemas.policies import Coverage, InsuredItem, PolicyholderSummary, PolicySummary
from claimvoice.schemas.policies import Policy as PolicyOut
from claimvoice.schemas.policies import Policyholder as PolicyholderOut


async def _open_claims(ctx: Ctx, policy_ids: Sequence[str]) -> dict[str, int]:
    if not policy_ids:
        return {}
    rows = await ctx.db.execute(
        select(Claim.policy_id, func.count())
        .where(Claim.policy_id.in_(policy_ids), Claim.status != "closed")
        .group_by(Claim.policy_id)
    )
    return {r[0]: int(r[1]) for r in rows.all()}


def policy_summary(p: Policy, holder: Policyholder, open_claims: int, lang: str) -> PolicySummary:
    return PolicySummary(
        id=p.id,
        policy_number=p.policy_number,
        holder_id=holder.id,
        holder_name=holder.full_name,
        line=labels.lit(p.line),
        line_label=labels.pick(labels.LINES.get(p.line), lang, p.line),
        product_label=labels.pick(labels.PRODUCTS.get(p.product), lang, p.product),
        region=p.region,
        region_label=labels.region(p.region, lang) or p.region,
        status=labels.lit(p.status),
        status_label=labels.pick(labels.POLICY_STATUSES.get(p.status), lang, p.status),
        effective_from=p.effective_from,
        effective_to=p.effective_to,
        open_claims=open_claims,
    )


@get("/policies")
async def list_policies(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    q: str | None = None,
    line: str | None = None,
    region: str | None = None,
    status: str | None = None,
) -> Page[PolicySummary]:
    ctx.require("policies:read")
    stmt: Select[Any] = (
        select(Policy)
        .join(Policyholder, Policyholder.id == Policy.holder_id)
        .options(selectinload(Policy.holder))
        .where(Policy.org_id == ctx.org_id)
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Policy.policy_number.ilike(like), Policyholder.full_name.ilike(like)))
    if line:
        stmt = stmt.where(Policy.line == line)
    if region:
        stmt = stmt.where(Policy.region == region)
    if status and status != "all":
        stmt = stmt.where(Policy.status == status)
    stmt = stmt.order_by(Policy.policy_number)

    async def mapper(rows: Sequence[Policy]) -> list[PolicySummary]:
        counts = await _open_claims(ctx, [p.id for p in rows])
        return [policy_summary(p, p.holder, counts.get(p.id, 0), ctx.lang) for p in rows]

    return await paged(ctx.db, stmt, page, page_size, mapper)


@get("/policies/{policy_id:str}")
async def get_policy(ctx: Ctx, policy_id: str) -> PolicyOut:
    ctx.require("policies:read")
    p = await ctx.get(Policy, policy_id)
    p = (
        await ctx.db.execute(
            select(Policy)
            .options(selectinload(Policy.holder), selectinload(Policy.coverages), selectinload(Policy.items))
            .where(Policy.id == p.id)
        )
    ).scalar_one()
    claims = (
        (
            await ctx.db.execute(
                select(Claim).where(Claim.policy_id == p.id).order_by(Claim.reported_at.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )
    base = policy_summary(p, p.holder, sum(1 for c in claims if c.status != "closed"), ctx.lang)
    fields = {f: getattr(base, f) for f in base.__struct_fields__}
    return PolicyOut(
        **fields,
        coverages=[
            Coverage(
                key=c.key,
                label=labels.pick(labels.COVERAGES.get(c.key), ctx.lang, c.key),
                included=c.included,
                limit=c.limit,
                deductible=c.deductible,
                currency=labels.lit(p.currency),
            )
            for c in p.coverages
        ],
        insured_items=[
            InsuredItem(id=i.id, kind=labels.lit(i.kind), label=i.label, details=i.details) for i in p.items
        ],
        premium=p.premium,
        currency=labels.lit(p.currency),
        coverage_changed_at=p.coverage_changed_at,
        recent_claims=[
            msgspec.to_builtins(s) for s in await claim_views.summaries(ctx.db, claims, ctx.lang, siu=ctx.siu)
        ],
        is_sample=p.is_sample,
    )


async def _holder_counts(ctx: Ctx, holder_ids: Sequence[str]) -> tuple[dict[str, int], dict[str, int]]:
    if not holder_ids:
        return {}, {}
    policies = dict(
        (
            await ctx.db.execute(
                select(Policy.holder_id, func.count())
                .where(Policy.holder_id.in_(holder_ids))
                .group_by(Policy.holder_id)
            )
        ).all()
    )
    since = clock.now() - timedelta(days=36 * 30)
    claims = dict(
        (
            await ctx.db.execute(
                select(Claim.holder_id, func.count())
                .where(Claim.holder_id.in_(holder_ids), Claim.reported_at >= since)
                .group_by(Claim.holder_id)
            )
        ).all()
    )
    return policies, claims


def holder_summary(h: Policyholder, policies: int, claims: int, lang: str) -> PolicyholderSummary:
    return PolicyholderSummary(
        id=h.id,
        full_name=h.full_name,
        phone_masked=labels.mask_phone(h.phone_e164) or "•••",
        email_masked=labels.mask_email(h.email),
        city=h.city,
        region=h.region,
        region_label=labels.region(h.region, lang) or h.region,
        preferred_language="fr" if h.preferred_language == "fr" else "en",
        policies=policies,
        claims_36m=claims,
    )


@get("/policyholders")
async def list_holders(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    q: str | None = None,
    region: str | None = None,
) -> Page[PolicyholderSummary]:
    ctx.require("policies:read")
    stmt: Select[Any] = select(Policyholder).where(Policyholder.org_id == ctx.org_id)
    if q:
        stmt = stmt.where(Policyholder.full_name.ilike(f"%{q.strip()}%"))
    if region:
        stmt = stmt.where(Policyholder.region == region)
    stmt = stmt.order_by(Policyholder.full_name)

    async def mapper(rows: Sequence[Policyholder]) -> list[PolicyholderSummary]:
        pol, cl = await _holder_counts(ctx, [h.id for h in rows])
        return [holder_summary(h, int(pol.get(h.id, 0)), int(cl.get(h.id, 0)), ctx.lang) for h in rows]

    return await paged(ctx.db, stmt, page, page_size, mapper)


@get("/policyholders/{holder_id:str}")
async def get_holder(ctx: Ctx, holder_id: str) -> PolicyholderOut:
    ctx.require("policies:read")
    h = await ctx.get(Policyholder, holder_id)
    pol, cl = await _holder_counts(ctx, [h.id])
    base = holder_summary(h, int(pol.get(h.id, 0)), int(cl.get(h.id, 0)), ctx.lang)
    policies = (
        (await ctx.db.execute(select(Policy).where(Policy.holder_id == h.id).order_by(Policy.policy_number)))
        .scalars()
        .all()
    )
    open_counts = await _open_claims(ctx, [p.id for p in policies])
    claims = (
        (await ctx.db.execute(select(Claim).where(Claim.holder_id == h.id).order_by(Claim.reported_at.desc())))
        .scalars()
        .all()
    )
    fields = {f: getattr(base, f) for f in base.__struct_fields__}
    return PolicyholderOut(
        **fields,
        postal_code_masked=labels.mask_postal(h.postal_code),
        customer_since=h.customer_since,
        policy_list=[policy_summary(p, h, open_counts.get(p.id, 0), ctx.lang) for p in policies],
        claims=[msgspec.to_builtins(s) for s in await claim_views.summaries(ctx.db, claims, ctx.lang, siu=ctx.siu)],
        created_at=h.created_at,
    )


ROUTER = Router(path="/api/v1", route_handlers=[list_policies, get_policy, list_holders, get_holder])
