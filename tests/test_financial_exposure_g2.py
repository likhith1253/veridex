import os
from datetime import datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import create_app_engine
from app.database.models import (
    Decision as DecisionORM,
    Exception as ExceptionORM,
    ExceptionTransaction as ExceptionTransactionORM,
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
)
from app.models.decision_result import DecisionAction
from app.models.exception_record import ExceptionCategory
from app.models.transaction import TransactionSource, TransactionStatus
from app.services.cash_position import CashPositionService
from app.services.exposure_service import FinancialExposureService
from app.services.fee_tax_service import FeeTaxService
from app.services.finance_controller import FinanceController
from app.services.finance_qa import FinanceQAService
from app.services.settlement_accounting_service import SettlementAccountingService

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_test")


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
async def test_case_a_populated_exposure(db_session: AsyncSession):
    """Case A: When exception has explicitly populated exposure, it must be respected."""
    run = ReconciliationRunORM(
        id="run_g2_a",
        run_id="run_g2_a",
        status="completed",
        created_at=_now(),
        started_at=_now(),
        completed_at=_now(),
        gateway_count=1,
        ledger_count=1,
        bank_count=1,
        match_count=0,
        exception_count=1,
    )
    db_session.add(run)

    txn = TransactionORM(
        id="txn_g2_a_1",
        domain_transaction_id="TXN_A1",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("50000.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    db_session.add(txn)
    await db_session.flush()

    # Populated exposure of 25000 (e.g. partial loss assessed by investigator)
    exc = ExceptionORM(
        id="exc_g2_a_1",
        run_id="run_g2_a",
        transaction_id="txn_g2_a_1",
        exception_category=ExceptionCategory.PARTIAL_REFUND.value,
        status="open",
        confidence=Decimal("0.90"),
        financial_exposure=Decimal("25000.00"),
        expected_cost=Decimal("25000.00"),
        explanation="Explicit 25k partial exposure",
        resolved=False,
        created_at=_now(),
    )
    db_session.add(exc)
    await db_session.commit()

    service = FinancialExposureService(db_session)
    exp = await service.calculate_exposure("run_g2_a")

    assert exp.unresolved_value == Decimal("25000.00")
    assert exp.category_breakdown.get(ExceptionCategory.PARTIAL_REFUND.value) == "25000.00"


@pytest.mark.asyncio
async def test_case_b_missing_exposure_transaction_fallback(db_session: AsyncSession):
    """Case B: When exception has financial_exposure=0, it MUST fall back to transaction amount."""
    run = ReconciliationRunORM(
        id="run_g2_b",
        run_id="run_g2_b",
        status="completed",
        created_at=_now(),
        started_at=_now(),
        completed_at=_now(),
        gateway_count=1,
        ledger_count=1,
        bank_count=1,
        match_count=0,
        exception_count=1,
    )
    db_session.add(run)

    txn = TransactionORM(
        id="txn_g2_b_1",
        domain_transaction_id="TXN_B1",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("158468.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    db_session.add(txn)
    await db_session.flush()

    # Missing / unpopulated exposure = 0
    exc = ExceptionORM(
        id="exc_g2_b_1",
        run_id="run_g2_b",
        transaction_id="txn_g2_b_1",
        exception_category="unexplained",
        status="open",
        confidence=Decimal("0.50"),
        financial_exposure=Decimal("0.00"),
        expected_cost=Decimal("0.00"),
        explanation="Unexplained exception with 0 populated exposure",
        resolved=False,
        created_at=_now(),
    )
    db_session.add(exc)
    await db_session.commit()

    service = FinancialExposureService(db_session)
    exp = await service.calculate_exposure("run_g2_b")

    # MUST NOT be 0; must fall back to linked txn amount
    assert exp.unresolved_value == Decimal("158468.00")
    assert exp.high_risk_value == Decimal("158468.00")
    assert exp.unexplained_exposure == Decimal("158468.00")

    # Also verify CashPosition reflects this risk floor
    cash_service = CashPositionService(db_session)
    cash = await cash_service.get_cash_position("run_g2_b")
    assert cash.unreconciled_amount >= Decimal("158468.00")
    assert cash.at_risk_amount >= Decimal("158468.00")


@pytest.mark.asyncio
async def test_case_c_no_double_counting_across_joins(db_session: AsyncSession):
    """Case C: Verify exposure is not duplicated across multiple junction entries."""
    run = ReconciliationRunORM(
        id="run_g2_c",
        run_id="run_g2_c",
        status="completed",
        created_at=_now(),
        started_at=_now(),
        completed_at=_now(),
        gateway_count=2,
        ledger_count=2,
        bank_count=2,
        match_count=1,
        exception_count=1,
    )
    db_session.add(run)

    txn1 = TransactionORM(
        id="txn_g2_c_1",
        domain_transaction_id="TXN_C1",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("100000.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    txn2 = TransactionORM(
        id="txn_g2_c_2",
        domain_transaction_id="TXN_C2",
        source=TransactionSource.LEDGER.value,
        amount=Decimal("100000.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    db_session.add_all([txn1, txn2])
    await db_session.flush()

    exc = ExceptionORM(
        id="exc_g2_c_1",
        run_id="run_g2_c",
        transaction_id="txn_g2_c_1",
        exception_category="fee_mismatch",
        status="open",
        confidence=Decimal("0.80"),
        financial_exposure=Decimal("0.00"),
        expected_cost=Decimal("0.00"),
        explanation="Multi-leg mismatch exception",
        resolved=False,
        created_at=_now(),
    )
    db_session.add(exc)
    await db_session.flush()

    # Link both transactions to the single exception via junction
    et1 = ExceptionTransactionORM(exception_id="exc_g2_c_1", transaction_id="txn_g2_c_1")
    et2 = ExceptionTransactionORM(exception_id="exc_g2_c_1", transaction_id="txn_g2_c_2")
    db_session.add_all([et1, et2])
    await db_session.commit()

    service = FinancialExposureService(db_session)
    exp = await service.calculate_exposure("run_g2_c")

    # Exposure for the single logical event must be 100,000, not 200,000
    assert exp.unresolved_value == Decimal("100000.00")
    assert exp.fee_tax_mismatch_exposure == Decimal("100000.00")


@pytest.mark.asyncio
async def test_case_d_category_totals_consistency(db_session: AsyncSession):
    """Case D: Category totals sum consistently with underlying items."""
    run = ReconciliationRunORM(
        id="run_g2_d",
        run_id="run_g2_d",
        status="completed",
        created_at=_now(),
        started_at=_now(),
        completed_at=_now(),
        gateway_count=3,
        ledger_count=3,
        bank_count=3,
        match_count=0,
        exception_count=3,
    )
    db_session.add(run)

    txns = [
        TransactionORM(id="txn_d_1", domain_transaction_id="D1", source="gateway", amount=Decimal("1000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_d_2", domain_transaction_id="D2", source="gateway", amount=Decimal("2000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_d_3", domain_transaction_id="D3", source="gateway", amount=Decimal("3000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
    ]
    db_session.add_all(txns)
    await db_session.flush()

    excs = [
        ExceptionORM(id="exc_d_1", run_id="run_g2_d", transaction_id="txn_d_1", exception_category="duplicate_entry", status="open", confidence=Decimal("1.0"), financial_exposure=Decimal("1000.00"), expected_cost=Decimal("1000.00"), explanation="dup", resolved=False, created_at=_now()),
        ExceptionORM(id="exc_d_2", run_id="run_g2_d", transaction_id="txn_d_2", exception_category="delayed_settlement", status="open", confidence=Decimal("1.0"), financial_exposure=Decimal("2000.00"), expected_cost=Decimal("2000.00"), explanation="delayed", resolved=False, created_at=_now()),
        ExceptionORM(id="exc_d_3", run_id="run_g2_d", transaction_id="txn_d_3", exception_category="unexplained", status="open", confidence=Decimal("1.0"), financial_exposure=Decimal("3000.00"), expected_cost=Decimal("3000.00"), explanation="unexp", resolved=False, created_at=_now()),
    ]
    db_session.add_all(excs)
    await db_session.commit()

    service = FinancialExposureService(db_session)
    exp = await service.calculate_exposure("run_g2_d")

    assert exp.duplicate_exposure == Decimal("1000.00")
    assert exp.delayed_settlement_exposure == Decimal("2000.00")
    assert exp.unexplained_exposure == Decimal("3000.00")
    assert exp.unresolved_value == Decimal("6000.00")
    assert sum(Decimal(v) for v in exp.category_breakdown.values()) == exp.unresolved_value


@pytest.mark.asyncio
async def test_case_e_asymmetric_feeds_no_max_masking(db_session: AsyncSession):
    """Case E: Gateway vs Ledger asymmetry must not be masked by max()."""
    txns = [
        TransactionORM(id="txn_e_gw", domain_transaction_id="E_GW", source="gateway", amount=Decimal("10000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_e_ld1", domain_transaction_id="E_LD1", source="ledger", amount=Decimal("10000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_e_ld2", domain_transaction_id="E_LD2", source="ledger", amount=Decimal("5000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_e_bk", domain_transaction_id="E_BK", source="bank", amount=Decimal("10000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
    ]
    db_session.add_all(txns)
    await db_session.commit()

    cash_service = CashPositionService(db_session)
    cash = await cash_service.get_cash_position()

    # Authoritative gross is Gateway gross (10,000), not max(GW=10k, LD=15k)=15,000
    assert cash.expected_gross == Decimal("10000.00")
    assert cash.breakdown_by_source["gateway"] == Decimal("10000.00")
    assert cash.breakdown_by_source["ledger"] == Decimal("15000.00")
    assert cash.breakdown_by_source["bank"] == Decimal("10000.00")


@pytest.mark.asyncio
async def test_case_f_empty_dataset_safe(db_session: AsyncSession):
    """Case F: Financial calculations must execute safely on an empty database."""
    # Wipe DB for empty check
    await db_session.execute(text("TRUNCATE TABLE audit_events, exception_transactions, match_transactions, decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"))
    await db_session.commit()

    exp_service = FinancialExposureService(db_session)
    exp = await exp_service.calculate_exposure()
    assert exp.total_processed_value == Decimal("0.00")
    assert exp.matched_value == Decimal("0.00")
    assert exp.unresolved_value == Decimal("0.00")

    cash_service = CashPositionService(db_session)
    cash = await cash_service.get_cash_position()
    assert cash.expected_gross == Decimal("0.00")
    assert cash.unreconciled_amount == Decimal("0.00")

    settlement_service = SettlementAccountingService(db_session)
    settlement = await settlement_service.calculate_settlement_accounting()
    assert settlement.gross_gateway_volume == "0.00"
    assert settlement.settlement_reconciliation_status == "RECONCILED"

    fee_tax_service = FeeTaxService(db_session)
    fee_tax = await fee_tax_service.reconcile_fees_and_taxes()
    assert fee_tax.total_gross_volume == "0.00"
    assert fee_tax.discrepant_transactions_count == 0


@pytest.mark.asyncio
async def test_case_g_all_sources_summed_in_total_processed(db_session: AsyncSession):
    """AUD-010 / AUD-035: Total processed value must sum Gateway + Ledger + Bank."""
    txns = [
        TransactionORM(id="txn_g_gw", domain_transaction_id="G_GW", source="gateway", amount=Decimal("100.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_g_ld", domain_transaction_id="G_LD", source="ledger", amount=Decimal("100.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="txn_g_bk", domain_transaction_id="G_BK", source="bank", amount=Decimal("100.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
    ]
    db_session.add_all(txns)
    await db_session.commit()

    exp_service = FinancialExposureService(db_session)
    exp = await exp_service.calculate_exposure()

    # MUST be 300.00 (all 3 feeds), NEVER 200.00 (GW+LD only)
    assert exp.total_processed_value == Decimal("300.00")
