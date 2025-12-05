"""§1.12 the activity log: hash-chained entries, chain verification and CSV export."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from litestar import Response, Router, get
from litestar.params import Parameter
from sqlalchemy import Select, select

from claimvoice import clock
from claimvoice.api.context import Ctx, paged
from claimvoice.platform import auditlog
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.models import AuditEvent
from claimvoice.schemas.audit import AuditEntry, ChainStatus
from claimvoice.schemas.base import Page

ACTION_LABELS: dict[str, str] = {
    "auth.login": "signed in",
    "auth.login_failed": "sign-in failed",
    "auth.logout": "signed out",
    "auth.password_changed": "changed their password",
    "member.role_changed": "changed a role",
    "member.removed": "removed a member",
    "invitation.created": "invited someone",
    "invitation.revoked": "withdrew an invitation",
    "invitation.accepted": "accepted an invitation",
    "org.updated": "updated the organisation",
    "call.listen": "listened in",
    "call.whisper": "whispered to the line",
    "call.handoff_accepted": "took a hand-off",
    "call.takeover": "took over",
    "call.returned": "handed back to the line",
    "call.hangup": "ended a call",
    "claim.created": "opened a claim",
    "claim.file_edited": "corrected the claim file",
    "claim.assigned": "assigned a claim",
    "claim.route_accepted": "accepted a route",
    "claim.route_override": "changed a route",
    "claim.status_changed": "changed a claim's status",
    "siu.referral_opened": "asked for a closer look",
    "siu.decision": "decided a closer-look referral",
    "qa.review": "reviewed a call",
    "check.signed_off": "signed off a routing check",
    "check.version_in_use": "put a routing check version into use",
    "check.regulator_pack": "downloaded the regulator pack",
    "surge.standby_called": "brought in the standby team",
    "surge.questions": "switched surge questions",
    "retention.purged": "removed expired recordings",
    "recording.played": "played a recording",
    "audit.exported": "exported the activity log",
    "photo.received": "received a photo",
}


def action_label(action: str) -> str:
    if action in ACTION_LABELS:
        return ACTION_LABELS[action]
    if action.startswith("settings."):
        return "changed a setting"
    return action.split(".")[-1].replace("_", " ")


def entry_out(e: AuditEvent) -> AuditEntry:
    details = dict(e.details or {})
    target_label = details.pop("targetLabel", None)
    return AuditEntry(
        id=e.id,
        seq=e.seq,
        at=e.at,
        actor_label=e.actor_label,
        action=e.action,
        action_label=action_label(e.action),
        target_type=e.target_type,
        target_id=e.target_id,
        target_label=target_label,
        summary=e.summary,
        details=details,
    )


def _when(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProblemError(400, "bad_request", "Bad request", f"{field} must be an ISO date or time.") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _filtered(
    ctx: Ctx, action: str | None, actor: str | None, target: str | None, start: str | None, end: str | None
) -> Select[Any]:
    stmt: Select[Any] = select(AuditEvent).where(AuditEvent.org_id == ctx.org_id)
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action))
    if actor:
        stmt = stmt.where(AuditEvent.actor_user_id == actor)
    if target:
        kind, _, ident = target.partition(":")
        stmt = stmt.where(AuditEvent.target_type == kind)
        if ident:
            stmt = stmt.where(AuditEvent.target_id == ident)
    if (s := _when(start, "from")) is not None:
        stmt = stmt.where(AuditEvent.at >= s)
    if (e := _when(end, "to")) is not None:
        stmt = stmt.where(AuditEvent.at <= e)
    return stmt.order_by(AuditEvent.seq.desc())


@get("/audit")
async def list_audit(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    action: str | None = None,
    actor: str | None = None,
    target: str | None = None,
    from_: str | None = Parameter(query="from", default=None),
    to: str | None = None,
) -> Page[AuditEntry]:
    ctx.require("audit:read")

    def mapper(rows: Sequence[AuditEvent]) -> list[AuditEntry]:
        return [entry_out(e) for e in rows]

    return await paged(ctx.db, _filtered(ctx, action, actor, target, from_, to), page, page_size, mapper)


@get("/audit/verify")
async def verify(ctx: Ctx) -> ChainStatus:
    ctx.require("audit:read")
    check = await auditlog.verify_org(ctx.db, ctx.org_id)
    return ChainStatus(
        ok=check.ok,
        checked=check.checked,
        first_broken_seq=check.first_broken_seq,
        reason=check.reason,
        checked_at=clock.now(),
    )


@get("/audit/export.csv")
async def export_csv(
    ctx: Ctx,
    action: str | None = None,
    actor: str | None = None,
    target: str | None = None,
    from_: str | None = Parameter(query="from", default=None),
    to: str | None = None,
) -> Response[bytes]:
    ctx.require("audit:read")
    rows = (await ctx.db.execute(_filtered(ctx, action, actor, target, from_, to).limit(50_000))).scalars().all()
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(["seq", "at", "person", "action", "target", "summary", "hash"])
    for e in rows:
        target_label = (e.details or {}).get("targetLabel") or ""
        out.writerow([e.seq, e.at.isoformat(), e.actor_label, e.action, target_label, _safe(e.summary), e.hash])
    await ctx.audit(
        "audit.exported",
        f"{ctx.user.full_name} exported {len(rows)} activity entries.",
        target_type="audit",
        target_id="export",
        target_label="Activity log",
        details={"filters": {"action": action, "actor": actor, "target": target}},
    )
    return Response(
        buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="claimvoice-activity.csv"'},
    )


def _safe(text: str) -> str:
    """Neutralise spreadsheet formulas in exported text."""
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


ROUTER = Router(path="/api/v1", route_handlers=[list_audit, verify, export_csv])
