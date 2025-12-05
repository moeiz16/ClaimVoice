"""§1.4 organisation, members, invitations and roles; §1.13 reference data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from litestar import Request, Response, Router, delete, get, patch, post
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import __version__, clock, reference
from claimvoice.api import labels
from claimvoice.api.context import Ctx, client_ip, request_language
from claimvoice.api.routes.auth import _EMAIL, _session_cookies, build_me, count_admins, password_problems
from claimvoice.config import get_settings
from claimvoice.dialogue.stages import STAGE_LABELS
from claimvoice.platform import auditlog, sessions
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.models import Invitation, Membership, Organization, Session, User
from claimvoice.platform.permissions import ROLE_PERMISSIONS, Role
from claimvoice.platform.security import hash_password, new_token, token_digest
from claimvoice.schemas.auth import (
    Invitation as InvitationOut,
)
from claimvoice.schemas.auth import (
    InvitationAcceptIn,
    InvitationIn,
    InvitationPreview,
    Me,
    Member,
    MemberUpdateIn,
    Org,
    OrgUpdateIn,
    RoleInfo,
)
from claimvoice.schemas.base import Labeled
from claimvoice.schemas.meta import LossTypeInfo, Meta, RegionInfo

INVITE_DAYS = 7
LOSS_TYPE_LINE = {
    "collision": "auto",
    "hail": "property",
    "wind": "property",
    "water": "property",
    "fire": "property",
    "theft": "property",
}


def _org_out(org: Organization) -> Org:
    from claimvoice.api.routes.auth import org_out

    return org_out(org)


@get("/org")
async def get_org(ctx: Ctx) -> Org:
    ctx.require("members:read")
    return _org_out(ctx.org)


@patch("/org")
async def update_org(ctx: Ctx, data: OrgUpdateIn) -> Org:
    ctx.require("org:manage")
    changed: dict[str, Any] = {}
    if data.name is not None and data.name.strip():
        ctx.org.name = changed["name"] = data.name.strip()[:160]
    if data.timezone is not None:
        try:
            ZoneInfo(data.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ProblemError(
                422,
                "validation_error",
                "Validation failed",
                errors=[{"field": "timezone", "message": "Choose a time zone from the list."}],
            ) from exc
        ctx.org.timezone = changed["timezone"] = data.timezone
    if data.languages is not None:
        if not data.languages:
            raise ProblemError(
                422,
                "validation_error",
                "Validation failed",
                errors=[{"field": "languages", "message": "Keep at least one language."}],
            )
        ctx.org.languages = changed["languages"] = list(dict.fromkeys(data.languages))
    await ctx.db.commit()
    await ctx.audit(
        "org.updated",
        f"{ctx.user.full_name} updated the organisation's details.",
        target_type="org",
        target_id=ctx.org.id,
        target_label=ctx.org.name,
        details=changed,
    )
    return _org_out(ctx.org)


async def _members(ctx: Ctx) -> list[Member]:
    rows = (
        await ctx.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == ctx.org_id)
            .order_by(User.full_name)
        )
    ).all()
    last_seen = dict(
        (
            await ctx.db.execute(
                select(Session.user_id, Session.last_seen_at).where(
                    Session.user_id.in_([u.id for _, u in rows]), Session.active_org_id == ctx.org_id
                )
            )
        ).all()
    )
    return [_member_out(m, u, ctx.user.id, last_seen.get(u.id)) for m, u in rows]


def _member_out(m: Membership, u: User, me: str, last_active: Any = None) -> Member:
    return Member(
        membership_id=m.id,
        user_id=u.id,
        full_name=u.full_name,
        email=u.email,
        role=m.role,
        role_label=labels.role_label(m.role),
        title=m.title,
        avatar_color=u.avatar_color,
        joined_at=m.created_at,
        last_active_at=last_active or u.last_login_at,
        is_you=u.id == me,
    )


@get("/org/members")
async def list_members(ctx: Ctx) -> list[Member]:
    ctx.require("members:read")
    return await _members(ctx)


@patch("/org/members/{membership_id:str}")
async def update_member(ctx: Ctx, membership_id: str, data: MemberUpdateIn) -> Member:
    ctx.require("members:manage")
    m = await ctx.get(Membership, membership_id)
    user = await ctx.db.get(User, m.user_id)
    assert user is not None
    before = m.role
    if data.role is not None:
        try:
            Role(data.role)
        except ValueError as exc:
            raise ProblemError(
                422, "validation_error", "Validation failed", errors=[{"field": "role", "message": "Unknown role."}]
            ) from exc
        if m.role == "admin" and data.role != "admin" and await count_admins(ctx.db, ctx.org_id) <= 1:
            raise ProblemError(
                409, "last_admin", "Keep one administrator", "Someone else must be an administrator first."
            )
        m.role = data.role
    if data.title is not None:
        m.title = data.title.strip()[:120] or None
    await ctx.db.commit()
    if before != m.role:
        await ctx.audit(
            "member.role_changed",
            f"{ctx.user.full_name} changed {user.full_name}'s role from {labels.role_label(before)} to "
            f"{labels.role_label(m.role)}.",
            target_type="member",
            target_id=m.id,
            target_label=user.full_name,
            details={"from": before, "to": m.role},
        )
    return _member_out(m, user, ctx.user.id)


@delete("/org/members/{membership_id:str}", status_code=204)
async def remove_member(ctx: Ctx, membership_id: str) -> None:
    ctx.require("members:manage")
    m = await ctx.get(Membership, membership_id)
    if m.role == "admin" and await count_admins(ctx.db, ctx.org_id) <= 1:
        raise ProblemError(409, "last_admin", "Keep one administrator", "Someone else must be an administrator first.")
    user = await ctx.db.get(User, m.user_id)
    name = user.full_name if user else "A member"
    await ctx.db.delete(m)
    await ctx.db.commit()
    await ctx.audit(
        "member.removed",
        f"{ctx.user.full_name} removed {name} from the organisation.",
        target_type="member",
        target_id=membership_id,
        target_label=name,
    )


def _invitation_status(inv: Invitation) -> str:
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    if clock.real_now() >= inv.expires_at:
        return "expired"
    return "pending"


async def _invitation_out(ctx: Ctx, inv: Invitation, accept_url: str | None = None) -> InvitationOut:
    inviter = await ctx.db.get(User, inv.invited_by) if inv.invited_by else None
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=inv.role,
        role_label=labels.role_label(inv.role),
        invited_by=inviter.full_name if inviter else None,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        status=labels.lit(_invitation_status(inv)),
        accept_url=accept_url,
    )


@get("/org/invitations")
async def list_invitations(ctx: Ctx) -> list[InvitationOut]:
    ctx.require("members:manage")
    rows = (
        (
            await ctx.db.execute(
                select(Invitation).where(Invitation.org_id == ctx.org_id).order_by(Invitation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _invitation_out(ctx, inv) for inv in rows]


@post("/org/invitations", status_code=201)
async def invite(ctx: Ctx, data: InvitationIn) -> InvitationOut:
    ctx.require("members:manage")
    email = data.email.strip().lower()
    errors = []
    if not _EMAIL.match(email):
        errors.append({"field": "email", "message": "Enter a valid email address."})
    try:
        Role(data.role)
    except ValueError:
        errors.append({"field": "role", "message": "Choose a role."})
    if errors:
        raise ProblemError(422, "validation_error", "Validation failed", errors=errors)
    existing = (
        await ctx.db.execute(
            select(Membership.id)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == ctx.org_id, User.email == email)
        )
    ).first()
    if existing:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "email", "message": "This person is already a member."}],
        )
    token = new_token()
    inv = Invitation(
        org_id=ctx.org_id,
        email=email,
        role=data.role,
        token_hash=token_digest(token),
        invited_by=ctx.user.id,
        expires_at=clock.real_now() + timedelta(days=INVITE_DAYS),
    )
    ctx.db.add(inv)
    await ctx.db.commit()
    await ctx.audit(
        "invitation.created",
        f"{ctx.user.full_name} invited {email} as {labels.role_label(data.role)}.",
        target_type="invitation",
        target_id=inv.id,
        target_label=email,
    )
    show = get_settings().environment != "production" or ctx.org.is_sample
    url = f"{get_settings().web_origin}/invite/{token}" if show else None
    return await _invitation_out(ctx, inv, url)


@delete("/org/invitations/{invitation_id:str}", status_code=204)
async def revoke_invitation(ctx: Ctx, invitation_id: str) -> None:
    ctx.require("members:manage")
    inv = await ctx.get(Invitation, invitation_id)
    if inv.revoked_at is None and inv.accepted_at is None:
        inv.revoked_at = clock.real_now()
        await ctx.db.commit()
        await ctx.audit(
            "invitation.revoked",
            f"{ctx.user.full_name} withdrew the invitation for {inv.email}.",
            target_type="invitation",
            target_id=inv.id,
            target_label=inv.email,
        )


async def _open_invitation(db: AsyncSession, token: str) -> Invitation:
    inv = (
        await db.execute(select(Invitation).where(Invitation.token_hash == token_digest(token)))
    ).scalar_one_or_none()
    if inv is None or inv.revoked_at is not None or inv.accepted_at is not None:
        raise ProblemError(404, "not_found", "Not found")
    if clock.real_now() >= inv.expires_at:
        raise ProblemError(410, "expired", "This invitation has expired", "Ask for a new invitation.")
    return inv


@get("/invitations/{token:str}")
async def preview_invitation(db_session: AsyncSession, token: str) -> InvitationPreview:
    inv = await _open_invitation(db_session, token)
    org = await db_session.get(Organization, inv.org_id)
    assert org is not None
    return InvitationPreview(
        org_name=org.name, email=inv.email, role_label=labels.role_label(inv.role), expires_at=inv.expires_at
    )


@post("/invitations/{token:str}/accept", status_code=200)
async def accept_invitation(
    request: Request[Any, Any, Any], db_session: AsyncSession, token: str, data: InvitationAcceptIn
) -> Response[Me]:
    inv = await _open_invitation(db_session, token)
    user = (await db_session.execute(select(User).where(User.email == inv.email))).scalar_one_or_none()
    if user is None:
        weak = password_problems(data.password, inv.email)
        if weak:
            raise ProblemError(
                422,
                "weak_password",
                "Choose a stronger password",
                weak,
                errors=[{"field": "password", "message": weak}],
            )
        if not data.full_name.strip():
            raise ProblemError(
                422,
                "validation_error",
                "Validation failed",
                errors=[{"field": "fullName", "message": "Enter your name."}],
            )
        user = User(email=inv.email, full_name=data.full_name.strip()[:160], password_hash=hash_password(data.password))
        db_session.add(user)
        await db_session.flush()
    db_session.add(Membership(org_id=inv.org_id, user_id=user.id, role=inv.role))
    inv.accepted_at = clock.real_now()
    token_value, row = await sessions.create(
        db_session, user, org_id=inv.org_id, ip=client_ip(request), user_agent=None
    )
    await db_session.commit()
    await auditlog.record(
        inv.org_id,
        auditlog.Entry(
            action="invitation.accepted",
            summary=f"{user.full_name} accepted the invitation and joined as {labels.role_label(inv.role)}.",
            actor_user_id=user.id,
            actor_label=user.full_name,
            target_type="invitation",
            target_id=inv.id,
            target_label=inv.email,
            ip=client_ip(request),
        ),
    )
    return Response(await build_me(db_session, user, row), cookies=_session_cookies(token_value))


@get("/roles")
async def roles(ctx: Ctx) -> list[RoleInfo]:
    ctx.require("members:read")
    return [
        RoleInfo(
            role=r.value,
            label=labels.role_label(r.value),
            description=labels.ROLE_DESCRIPTIONS[r.value],
            permissions=sorted(ROLE_PERMISSIONS[r]),
        )
        for r in Role
    ]


@get("/meta")
async def meta(request: Request[Any, Any, Any]) -> Meta:
    lang = request_language(request)
    from claimvoice.dialogue.stages import SCRIPT_ORDER, Stage

    stages = [*SCRIPT_ORDER, Stage.HANDOFF, Stage.ENDED]
    return Meta(
        product="ClaimVoice",
        version=__version__,
        languages=[Labeled(key="en", label="English"), Labeled(key="fr", label="Français")],
        loss_types=[
            LossTypeInfo(key=k, label=labels.pick(v, lang), line=LOSS_TYPE_LINE.get(k, "property"))
            for k, v in reference.LOSS_TYPES.items()
        ],
        regions=[
            RegionInfo(code=k, label=v.get(lang) or v["en"], country=v["country"], consent_rule=v["consent"])
            for k, v in reference.REGIONS.items()
        ],
        stages=[Labeled(key=s.value, label=labels.pick(STAGE_LABELS[s], lang)) for s in stages],
        routes=[Labeled(key=k, label=labels.pick(v, lang)) for k, v in reference.ROUTES.items()],
        roles=[Labeled(key=r.value, label=labels.role_label(r.value)) for r in Role],
        demo_scenarios=[Labeled(key=k, label=labels.pick(v, lang)) for k, v in reference.DEMO_SCENARIOS.items()],
    )


ROUTER = Router(
    path="/api/v1",
    route_handlers=[
        get_org,
        update_org,
        list_members,
        update_member,
        remove_member,
        list_invitations,
        invite,
        revoke_invitation,
        preview_invitation,
        accept_invitation,
        roles,
        meta,
    ],
)
