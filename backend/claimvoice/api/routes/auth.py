"""§1.2 auth and session: cookie + CSRF, demo sign-in by role."""

from __future__ import annotations

import re
from typing import Any

from litestar import Request, Response, Router, get, post
from litestar.datastructures import Cookie
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.api import labels
from claimvoice.api.context import Ctx, client_ip, resolve_user
from claimvoice.config import get_settings
from claimvoice.platform import auditlog, sessions
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.models import Membership, Organization, Session, User
from claimvoice.platform.permissions import Role, permissions_for
from claimvoice.platform.security import hash_password, new_token, verify_password
from claimvoice.schemas.auth import (
    DemoSignInIn,
    LoginIn,
    Me,
    MembershipInfo,
    Org,
    OrgSummary,
    PasswordChangeIn,
    RefreshOut,
    SessionInfo,
    SessionState,
    SignupIn,
    SwitchOrgIn,
)
from claimvoice.schemas.auth import User as UserOut
from claimvoice.schemas.base import ClockInfo

COMMON_PASSWORDS = {
    "password1234",
    "passwordpassword",
    "123456789012",
    "qwertyuiopas",
    "letmein12345",
    "iloveyou1234",
    "welcome12345",
    "administrator",
    "changeme1234",
}
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")


def clock_info(org: Organization | None = None) -> ClockInfo:
    tz = org.timezone if org else get_settings().claimvoice_demo_tz
    return ClockInfo(today=clock.today(tz).isoformat(), now=clock.now(), demo=clock.is_shifted(), timezone=tz)


def org_out(org: Organization) -> Org:
    return Org(
        id=org.id,
        name=org.name,
        slug=org.slug,
        timezone=org.timezone,
        regions=list(org.regions or []),
        languages=list(org.languages or ["en"]),
        is_sample=org.is_sample,
        created_at=org.created_at,
    )


def user_out(user: User) -> UserOut:
    lang = user.preferred_language if user.preferred_language in ("en", "fr") else "en"
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        preferred_language=labels.lit(lang),
        avatar_color=user.avatar_color,
        created_at=user.created_at,
    )


async def build_me(db: AsyncSession, user: User, session: Session) -> Me:
    rows = (
        await db.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.org_id)
            .where(Membership.user_id == user.id)
            .order_by(Organization.name)
        )
    ).all()
    active = next(((m, o) for m, o in rows if o.id == session.active_org_id), None)
    membership = None
    if active:
        m = active[0]
        membership = MembershipInfo(
            role=m.role,
            role_label=labels.role_label(m.role),
            title=m.title,
            permissions=sorted(permissions_for(m.role)),
        )
    return Me(
        user=user_out(user),
        active_org=org_out(active[1]) if active else None,
        membership=membership,
        orgs=[
            OrgSummary(
                id=o.id,
                name=o.name,
                slug=o.slug,
                role=m.role,
                role_label=labels.role_label(m.role),
                is_sample=o.is_sample,
            )
            for m, o in rows
        ],
        session=SessionInfo(expires_at=session.expires_at, absolute_expires_at=session.absolute_expires_at),
        clock=clock_info(active[1] if active else None),
    )


def _session_cookies(token: str | None, *, clear: bool = False) -> list[Cookie]:
    s = get_settings()
    max_age = 0 if clear else s.session_absolute_hours * 3600
    return [
        Cookie(
            key=sessions.SESSION_COOKIE,
            value="" if clear else (token or ""),
            httponly=True,
            samesite="lax",
            secure=s.cookie_secure,
            path="/",
            max_age=max_age,
        )
    ]


def _csrf_cookie(token: str) -> Cookie:
    s = get_settings()
    return Cookie(
        key=sessions.CSRF_COOKIE, value=token, httponly=False, samesite="lax", secure=s.cookie_secure, path="/"
    )


def password_problems(password: str, email: str) -> str | None:
    name = email.split("@", 1)[0].lower()
    if len(password) < 12:
        return "Use at least 12 characters."
    if password.lower() in COMMON_PASSWORDS or len(set(password)) < 5:
        return "That password is too common. Try a short phrase."
    if len(name) >= 3 and name in password.lower():
        return "Don't use your email name in the password."
    return None


