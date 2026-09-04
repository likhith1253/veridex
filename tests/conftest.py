"""
Test database isolation.

mistakes.txt (2026) records that running pytest previously wiped the
development database because tests used app.database.session's DATABASE_URL
directly with no isolation. This module forces a separate, disposable test
database BEFORE any test module imports app.database.session, and refuses to
run at all if it cannot establish that separation.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

# app.database.session also calls load_dotenv(), but that happens too late for
# us here — we must read the real DATABASE_URL before that module is imported.
load_dotenv()

_DEV_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://user:password@localhost/sentinel"
)


def _derive_test_url(dev_url: str) -> str:
    """postgresql+asyncpg://user:pass@host/sentinel -> .../sentinel_test"""
    base, _, dbname = dev_url.rpartition("/")
    if not dbname or not base:
        raise RuntimeError(f"Cannot parse DATABASE_URL to derive a test database: {dev_url!r}")
    if dbname.endswith("_test"):
        return dev_url  # already pointed at a test DB explicitly
    return f"{base}/{dbname}_test"


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _derive_test_url(_DEV_URL)

if TEST_DATABASE_URL == _DEV_URL:
    raise RuntimeError(
        "Refusing to run tests: TEST_DATABASE_URL resolves to the same database as "
        "DATABASE_URL. Set TEST_DATABASE_URL to a disposable database explicitly."
    )

# Must happen before any test module (transitively) imports app.database.session,
# since that module reads DATABASE_URL once at import time.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Some test modules read TEST_DATABASE_URL directly with their own hardcoded
# fallback DSN (different credentials entirely) instead of DATABASE_URL — set
# it explicitly so every test module ends up pointed at the same database.
os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL
if "app.database.session" in sys.modules:
    raise RuntimeError(
        "app.database.session was imported before tests/conftest.py could redirect "
        "DATABASE_URL to the test database. Re-order imports so conftest loads first."
    )


def _ensure_test_database_exists() -> None:
    import asyncpg

    async def _create_if_missing():
        base, _, dbname = TEST_DATABASE_URL.rpartition("/")
        admin_url = base.replace("postgresql+asyncpg://", "postgresql://") + "/postgres"
        conn = await asyncpg.connect(admin_url)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbname)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{dbname}"')
        finally:
            await conn.close()

    asyncio.run(_create_if_missing())


def _create_schema() -> None:
    from app.database.session import create_app_engine
    from app.database.models.base import Base

    async def _create():
        from sqlalchemy import text

        engine = create_app_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # The test DB's CREATE DATABASE clones template1, which in this
            # environment already carries a full schema owned by a different
            # role ("sentinel") than the one tests connect as ("postgres").
            # Without this, TRUNCATE (used by test fixtures to reset state
            # between tests) fails with "permission denied" on those tables.
            await conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO CURRENT_USER"))
        await engine.dispose()

    asyncio.run(_create())


_ensure_test_database_exists()
_create_schema()
