"""§1.9 call quality: the rubric, the review queue, one call's score, a reviewer's verdicts and how often reviewers
agree with the automatic scorer."""

from __future__ import annotations

from datetime import UTC, datetime

from litestar import Router, get, post
from litestar.params import Parameter
from sqlalchemy import select

from claimvoice import clock
from claimvoice.api.context import Ctx, not_found, page_args
from claimvoice.calls import quality, views
from claimvoice.calls.models import Call, QaScoreRow
from claimvoice.platform.errors import ProblemError
from claimvoice.qa.rubric import RUBRIC
from claimvoice.schemas import qa as w
from claimvoice.schemas.base import Page

EMPTY_QUEUE = "Nothing to review. Every call this week met the rubric."


@get("/qa/rubric")
async def rubric(ctx: Ctx) -> list[w.RubricItemInfo]:
    ctx.require("qa:read")
    return [
        w.RubricItemInfo(
            key=r.key, label=r.label, description=r.description, points=r.points, critical=r.critical, bead=r.bead
        )
        for r in RUBRIC
    ]


def _flagged(row: QaScoreRow) -> bool:
    return row.band == "failed" or any(i["critical"] and i["passed"] is False for i in row.items)


@get("/qa/queue")
async def queue(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    status: str = "needs_review",
    item: str | None = None,
    band: str | None = None,
    from_: str | None = Parameter(query="from", default=None),
    to: str | None = None,
) -> Page[w.QaQueueItem]:
    ctx.require("qa:read")
    stmt = (
        select(QaScoreRow, Call)
        .join(Call, Call.id == QaScoreRow.call_id)
        .where(QaScoreRow.org_id == ctx.org_id, Call.is_public_demo.is_(False))
    )
    if status != "all":
        stmt = stmt.where(QaScoreRow.status == status)
    if band:
        stmt = stmt.where(QaScoreRow.band == band)
    for value, field in ((from_, "from"), (to, "to")):
        if value:
            try:
                dt = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ProblemError(400, "bad_request", "Bad request", f"{field} must be an ISO date or time.") from exc
            dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            stmt = stmt.where(Call.answered_at >= dt if field == "from" else Call.answered_at <= dt)
    rows: list[tuple[QaScoreRow, Call]] = [(r, c) for r, c in (await ctx.db.execute(stmt)).all()]
    if item:
        rows = [(r, c) for r, c in rows if any(i["key"] == item and i["passed"] is False for i in r.items)]
    rows.sort(key=lambda rc: (not _flagged(rc[0]), rc[0].score, rc[1].answered_at))
    p, size = page_args(page, page_size)
    chunk = rows[(p - 1) * size : p * size]
    claims = await views.claims_for_calls(ctx.db, [c.id for _, c in chunk])
    people = await views.users_by_id(ctx.db, [r.reviewed_by for r, _ in chunk])
    items = [quality.queue_item(r, c, claims.get(c.id), people, ctx.lang) for r, c in chunk]
    total = len(rows)
    return Page(items=items, page=p, page_size=size, total=total, total_pages=max(1, -(-total // size)))


async def _score_row(ctx: Ctx, call_id: str) -> tuple[QaScoreRow, Call]:
    call = await ctx.get(Call, call_id)
    row = (await ctx.db.execute(select(QaScoreRow).where(QaScoreRow.call_id == call.id))).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row, call


async def _score_out(ctx: Ctx, row: QaScoreRow, call: Call) -> w.QaScore:
    claim = (await views.claims_for_calls(ctx.db, [call.id])).get(call.id)
    people = await views.users_by_id(ctx.db, [row.reviewed_by])
    return quality.score_out(row, claim, people, ctx.lang)


@get("/qa/calls/{call_id:str}")
async def call_score(ctx: Ctx, call_id: str) -> w.QaScore:
    ctx.require("qa:read")
    row, call = await _score_row(ctx, call_id)
    return await _score_out(ctx, row, call)


@post("/qa/calls/{call_id:str}/review", status_code=200)
async def review(ctx: Ctx, call_id: str, data: w.ReviewIn) -> w.QaScore:
    ctx.require("qa:review")
    row, call = await _score_row(ctx, call_id)
    keys = {i["key"] for i in row.items}
    seen: set[str] = set()
    for i, it in enumerate(data.items):
        if it.key not in keys or it.key in seen:
            raise ProblemError(
                422,
                "validation_error",
                "Validation failed",
                errors=[{"field": f"items[{i}].key", "message": "Choose a rubric item once."}],
            )
        if it.verdict == "disagree" and not (it.note or "").strip():
            raise ProblemError(
                422,
                "validation_error",
                "Validation failed",
                errors=[{"field": f"items[{i}].note", "message": "Say why you disagree."}],
            )
        seen.add(it.key)
    row.review = {
        "items": [
            {"key": it.key, "verdict": it.verdict, "note": (it.note or "").strip()[:500] or None} for it in data.items
        ],
        "note": (data.note or "").strip()[:1000] or None,
    }
    row.coaching_note = (data.coaching_note or "").strip()[:1000] or None
    row.status, row.reviewed_by, row.reviewed_at = "reviewed", ctx.user.id, clock.now()
    await ctx.db.commit()
    disagreed = sum(1 for it in data.items if it.verdict == "disagree")
    await ctx.audit(
        "qa.review",
        f"{ctx.user.full_name} reviewed {call.reference}: agreed on {_items(len(data.items) - disagreed)}, "
        f"disagreed on {_items(disagreed)}.",
        target_type="call",
        target_id=call.id,
        target_label=call.reference,
        details={"disagreed": disagreed, "coaching": bool(row.coaching_note)},
    )
    return await _score_out(ctx, row, call)


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Agreement between the scorer's pass/fail and the reviewer's, corrected for chance."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


@get("/qa/agreement")
async def agreement(ctx: Ctx) -> w.Agreement:
    ctx.require("qa:read")
    rows = (
        (
            await ctx.db.execute(
                select(QaScoreRow).where(QaScoreRow.org_id == ctx.org_id, QaScoreRow.status == "reviewed")
            )
        )
        .scalars()
        .all()
    )
    per: dict[str, list[bool]] = {}
    pairs: list[tuple[bool, bool]] = []
    for r in rows:
        passed = {i["key"]: i["passed"] for i in r.items}
        for v in (r.review or {}).get("items", []):
            agree = v["verdict"] == "agree"
            per.setdefault(v["key"], []).append(agree)
            scorer = passed.get(v["key"])
            if scorer is not None:
                pairs.append((bool(scorer), bool(scorer) if agree else not scorer))
    labels = {r.key: r.label for r in RUBRIC}
    all_votes = [a for votes in per.values() for a in votes]
    return w.Agreement(
        reviewed_calls=len(rows),
        overall=round(sum(all_votes) / len(all_votes), 3) if all_votes else 1.0,
        cohen_kappa=cohen_kappa(pairs),
        by_item=[
            w.AgreementRow(key=k, label=labels.get(k, k), reviewed=len(v), agreement=round(sum(v) / len(v), 3))
            for k, v in sorted(
                per.items(), key=lambda kv: [r.key for r in RUBRIC].index(kv[0]) if kv[0] in labels else 99
            )
        ],
    )


ROUTER = Router(path="/api/v1", route_handlers=[rubric, queue, call_score, review, agreement])


def _items(n: int) -> str:
    return "1 item" if n == 1 else f"{n} items"
