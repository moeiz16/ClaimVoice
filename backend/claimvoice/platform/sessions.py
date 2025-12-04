"""Server-side sessions: an opaque cookie token, its HMAC stored, idle and absolute expiry on the real clock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.config import get_settings
from claimvoice.platform.models import Membership, Session, User
from claimvoice.platform.security import new_token, token_digest

SESSION_COOKIE = "cv_session"
CSRF_COOKIE = "cv_csrf"
CSRF_HEADER = "x-csrf-token"
_TOUCH_EVERY = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class Resolved:
    session: Session
    user: User
    expired: bool = False


def _idle() -> timedelta:
    return timedelta(minutes=get_settings().session_idle_minutes)


async def create(
    db: AsyncSession, user: User, *, org_id: str | None, ip: str | None, user_agent: str | None
) -> tuple[str, Session]:
    now = clock.real_now()
    token = new_token()
    if org_id is None:
        first = (
            await db.execute(
                select(Membership.org_id).where(Membership.user_id == user.id).order_by(Membership.created_at)
            )
        ).first()
        org_id = first[0] if first else None
    row = Session(
        token_hash=token_digest(token),
        user_id=user.id,
        active_org_id=org_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + _idle(),
        absolute_expires_at=now + timedelta(hours=get_settings().session_absolute_hours),
        ip=ip,
        user_agent=(user_agent or "")[:300] or None,
    )
    db.add(row)
    user.last_login_at = clock.now()
    await db.flush()
    return token, row


async def resolve(db: AsyncSession, token: str | None) -> Resolved | None:
    """The live session for a cookie token. Returns `expired=True` for a known but ended session (so the API can say
    `session_expired` rather than `not_authenticated`)."""
    if not token:
        return None
    row = (await db.execute(select(Session).where(Session.token_hash == token_digest(token)))).scalar_one_or_none()
    if row is None:
        return None
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    now = clock.real_now()
    if row.revoked_at is not None or now >= row.expires_at or now >= row.absolute_expires_at:
        return Resolved(row, user, expired=True)
    if now - row.last_seen_at >= _TOUCH_EVERY:
        row.last_seen_at = now
        row.expires_at = min(now + _idle(), row.absolute_expires_at)
        await db.commit()
    return Resolved(row, user)


async def refresh(db: AsyncSession, row: Session) -> Session:
    now = clock.real_now()
    row.last_seen_at = now
    row.expires_at = min(now + _idle(), row.absolute_expires_at)
    await db.commit()
    return row


async def revoke(db: AsyncSession, row: Session) -> None:
    row.revoked_at = clock.real_now()
    await db.commit()


async def revoke_others(db: AsyncSession, user_id: str, keep_session_id: str) -> None:
    await db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.id != keep_session_id, Session.revoked_at.is_(None))
        .values(revoked_at=clock.real_now())
    )
    await db.commit()
