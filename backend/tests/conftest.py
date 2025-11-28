"""Test settings: a throwaway SQLite file per session, real time unless a test installs the demo clock."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

_TMP = Path(os.environ.get("PYTEST_TMPDIR", "/tmp")) / f"claimvoice-test-{os.getpid()}"
_TMP.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ["DATA_DIR"] = str(_TMP)
os.environ["CLAIMVOICE_DEMO_TODAY"] = "off"
os.environ["LLM_FAKE"] = "true"

from claimvoice import clock  # noqa: E402
from claimvoice.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _real_clock() -> Iterator[None]:
    clock.uninstall()
    yield
    clock.uninstall()


@pytest.fixture(scope="session")
def migrated_db() -> str:
    from claimvoice.cli import _alembic_upgrade

    get_settings.cache_clear()
    db_file = Path(get_settings().database_url.split("///", 1)[1])
    db_file.unlink(missing_ok=True)
    _alembic_upgrade()
    return str(db_file)


@pytest.fixture
async def client(migrated_db: str) -> AsyncIterator[object]:
    from litestar.testing import AsyncTestClient

    from claimvoice.api.app import create_app
    from claimvoice.platform import db

    async with AsyncTestClient(app=create_app()) as c:
        yield c
    await db.dispose()
