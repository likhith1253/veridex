"""
Regression and Acceptance Test Suite for Root-Cause Group G5 (AUD-044):
CASH FORECAST CORRECTNESS & EMPIRICAL SETTLEMENT PROJECTIONS.
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import create_app_engine
from app.database.models import Transaction as TransactionORM
from app.models.transaction import TransactionSource, TransactionStatus
from app.services.forecast_service import CashForecastService

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/sentinel_test")


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
async def db_session():
    """Create a test database session in isolated test DB."""
    engine = create_app_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session_maker() as session:
        yield session
    await engine.dispose()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_aud_044_empirical_daily_average_and_liquidity_curve(db_session: AsyncSession):
    """AUD-044: Verify daily average uses distinct historical dates and empirical liquidity curve."""
    # Seed 5 distinct transaction dates
    base_date = datetime(2023, 12, 1, 10, 0, 0)
    daily_values = [100000.0, 200000.0, 150000.0, 300000.0, 250000.0]  # Average = 200,000.0

    for i, val in enumerate(daily_values):
        dt = base_date + timedelta(days=i * 2)  # spread across 10 calendar days
        txn = TransactionORM(
            id=f"tx_fc_{i}",
            domain_transaction_id=f"TX_FC_{i}",
            source=TransactionSource.GATEWAY.value,
            amount=Decimal(str(val)),
            currency="INR",
            timestamp=dt,
            status=TransactionStatus.COMPLETED.value,
            created_at=dt,
        )
        db_session.add(txn)

    await db_session.commit()

    service = CashForecastService(db_session)
    report = await service.generate_7day_forecast()

    assert report.historical_data_sufficient is True
    assert report.distinct_historical_days == 5
    assert report.historical_daily_avg_inr == 200000.0
    assert report.daily_volatility_inr > 0.0
    assert len(report.forecast_days) == 7

    # Verify 7-day total equals sum of daily projections
    calc_sum = round(sum(d["forecast_amount_inr"] for d in report.forecast_days), 2)
    assert report.seven_day_forecast_total_inr == calc_sum

    # Verify confidence intervals are consistent: low <= forecast <= high
    for d in report.forecast_days:
        assert d["confidence_interval_low"] <= d["forecast_amount_inr"]
        assert d["forecast_amount_inr"] <= d["confidence_interval_high"]


@pytest.mark.asyncio
async def test_aud_044_empty_database_edge_case(db_session: AsyncSession):
    """AUD-044: Empty database returns zero forecast with insufficient data flag."""
    service = CashForecastService(db_session)
    report = await service.generate_7day_forecast()

    assert report.historical_data_sufficient is False
    assert report.distinct_historical_days == 0
    assert report.historical_daily_avg_inr == 0.0
    assert report.seven_day_forecast_total_inr == 0.0
    assert report.forecast_days == []
    assert "Insufficient Historical Data" in report.methodology


@pytest.mark.asyncio
async def test_aud_044_single_day_history_edge_case(db_session: AsyncSession):
    """AUD-044: Single-day history sets historical_data_sufficient=False and uses baseline estimate."""
    dt = datetime(2023, 12, 15, 12, 0, 0)
    txn = TransactionORM(
        id="tx_single",
        domain_transaction_id="TX_SINGLE",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("75000.00"),
        currency="INR",
        timestamp=dt,
        status=TransactionStatus.COMPLETED.value,
        created_at=dt,
    )
    db_session.add(txn)
    await db_session.commit()

    service = CashForecastService(db_session)
    report = await service.generate_7day_forecast()

    assert report.historical_data_sufficient is False
    assert report.distinct_historical_days == 1
    assert report.historical_daily_avg_inr == 75000.0
    assert report.seven_day_forecast_total_inr == 525000.0  # 75000 * 7
    assert len(report.forecast_days) == 7
    assert "Single-Day Baseline Estimate" in report.methodology
