"""`make seed`: Larkspur Mutual and its people (idempotent). Policies, historical calls and claims, the live demo
lines, the urgent-safety call, the SIU-flagged claim and the Calgary hail surge are added on top of this (seed plan in
docs/DATA.md and `seed.plan`)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice.platform.models import Membership, Organization, User
from claimvoice.platform.security import hash_password
from claimvoice.seed.plan import DEMO_PASSWORD, ORG, PERSONAS


async def seed_org(session: AsyncSession) -> Organization:
    org = (await session.execute(select(Organization).where(Organization.slug == ORG["slug"]))).scalar_one_or_none()
    if org is None:
        org = Organization(
            name=ORG["name"],
            slug=ORG["slug"],
            timezone=ORG["timezone"],
            regions=list(ORG["regions"]),
            languages=list(ORG["languages"]),
            is_sample=True,
            settings={"privacyOfficer": {"name": "Priya Sandhu", "email": "privacy@larkspur.example"}},
        )
        session.add(org)
        await session.flush()
    password_hash: str | None = None
    for p in PERSONAS:
        user = (await session.execute(select(User).where(User.email == p.email))).scalar_one_or_none()
        if user is None:
            password_hash = password_hash or hash_password(DEMO_PASSWORD)
            user = User(
                email=p.email,
                full_name=p.full_name,
                password_hash=password_hash,
                preferred_language=p.language,
                avatar_color=p.color,
            )
            session.add(user)
            await session.flush()
        member = (
            await session.execute(select(Membership).where(Membership.org_id == org.id, Membership.user_id == user.id))
        ).scalar_one_or_none()
        if member is None:
            session.add(Membership(org_id=org.id, user_id=user.id, role=p.role, title=p.title))
    await session.commit()
    return org


async def run() -> dict[str, int]:
    from claimvoice.platform import db

    async with db.sessionmaker()() as session:
        await seed_org(session)
        users = len((await session.execute(select(User))).scalars().all())
    return {"organizations": 1, "users": users}
