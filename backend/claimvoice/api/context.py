"""Request context: the signed-in person, their active organisation and permissions, the viewer's language, and
helpers every route uses (permission checks, tenant-scoped lookups, audit, paging)."""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from litestar import Request
from litestar.di import Provide
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice.platform import auditlog, db, sessions
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.models import Membership, Organization, Session, User
from claimvoice.platform.permissions import permissions_for
from claimvoice.schemas.base import Page

T = TypeVar("T")
R = TypeVar("R")


def client_ip(request: Request[Any, Any, Any]) -> str | None:
    client = request.scope.get("client")
    return client[0] if client else None


def request_language(request: Request[Any, Any, Any], preferred: str | None = None) -> str:
    header = (request.headers.get("accept-language") or "").strip().lower()
    if header.startswith("fr"):
        return "fr"
    if header.startswith("en"):
        return "en"
    return preferred if preferred in ("en", "fr") else "en"


def forbidden() -> ProblemError:
    return ProblemError(403, "forbidden", "Not allowed", "Your role does not include this action.")


def not_found() -> ProblemError:
    return ProblemError(404, "not_found", "Not found")


@dataclass
class Ctx:
    request: Request[Any, Any, Any]
    db: AsyncSession
    user: User
    session: Session
    org: Organization
    membership: Membership
    perms: frozenset[str]
    lang: str

    @property
    def org_id(self) -> str:
        return self.org.id

    @property
    def ip(self) -> str | None:
        return client_ip(self.request)

    @property
    def siu(self) -> bool:
        return "siu:read" in self.perms

    def can(self, permission: str) -> bool:
        return permission in self.perms

    def require(self, *permissions: str) -> None:
        """All of the given permissions are needed."""
        if not all(p in self.perms for p in permissions):
            raise forbidden()

    def require_any(self, *permissions: str) -> None:
        if not any(p in self.perms for p in permissions):
            raise forbidden()

    async def get(self, model: type[T], ident: str) -> T:
        """A tenant-owned row by id, or 404 (never 403) when it is unknown or belongs to another organisation."""
        row = await self.db.get(model, ident)
        if row is None or getattr(row, "org_id", None) != self.org.id:
            raise not_found()
        return row

    async def audit(
        self,
        action: str,
        summary: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        target_label: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await auditlog.record(
            self.org.id,
            auditlog.Entry(
                action=action,
                summary=summary,
                actor_user_id=self.user.id,
                actor_label=self.user.full_name,
                target_type=target_type,
                target_id=target_id,
                target_label=target_label,
                details=details or {},
                ip=self.ip,
            ),
        )


async def provide_db() -> AsyncIterator[AsyncSession]:
    async for session in db.session_scope():
        yield session


async def resolve_user(request: Request[Any, Any, Any], session: AsyncSession) -> tuple[sessions.Resolved | None, bool]:
    resolved = await sessions.resolve(session, request.cookies.get(sessions.SESSION_COOKIE))
    if resolved is None:
        return None, False
    return (None, True) if resolved.expired else (resolved, False)


async def provide_ctx(request: Request[Any, Any, Any], db_session: AsyncSession) -> Ctx:
    resolved, expired = await resolve_user(request, db_session)
    if resolved is None:
        if expired:
            raise ProblemError(401, "session_expired", "Session ended", "Please sign in again.")
        raise ProblemError(401, "not_authenticated", "Not signed in", "Please sign in.")
    org_id = resolved.session.active_org_id
    membership = None
    org = None
    if org_id:
        membership = (
            await db_session.execute(
                select(Membership).where(Membership.org_id == org_id, Membership.user_id == resolved.user.id)
            )
        ).scalar_one_or_none()
        org = await db_session.get(Organization, org_id) if membership else None
    if membership is None or org is None:
        raise ProblemError(403, "no_active_org", "No organisation", "Choose or create an organisation first.")
    perms = permissions_for(membership.role)
    request.scope.setdefault("state", {})["perms"] = perms
    return Ctx(
        request=request,
        db=db_session,
        user=resolved.user,
        session=resolved.session,
        org=org,
        membership=membership,
        perms=perms,
        lang=request_language(request, resolved.user.preferred_language),
    )


DEPENDENCIES: dict[str, Provide] = {
    "db_session": Provide(provide_db),
    "ctx": Provide(provide_ctx),
}


def page_args(page: int | None, page_size: int | None) -> tuple[int, int]:
    p = max(1, page or 1)
    size = min(100, max(1, page_size or 25))
    return p, size


async def paged(
    session: AsyncSession,
    stmt: Select[Any],
    page: int | None,
    page_size: int | None,
    mapper: Callable[[Sequence[Any]], Any],
) -> Page[Any]:
    """Run a select with paging. `mapper` turns the page's rows into wire items (it may be async)."""
    p, size = page_args(page, page_size)
    total = (await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await session.execute(stmt.limit(size).offset((p - 1) * size))).scalars().all()
    items = mapper(rows)
    if hasattr(items, "__await__"):
        items = await items
    return Page(items=list(items), page=p, page_size=size, total=total, total_pages=max(1, math.ceil(total / size)))
