from sqlalchemy import func, select

from claimvoice.platform import db
from claimvoice.platform.models import Membership, Organization
from claimvoice.seed import run
from claimvoice.seed.plan import PERSONAS


async def test_seed_creates_larkspur_with_one_person_per_role_and_replaces_itself(migrated_db):
    await run()
    await run()
    async with db.sessionmaker()() as session:
        orgs = (await session.execute(select(Organization).where(Organization.is_sample.is_(True)))).scalars().all()
        org_id = orgs[0].id
        roles = (await session.execute(select(Membership.role).where(Membership.org_id == org_id))).scalars().all()
        count = (
            await session.execute(select(func.count()).select_from(Membership).where(Membership.org_id == org_id))
        ).scalar_one()
    await db.dispose()
    assert [o.name for o in orgs] == ["Larkspur Mutual"]
    assert sorted(roles) == sorted(p.role for p in PERSONAS)
    assert count == len(PERSONAS)