async def _sign_in(
    request: Request[Any, Any, Any], db: AsyncSession, user: User, org_id: str | None = None
) -> Response[Me]:
    token, row = await sessions.create(db, user, org_id=org_id, ip=client_ip(request), user_agent=None)
    await db.commit()
    me = await build_me(db, user, row)
    if me.active_org is not None:
        await auditlog.record(
            me.active_org.id,
            auditlog.Entry(
                action="auth.login",
                summary=f"{user.full_name} signed in.",
                actor_user_id=user.id,
                actor_label=user.full_name,
                target_type="user",
                target_id=user.id,
                target_label=user.full_name,
                ip=client_ip(request),
            ),
        )
    return Response(me, cookies=_session_cookies(token))


@get("/csrf", status_code=204)
async def csrf(request: Request[Any, Any, Any]) -> Response[None]:
    token = request.cookies.get(sessions.CSRF_COOKIE) or new_token(24)
    return Response(None, status_code=204, cookies=[_csrf_cookie(token)])


@get("/session")
async def session_state(request: Request[Any, Any, Any], db_session: AsyncSession) -> SessionState:
    """Always 200, so public pages never see a 401."""
    resolved, _ = await resolve_user(request, db_session)
    if resolved is None:
        return SessionState(me=None, clock=clock_info())
    me = await build_me(db_session, resolved.user, resolved.session)
    return SessionState(me=me, clock=me.clock)


@post("/login", status_code=200)
async def login(request: Request[Any, Any, Any], db_session: AsyncSession, data: LoginIn) -> Response[Me]:
    email = data.email.strip().lower()
    limiter = request.app.state.limiter
    paused = limiter.login_paused(email)
    if paused:
        raise ProblemError(
            429,
            "rate_limited",
            "Too many attempts",
            "Sign-in is paused for this email for a few minutes.",
            headers={"Retry-After": str(paused)},
        )
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(user.password_hash, data.password):
        limiter.login_failed(email)
        if user is not None:
            org_id = (
                await db_session.execute(select(Membership.org_id).where(Membership.user_id == user.id).limit(1))
            ).scalar_one_or_none()
            if org_id:
                await auditlog.record(
                    org_id,
                    auditlog.Entry(
                        action="auth.login_failed",
                        summary=f"A sign-in for {user.full_name} failed.",
                        target_type="user",
                        target_id=user.id,
                        target_label=user.full_name,
                        ip=client_ip(request),
                    ),
                )
        raise ProblemError(401, "invalid_credentials", "Sign-in failed", "That email and password don't match.")
    limiter.login_ok(email)
    return await _sign_in(request, db_session, user)


@post("/demo", status_code=200)
async def demo(request: Request[Any, Any, Any], db_session: AsyncSession, data: DemoSignInIn) -> Response[Me]:
    from claimvoice.seed.plan import ORG, PERSONAS

    if get_settings().environment == "production":
        raise ProblemError(404, "not_found", "Not found")
    org = (
        await db_session.execute(
            select(Organization).where(Organization.slug == ORG["slug"], Organization.is_sample.is_(True))
        )
    ).scalar_one_or_none()
    persona = next((p for p in PERSONAS if p.role == data.role and p.demo), None)
    if org is None or persona is None:
        raise ProblemError(404, "not_found", "Not found", "The sample organisation isn't set up. Run make seed.")
    user = (await db_session.execute(select(User).where(User.email == persona.email))).scalar_one_or_none()
    if user is None:
        raise ProblemError(404, "not_found", "Not found", "The sample organisation isn't set up. Run make seed.")
    return await _sign_in(request, db_session, user, org.id)


