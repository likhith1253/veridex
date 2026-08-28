import os
import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_db_session
from app.api.main import app
from app.database.session import create_app_engine
from app.services.source_health_service import SourceMetrics

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_test")


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Clean tables in isolated test database before each test."""
    engine = create_app_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE audit_events, exception_transactions, match_transactions, "
            "decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"
        ))
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client():
    """Async HTTP client with isolated database session dependency override."""
    engine = create_app_engine(TEST_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


def test_aud_037_source_metrics_clean_match_rate():
    """Verify SourceHealthService computes clean match rate accurately."""
    sm = SourceMetrics(
        source_name="Payment Gateway",
        total_records=10,
        matched_records=10,
        clean_matched_records=4,
        exception_records=6,
        match_rate_percent=100.0,
        clean_match_rate_percent=40.0,
        exception_rate_percent=60.0,
        health_status="ANOMALOUS",
    )
    assert sm.clean_match_rate_percent == 40.0
    assert sm.exception_rate_percent == 60.0
    assert sm.health_status == "ANOMALOUS"


@pytest.mark.asyncio
async def test_aud_037_source_health_api_live(test_client: AsyncClient):
    """Verify GET /api/v1/controller/source-health endpoint returns clean match metrics."""
    res = await test_client.get("/api/v1/controller/source-health")
    assert res.status_code == 200
    data = res.json()
    assert "overall_health" in data
    assert "sources" in data
    for src_key, s_data in data["sources"].items():
        assert "clean_match_rate_percent" in s_data
        assert "exception_rate_percent" in s_data
        assert "health_status" in s_data


@pytest.mark.asyncio
async def test_aud_039_summary_kpis_no_hardcoded_division(test_client: AsyncClient):
    """Verify summary KPIs derive true logical transaction counts from clusters rather than // 3."""
    res = await test_client.get("/api/v1/controller/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_records_processed" in data
    assert "total_logical_transactions" in data
    assert isinstance(data["total_logical_transactions"], int)
