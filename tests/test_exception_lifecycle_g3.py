"""
Regression and Acceptance Test Suite for Root-Cause Group G3:
EXCEPTION LIFECYCLE & CLASSIFICATION (AUD-016, AUD-017, AUD-045).

Covers:
- AUD-016: Truthful exception categorization (no 'unknown' categories) and grounded exposure.
- AUD-017: Atomic lifecycle state transitions (status='resolved' <-> resolved=True <-> resolved_at IS NOT NULL).
- AUD-045: Exception queue retrieval, multi-category triage, and recommended actions.
"""

import os
from datetime import datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import create_app_engine
from app.database.models import (
    AuditEvent as AuditEventORM,
    Decision as DecisionORM,
    Exception as ExceptionORM,
    ExceptionTransaction as ExceptionTransactionORM,
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
)
from app.database.models.exception import ExceptionCategory as ORMExceptionCategory
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory as DomainExceptionCategory, ExceptionRecord
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.exception_management_service import ExceptionManagementService
from app.services.human_decision_service import HumanAction, HumanDecisionService
from app.services.reconciliation import ReconciliationService

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
async def test_aud_016_truthful_exception_categories_and_exposure(db_session: AsyncSession):
    """AUD-016: Exceptions must have standard valid categories and grounded exposure, never 'unknown'."""
    run = ReconciliationRunORM(
        id="run_g3_016",
        run_id="run_g3_016",
        status="completed",
        created_at=_now(),
        started_at=_now(),
        completed_at=_now(),
        gateway_count=2,
        ledger_count=2,
        bank_count=2,
        match_count=0,
        exception_count=2,
    )
    db_session.add(run)

    txn1 = TransactionORM(
        id="txn_g3_1",
        domain_transaction_id="TXN_G3_1",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("150000.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    txn2 = TransactionORM(
        id="txn_g3_2",
        domain_transaction_id="TXN_G3_2",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("250000.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    db_session.add_all([txn1, txn2])
    await db_session.flush()

    exc1 = ExceptionORM(
        id="exc_g3_1",
        run_id="run_g3_016",
        transaction_id="txn_g3_1",
        exception_category=ORMExceptionCategory.DUPLICATE_RECORD.value,
        status="open",
        confidence=Decimal("0.95"),
        financial_exposure=Decimal("150000.00"),
        expected_cost=Decimal("7500.00"),
        explanation="Duplicate gateway entry detected",
        recommended_action="flag_duplicate",
        resolved=False,
        created_at=_now(),
    )
    exc2 = ExceptionORM(
        id="exc_g3_2",
        run_id="run_g3_016",
        transaction_id="txn_g3_2",
        exception_category=ORMExceptionCategory.AMOUNT_MISMATCH.value,
        status="open",
        confidence=Decimal("0.90"),
        financial_exposure=Decimal("250000.00"),
        expected_cost=Decimal("25000.00"),
        explanation="Fee calculation variance between gateway and bank",
        recommended_action="request_credit_note",
        resolved=False,
        created_at=_now(),
    )
    db_session.add_all([exc1, exc2])
    await db_session.commit()

    service = ExceptionManagementService(db_session)
    items, count = await service.list_exceptions(run_id="run_g3_016")

    assert count == 2
    categories = [it["category"] for it in items]
    assert "unknown" not in categories
    assert ORMExceptionCategory.AMOUNT_MISMATCH.value in categories
    assert ORMExceptionCategory.DUPLICATE_RECORD.value in categories

    for it in items:
        assert it["financial_exposure_inr"] > 0
        assert it["expected_cost_inr"] > 0
        assert it["recommended_action"] in ("flag_duplicate", "request_credit_note")


@pytest.mark.asyncio
async def test_aud_017_atomic_lifecycle_state_consistency(db_session: AsyncSession):
    """AUD-017: status='resolved' <-> resolved=True <-> resolved_at IS NOT NULL must remain in lockstep."""
    run = ReconciliationRunORM(
        id="run_g3_017",
        run_id="run_g3_017",
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
        id="txn_g3_17",
        domain_transaction_id="TXN_17",
        source=TransactionSource.GATEWAY.value,
        amount=Decimal("85000.00"),
        currency="INR",
        timestamp=_now(),
        status=TransactionStatus.COMPLETED.value,
        created_at=_now(),
    )
    db_session.add(txn)
    await db_session.flush()

    exc = ExceptionORM(
        id="exc_g3_17",
        run_id="run_g3_017",
        transaction_id="txn_g3_17",
        exception_category=ORMExceptionCategory.UNEXPLAINED.value,
        status="open",
        confidence=Decimal("0.50"),
        financial_exposure=Decimal("85000.00"),
        expected_cost=Decimal("42500.00"),
        explanation="Unexplained exception pending controller investigation",
        resolved=False,
        resolved_at=None,
        created_at=_now(),
    )
    db_session.add(exc)
    await db_session.commit()

    human_service = HumanDecisionService(db_session)

    # 1. Action: RESOLVE
    res = await human_service.apply_decision(
        exception_id="exc_g3_17",
        action=HumanAction.RESOLVE,
        actor="lead_auditor",
        reason="Manual adjustment entry booked in ledger",
    )
    assert res.new_status == "resolved"
    assert res.action == "resolve"

    # Verify atomic update in database
    chk_res = await db_session.execute(select(ExceptionORM).where(ExceptionORM.id == "exc_g3_17"))
    chk_exc = chk_res.scalar_one()
    assert chk_exc.status == "resolved"
    assert chk_exc.resolved is True
    assert chk_exc.resolved_at is not None

    # 2. Cannot apply non-note action on already resolved exception
    with pytest.raises(ValueError, match="Cannot perform action 'approve' on already resolved exception"):
        await human_service.apply_decision(
            exception_id="exc_g3_17",
            action=HumanAction.APPROVE,
            actor="lead_auditor",
        )

    # 3. Add note on resolved item is allowed
    res_note = await human_service.apply_decision(
        exception_id="exc_g3_17",
        action=HumanAction.ADD_NOTE,
        actor="lead_auditor",
        note="Verified with bank settlement team",
    )
    assert res_note.new_status == "resolved"


@pytest.mark.asyncio
async def test_aud_045_multi_criteria_filtering_and_triage_actions(db_session: AsyncSession):
    """AUD-045: Exception queue supports multi-category triage, aging, and actionable recommendations."""
    run = ReconciliationRunORM(
        id="run_g3_045",
        run_id="run_g3_045",
        status="completed",
        created_at=_now(),
        started_at=_now(),
        completed_at=_now(),
        gateway_count=4,
        ledger_count=4,
        bank_count=4,
        match_count=0,
        exception_count=4,
    )
    db_session.add(run)

    txns = [
        TransactionORM(id="t1", domain_transaction_id="T1", source="gateway", amount=Decimal("10000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="t2", domain_transaction_id="T2", source="gateway", amount=Decimal("25000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="t3", domain_transaction_id="T3", source="gateway", amount=Decimal("120000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
        TransactionORM(id="t4", domain_transaction_id="T4", source="gateway", amount=Decimal("500000.00"), currency="INR", timestamp=_now(), status="completed", created_at=_now()),
    ]
    db_session.add_all(txns)
    await db_session.flush()

    excs = [
        ExceptionORM(id="e1", run_id="run_g3_045", transaction_id="t1", exception_category="duplicate_record", status="open", confidence=Decimal("0.95"), financial_exposure=Decimal("10000.00"), expected_cost=Decimal("10000.00"), explanation="Duplicate entry", recommended_action="flag_duplicate", resolved=False, created_at=_now()),
        ExceptionORM(id="e2", run_id="run_g3_045", transaction_id="t2", exception_category="timing_mismatch", status="open", confidence=Decimal("0.85"), financial_exposure=Decimal("25000.00"), expected_cost=Decimal("25000.00"), explanation="Delayed settlement", recommended_action="await_settlement_window", resolved=False, created_at=_now()),
        ExceptionORM(id="e3", run_id="run_g3_045", transaction_id="t3", exception_category="amount_mismatch", status="open", confidence=Decimal("0.90"), financial_exposure=Decimal("120000.00"), expected_cost=Decimal("12000.00"), explanation="Fee variance", recommended_action="request_credit_note", resolved=False, created_at=_now()),
        ExceptionORM(id="e4", run_id="run_g3_045", transaction_id="t4", exception_category="unexplained", status="open", confidence=Decimal("0.30"), financial_exposure=Decimal("500000.00"), expected_cost=Decimal("500000.00"), explanation="High-value unexplained anomaly", recommended_action="investigate", resolved=False, created_at=_now()),
    ]
    db_session.add_all(excs)
    await db_session.commit()

    service = ExceptionManagementService(db_session)

    # 1. Filter by category (both domain and ORM alias)
    dup_items, dup_count = await service.list_exceptions(category="duplicate_entry")
    assert dup_count == 1
    assert dup_items[0]["exception_id"] == "e1"

    # 2. Filter by minimum exposure (high risk >= 100,000)
    high_items, high_count = await service.list_exceptions(min_exposure=Decimal("100000.00"))
    assert high_count == 2
    assert {it["exception_id"] for it in high_items} == {"e3", "e4"}

    # 3. Single detail view
    detail = await service.get_exception_detail("e4")
    assert detail.financial_exposure_inr == 500000.0
    assert detail.category == "unexplained"
    assert detail.recommended_action == "investigate"

    # 4. Aging summary
    aging = await service.calculate_exception_aging("run_g3_045")
    assert aging.total_open_exceptions == 4
    assert aging.total_aging_exposure_inr == 655000.0
