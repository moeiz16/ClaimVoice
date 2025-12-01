from sqlalchemy import func, select

from claimvoice.platform import db
from claimvoice.platform.models import Membership, Organization
from claimvoice.seed import run
from claimvoice.seed.plan import PERSONAS


async def test_seed_creates_larkspur_with_one_person_per_role_and_is_idempotent(migrated_db):
    await run()
    await run()
    async with db.sessionmaker()() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        roles = (await session.execute(select(Membership.role))).scalars().all()
        count = (await session.execute(select(func.count()).select_from(Membership))).scalar_one()
    await db.dispose()
    assert [o.name for o in orgs] == ["Larkspur Mutual"]
    assert sorted(roles) == sorted(p.role for p in PERSONAS)
    assert count == len(PERSONAS)
