import os
from datetime import datetime
from decimal import Decimal

from dotenv import load_dotenv
import pytest
import pytest_asyncio

load_dotenv()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Skip tests if test DB is not available
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://sentinel:test123@localhost:5432/sentinel_test")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="PostgreSQL TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Clean tables in isolated test database before each test."""
    database_url = TEST_DATABASE_URL
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")
    from app.database.session import create_app_engine
    from sqlalchemy import text
    engine = create_app_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE audit_events, exception_transactions, match_transactions, "
            "decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"
        ))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    """Create a test database session in isolated test DB."""
    database_url = TEST_DATABASE_URL
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")

    from app.database.session import create_app_engine
    engine = create_app_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_transaction_create_and_retrieve(db_session: AsyncSession):
    """Test creating and retrieving a transaction."""
    from app.database.models import Transaction, TransactionSource, TransactionStatus

    txn = Transaction(
        id="test-txn-1",
        domain_transaction_id="GTX123",
        source=TransactionSource.GATEWAY,
        reference_number="REF123",
        order_id="ORD123",
        amount=Decimal("100.50"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        narration="Test transaction",
        fee=Decimal("2.50"),
        tax=Decimal("8.50"),
        status=TransactionStatus.PROCESSED,
        meta_data={"key": "value"},
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(txn)
    await db_session.commit()

    result = await db_session.execute(select(Transaction).where(Transaction.id == "test-txn-1"))
    retrieved = result.scalar_one()

    assert retrieved is not None
    assert retrieved.domain_transaction_id == "GTX123"
    assert retrieved.source == TransactionSource.GATEWAY
    assert retrieved.amount == Decimal("100.50")
    assert retrieved.currency == "USD"
    assert retrieved.meta_data == {"key": "value"}


@pytest.mark.asyncio
async def test_transaction_unique_constraint(db_session: AsyncSession):
    """Test unique constraint on (source, domain_transaction_id)."""
    from app.database.models import Transaction, TransactionSource, TransactionStatus
    from sqlalchemy.exc import IntegrityError

    txn1 = Transaction(
        id="test-txn-2",
        domain_transaction_id="GTX456",
        source=TransactionSource.GATEWAY,
        amount=Decimal("50.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(txn1)
    await db_session.commit()

    txn2 = Transaction(
        id="test-txn-3",
        domain_transaction_id="GTX456",  # Same domain ID
        source=TransactionSource.GATEWAY,  # Same source
        amount=Decimal("75.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(txn2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_reconciliation_run_and_items_relationship(db_session: AsyncSession):
    """Test relationship between reconciliation_run and reconciliation_items."""
    from app.database.models import (
        ReconciliationRun,
        ReconciliationItem,
        ReconciliationRunStatus,
        Transaction,
        TransactionSource,
        TransactionStatus,
    )

    run = ReconciliationRun(
        id="run-rel-1",
        run_id="RUN-REL-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=10,
        ledger_count=10,
        bank_count=10,
        match_count=8,
        exception_count=2,
        summary="Test run",
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn = Transaction(
        id="txn-rel-1",
        domain_transaction_id="TXN-REL-001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([run, txn])
    await db_session.flush()

    item = ReconciliationItem(
        id="item-rel-1",
        run_id=run.id,
        transaction_id=txn.id,
        processing_status="matched",
        resulting_action="auto_match",
        created_at=datetime(2026, 8, 24, 10, 0, 0),
        updated_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(item)
    await db_session.commit()

    # Verify relationship
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(ReconciliationRun)
        .options(selectinload(ReconciliationRun.reconciliation_items))
        .where(ReconciliationRun.id == "run-rel-1")
    )
    retrieved_run = result.scalar_one()
    assert len(retrieved_run.reconciliation_items) == 1
    assert retrieved_run.reconciliation_items[0].transaction_id == "txn-rel-1"


@pytest.mark.asyncio
async def test_match_and_transactions_relationship(db_session: AsyncSession):
    """Test N:M relationship between matches and transactions via junction table."""
    from app.database.models import (
        Match,
        MatchTransaction,
        MatchType,
        ReconciliationRun,
        ReconciliationRunStatus,
        Transaction,
        TransactionSource,
        TransactionStatus,
    )

    run = ReconciliationRun(
        id="run-match-1",
        run_id="RUN-MATCH-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=1,
        bank_count=0,
        match_count=1,
        exception_count=0,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn1 = Transaction(
        id="txn-match-1",
        domain_transaction_id="TXN-MATCH-001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn2 = Transaction(
        id="txn-match-2",
        domain_transaction_id="TXN-MATCH-002",
        source=TransactionSource.LEDGER,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([run, txn1, txn2])
    await db_session.flush()

    match = Match(
        id="match-nm-1",
        run_id=run.id,
        match_type=MatchType.EXACT,
        confidence=Decimal("1.0"),
        reason="Exact match",
        evidence={"amount_match": True},
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(match)
    await db_session.flush()

    mt1 = MatchTransaction(match_id=match.id, transaction_id=txn1.id)
    mt2 = MatchTransaction(match_id=match.id, transaction_id=txn2.id)
    db_session.add_all([mt1, mt2])
    await db_session.commit()

    # Verify junction table
    result = await db_session.execute(
        select(MatchTransaction).where(MatchTransaction.match_id == "match-nm-1")
    )
    transactions = result.scalars().all()
    assert len(transactions) == 2


@pytest.mark.asyncio
async def test_exception_and_transactions_relationship(db_session: AsyncSession):
    """Test N:M relationship between exceptions and transactions via junction table."""
    from app.database.models import (
        Exception,
        ExceptionTransaction,
        ExceptionCategory,
        ReconciliationRun,
        ReconciliationRunStatus,
        Transaction,
        TransactionSource,
        TransactionStatus,
    )

    run = ReconciliationRun(
        id="run-exc-1",
        run_id="RUN-EXC-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=1,
        bank_count=0,
        match_count=0,
        exception_count=1,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn1 = Transaction(
        id="txn-exc-1",
        domain_transaction_id="TXN-EXC-001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn2 = Transaction(
        id="txn-exc-2",
        domain_transaction_id="TXN-EXC-002",
        source=TransactionSource.LEDGER,
        amount=Decimal("105.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([run, txn1, txn2])
    await db_session.flush()

    exc = Exception(
        id="exc-nm-1",
        run_id=run.id,
        transaction_id=txn1.id,
        exception_category=ExceptionCategory.AMOUNT_MISMATCH,
        status="open",
        confidence=Decimal("0.9"),
        financial_exposure=Decimal("100.00"),
        expected_cost=Decimal("50.00"),
        explanation="Amount mismatch",
        evidence={},
        resolved=False,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(exc)
    await db_session.flush()

    et1 = ExceptionTransaction(exception_id=exc.id, transaction_id=txn1.id)
    et2 = ExceptionTransaction(exception_id=exc.id, transaction_id=txn2.id)
    db_session.add_all([et1, et2])
    await db_session.commit()

    # Verify junction table
    result = await db_session.execute(
        select(ExceptionTransaction).where(ExceptionTransaction.exception_id == "exc-nm-1")
    )
    transactions = result.scalars().all()
    assert len(transactions) == 2


@pytest.mark.asyncio
async def test_decision_foreign_key(db_session: AsyncSession):
    """Test foreign key relationship between decision and match."""
    from app.database.models import (
        Decision,
        DecisionAction,
        Match,
        MatchType,
        ReconciliationRun,
        ReconciliationRunStatus,
    )

    run = ReconciliationRun(
        id="run-dec-1",
        run_id="RUN-DEC-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=1,
        bank_count=0,
        match_count=1,
        exception_count=0,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(run)
    await db_session.flush()

    match = Match(
        id="match-dec-1",
        run_id=run.id,
        match_type=MatchType.EXACT,
        confidence=Decimal("0.95"),
        reason="Exact match",
        evidence={"score": 0.95},
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(match)
    await db_session.flush()

    decision = Decision(
        id="decision-1",
        run_id=run.id,
        match_id=match.id,
        decision_action=DecisionAction.AUTO_MATCH,
        deterministic_confidence=Decimal("0.95"),
        ml_probability=None,
        candidate_margin=None,
        evidence={"score": 0.95},
        reason="High confidence",
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(decision)
    await db_session.commit()

    result = await db_session.execute(select(Decision).where(Decision.id == "decision-1"))
    retrieved = result.scalar_one()
    assert retrieved.match_id == "match-dec-1"


@pytest.mark.asyncio
async def test_audit_event_foreign_keys(db_session: AsyncSession):
    """Test foreign key relationships in audit events."""
    from app.database.models import (
        AuditEvent,
        ReconciliationRun,
        ReconciliationRunStatus,
        Transaction,
        TransactionSource,
        TransactionStatus,
    )

    run = ReconciliationRun(
        id="run-audit-1",
        run_id="RUN-AUDIT-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=1,
        bank_count=0,
        match_count=1,
        exception_count=0,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn = Transaction(
        id="txn-audit-1",
        domain_transaction_id="TXN-AUDIT-001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([run, txn])
    await db_session.flush()

    audit = AuditEvent(
        id="audit-1",
        run_id=run.id,
        transaction_id=txn.id,
        event_type="match",
        stage="matching",
        action="auto_match",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        meta_data={"key": "value"},
        decision={"action": "auto_match"},
    )
    db_session.add(audit)
    await db_session.commit()

    result = await db_session.execute(select(AuditEvent).where(AuditEvent.id == "audit-1"))
    retrieved = result.scalar_one()
    assert retrieved.run_id == "run-audit-1"
    assert retrieved.transaction_id == "txn-audit-1"


@pytest.mark.asyncio
async def test_decimal_persistence(db_session: AsyncSession):
    """Test that Decimal values are persisted correctly."""
    from app.database.models import Transaction, TransactionSource, TransactionStatus

    txn = Transaction(
        id="test-decimal",
        domain_transaction_id="GTX789",
        source=TransactionSource.GATEWAY,
        amount=Decimal("123.4567"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(txn)
    await db_session.commit()

    result = await db_session.execute(select(Transaction).where(Transaction.id == "test-decimal"))
    retrieved = result.scalar_one()
    assert retrieved.amount == Decimal("123.4567")


@pytest.mark.asyncio
async def test_jsonb_storage(db_session: AsyncSession):
    """Test JSONB field storage and retrieval."""
    from app.database.models import Transaction, TransactionSource, TransactionStatus

    metadata = {"nested": {"key": "value", "number": 42}, "list": [1, 2, 3]}
    txn = Transaction(
        id="test-jsonb",
        domain_transaction_id="GTX999",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        meta_data=metadata,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(txn)
    await db_session.commit()

    result = await db_session.execute(select(Transaction).where(Transaction.id == "test-jsonb"))
    retrieved = result.scalar_one()
    assert retrieved.meta_data == metadata
    assert retrieved.meta_data["nested"]["number"] == 42


@pytest.mark.asyncio
async def test_same_transaction_multiple_runs(db_session: AsyncSession):
    """Test that the same transaction can appear in multiple reconciliation runs."""
    from app.database.models import (
        Transaction,
        ReconciliationRun,
        ReconciliationItem,
        TransactionSource,
        TransactionStatus,
        ReconciliationRunStatus,
    )

    # Create a transaction
    txn = Transaction(
        id="shared-txn",
        domain_transaction_id="SHARED001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(txn)
    await db_session.flush()

    # Create two runs
    run1 = ReconciliationRun(
        id="run-shared-1",
        run_id="RUN-SH-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=1,
        bank_count=1,
        match_count=1,
        exception_count=0,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    run2 = ReconciliationRun(
        id="run-shared-2",
        run_id="RUN-SH-002",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=1,
        bank_count=1,
        match_count=1,
        exception_count=0,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([run1, run2])
    await db_session.flush()

    # Add the same transaction to both runs
    item1 = ReconciliationItem(
        id="item-sh-1",
        run_id=run1.id,
        transaction_id=txn.id,
        processing_status="matched",
        created_at=datetime(2026, 8, 24, 10, 0, 0),
        updated_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    item2 = ReconciliationItem(
        id="item-sh-2",
        run_id=run2.id,
        transaction_id=txn.id,
        processing_status="matched",
        created_at=datetime(2026, 8, 24, 10, 0, 0),
        updated_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([item1, item2])
    await db_session.commit()

    # Verify both items exist
    result = await db_session.execute(
        select(ReconciliationItem).where(ReconciliationItem.transaction_id == "shared-txn")
    )
    items = result.scalars().all()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_foreign_key_restrict(db_session: AsyncSession):
    """Test that RESTRICT foreign key constraint prevents deletion of referenced records."""
    from app.database.models import (
        Transaction,
        ReconciliationItem,
        ReconciliationRun,
        ReconciliationRunStatus,
        TransactionSource,
        TransactionStatus,
    )
    from sqlalchemy.exc import IntegrityError

    # Create run and transaction
    run = ReconciliationRun(
        id="run-fk-1",
        run_id="RUN-FK-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 10, 0, 0),
        completed_at=datetime(2026, 8, 24, 10, 5, 0),
        gateway_count=1,
        ledger_count=0,
        bank_count=0,
        match_count=0,
        exception_count=0,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    txn = Transaction(
        id="fk-test-txn",
        domain_transaction_id="FK001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2026, 8, 24, 10, 0, 0),
        status=TransactionStatus.PROCESSED,
        created_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add_all([run, txn])
    await db_session.flush()

    # Create item referencing transaction
    item = ReconciliationItem(
        id="fk-test-item",
        run_id=run.id,
        transaction_id=txn.id,
        processing_status="matched",
        created_at=datetime(2026, 8, 24, 10, 0, 0),
        updated_at=datetime(2026, 8, 24, 10, 0, 0),
    )
    db_session.add(item)
    await db_session.commit()

    # Try to delete the transaction (should fail due to RESTRICT)
    txn_to_delete = await db_session.get(Transaction, "fk-test-txn")
    await db_session.delete(txn_to_delete)

    with pytest.raises(IntegrityError):
        await db_session.commit()