@post("/signup", status_code=201)
async def signup(request: Request[Any, Any, Any], db_session: AsyncSession, data: SignupIn) -> Response[Me]:
    from claimvoice.settings.service import install_defaults

    email = data.email.strip().lower()
    errors = []
    if not _EMAIL.match(email):
        errors.append({"field": "email", "message": "Enter a valid email address."})
    if not data.full_name.strip():
        errors.append({"field": "fullName", "message": "Enter your name."})
    if not data.org_name.strip():
        errors.append({"field": "orgName", "message": "Enter your organisation's name."})
    if errors:
        raise ProblemError(
            422, "validation_error", "Validation failed", "One or more fields are invalid.", errors=errors
        )
    weak = password_problems(data.password, email)
    if weak:
        raise ProblemError(
            422, "weak_password", "Choose a stronger password", weak, errors=[{"field": "password", "message": weak}]
        )
    if (await db_session.execute(select(User.id).where(User.email == email))).first():
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            "One or more fields are invalid.",
            errors=[{"field": "email", "message": "An account already uses this email. Sign in instead."}],
        )
    base = re.sub(r"[^a-z0-9]+", "-", data.org_name.lower()).strip("-")[:60] or "org"
    slug, n = base, 1
    while (await db_session.execute(select(Organization.id).where(Organization.slug == slug))).first():
        n += 1
        slug = f"{base}-{n}"
    org = Organization(
        name=data.org_name.strip()[:160],
        slug=slug,
        timezone="America/Edmonton",
        regions=["CA-AB"],
        languages=["en", "fr"] if data.preferred_language == "fr" else ["en"],
        settings={},
    )
    user = User(
        email=email,
        full_name=data.full_name.strip()[:160],
        password_hash=hash_password(data.password),
        preferred_language=data.preferred_language,
    )
    db_session.add_all([org, user])
    await db_session.flush()
    db_session.add(Membership(org_id=org.id, user_id=user.id, role=Role.ADMIN.value, title="Administrator"))
    await install_defaults(db_session, org)
    await db_session.commit()
    response = await _sign_in(request, db_session, user, org.id)
    response.status_code = 201
    return response


@post("/logout", status_code=204)
async def logout(ctx: Ctx) -> Response[None]:
    await sessions.revoke(ctx.db, ctx.session)
    await ctx.audit("auth.logout", f"{ctx.user.full_name} signed out.", target_type="user", target_id=ctx.user.id)
    return Response(None, status_code=204, cookies=_session_cookies(None, clear=True))


@post("/refresh", status_code=200)
async def refresh(ctx: Ctx) -> RefreshOut:
    row = await sessions.refresh(ctx.db, ctx.session)
    return RefreshOut(expires_at=row.expires_at, absolute_expires_at=row.absolute_expires_at)


@get("/me")
async def me(ctx: Ctx) -> Me:
    return await build_me(ctx.db, ctx.user, ctx.session)


@post("/switch-org", status_code=200)
async def switch_org(request: Request[Any, Any, Any], db_session: AsyncSession, data: SwitchOrgIn) -> Me:
    resolved, expired = await resolve_user(request, db_session)
    if resolved is None:
        code = "session_expired" if expired else "not_authenticated"
        raise ProblemError(401, code, "Not signed in", "Please sign in.")
    member = (
        await db_session.execute(
            select(Membership).where(Membership.user_id == resolved.user.id, Membership.org_id == data.org_id)
        )
    ).scalar_one_or_none()
    if member is None:
        raise ProblemError(404, "not_found", "Not found")
    resolved.session.active_org_id = data.org_id
    await db_session.commit()
    return await build_me(db_session, resolved.user, resolved.session)


@post("/password", status_code=204)
async def change_password(ctx: Ctx, data: PasswordChangeIn) -> Response[None]:
    if not verify_password(ctx.user.password_hash, data.current_password):
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            "One or more fields are invalid.",
            errors=[{"field": "currentPassword", "message": "That isn't your current password."}],
        )
    weak = password_problems(data.new_password, ctx.user.email)
    if weak:
        raise ProblemError(
            422, "weak_password", "Choose a stronger password", weak, errors=[{"field": "newPassword", "message": weak}]
        )
    ctx.user.password_hash = hash_password(data.new_password)
    await ctx.db.commit()
    await sessions.revoke_others(ctx.db, ctx.user.id, ctx.session.id)
    await ctx.audit(
        "auth.password_changed",
        f"{ctx.user.full_name} changed their password; other sessions were ended.",
        target_type="user",
        target_id=ctx.user.id,
    )
    return Response(None, status_code=204)


async def count_admins(db: AsyncSession, org_id: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(Membership)
                .where(Membership.org_id == org_id, Membership.role == "admin")
            )
        ).scalar_one()
    )


ROUTER = Router(
    path="/api/v1/auth",
    route_handlers=[csrf, session_state, login, demo, signup, logout, refresh, me, switch_org, change_password],
)
