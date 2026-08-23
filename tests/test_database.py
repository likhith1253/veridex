import os
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Skip tests if PostgreSQL is not available
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="PostgreSQL DATABASE_URL not set"
)


@pytest.fixture
async def db_session():
    """Create a test database session."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    engine = create_async_engine(database_url, echo=False)
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
        timestamp=datetime.now(timezone.utc),
        narration="Test transaction",
        fee=Decimal("2.50"),
        tax=Decimal("8.50"),
        status=TransactionStatus.PROCESSED,
        metadata={"key": "value"},
        created_at=datetime.now(timezone.utc),
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
    assert retrieved.metadata == {"key": "value"}


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
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PROCESSED,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(txn1)
    await db_session.commit()

    txn2 = Transaction(
        id="test-txn-3",
        domain_transaction_id="GTX456",  # Same domain ID
        source=TransactionSource.GATEWAY,  # Same source
        amount=Decimal("75.00"),
        currency="USD",
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PROCESSED,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(txn2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_reconciliation_run_and_items_relationship(db_session: AsyncSession):
    """Test relationship between reconciliation_run and reconciliation_items."""
    from app.database.models import ReconciliationRun, ReconciliationItem, ReconciliationRunStatus

    run = ReconciliationRun(
        id="run-1",
        run_id="RUN-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        gateway_count=10,
        ledger_count=10,
        bank_count=10,
        match_count=8,
        exception_count=2,
        summary="Test run",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    await db_session.flush()

    item = ReconciliationItem(
        id="item-1",
        run_id=run.id,
        transaction_id="txn-1",
        processing_status="matched",
        resulting_action="auto_match",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(item)
    await db_session.commit()

    # Verify relationship
    result = await db_session.execute(
        select(ReconciliationRun).where(ReconciliationRun.id == "run-1")
    )
    retrieved_run = result.scalar_one()
    assert len(retrieved_run.reconciliation_items) == 1
    assert retrieved_run.reconciliation_items[0].transaction_id == "txn-1"


@pytest.mark.asyncio
async def test_match_and_transactions_relationship(db_session: AsyncSession):
    """Test N:M relationship between matches and transactions via junction table."""
    from app.database.models import Match, MatchTransaction, MatchType

    match = Match(
        id="match-1",
        run_id="run-1",
        match_type=MatchType.EXACT,
        confidence=Decimal("1.0"),
        reason="Exact match",
        evidence={"amount_match": True},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(match)
    await db_session.flush()

    mt1 = MatchTransaction(match_id=match.id, transaction_id="txn-1")
    mt2 = MatchTransaction(match_id=match.id, transaction_id="txn-2")
    db_session.add_all([mt1, mt2])
    await db_session.commit()

    # Verify junction table
    result = await db_session.execute(
        select(MatchTransaction).where(MatchTransaction.match_id == "match-1")
    )
    transactions = result.scalars().all()
    assert len(transactions) == 2


@pytest.mark.asyncio
async def test_exception_and_transactions_relationship(db_session: AsyncSession):
    """Test N:M relationship between exceptions and transactions via junction table."""
    from app.database.models import Exception, ExceptionTransaction, ExceptionCategory

    exc = Exception(
        id="exc-1",
        run_id="run-1",
        transaction_id="txn-1",
        exception_category=ExceptionCategory.AMOUNT_MISMATCH,
        status="open",
        confidence=Decimal("0.9"),
        financial_exposure=Decimal("100.00"),
        expected_cost=Decimal("50.00"),
        explanation="Amount mismatch",
        evidence={},
        resolved=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(exc)
    await db_session.flush()

    et1 = ExceptionTransaction(exception_id=exc.id, transaction_id="txn-1")
    et2 = ExceptionTransaction(exception_id=exc.id, transaction_id="txn-2")
    db_session.add_all([et1, et2])
    await db_session.commit()

    # Verify junction table
    result = await db_session.execute(
        select(ExceptionTransaction).where(ExceptionTransaction.exception_id == "exc-1")
    )
    transactions = result.scalars().all()
    assert len(transactions) == 2


@pytest.mark.asyncio
async def test_decision_foreign_key(db_session: AsyncSession):
    """Test foreign key relationship between decision and match."""
    from app.database.models import Decision, DecisionAction

    decision = Decision(
        id="decision-1",
        run_id="run-1",
        match_id="match-1",
        decision_action=DecisionAction.AUTO_MATCH,
        deterministic_confidence=Decimal("0.95"),
        ml_probability=None,
        candidate_margin=None,
        evidence={"score": 0.95},
        reason="High confidence",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(decision)
    await db_session.commit()

    result = await db_session.execute(select(Decision).where(Decision.id == "decision-1"))
    retrieved = result.scalar_one()
    assert retrieved.match_id == "match-1"


@pytest.mark.asyncio
async def test_audit_event_foreign_keys(db_session: AsyncSession):
    """Test foreign key relationships in audit events."""
    from app.database.models import AuditEvent

    audit = AuditEvent(
        id="audit-1",
        run_id="run-1",
        transaction_id="txn-1",
        event_type="match",
        stage="matching",
        action="auto_match",
        timestamp=datetime.now(timezone.utc),
        metadata={"key": "value"},
        decision={"action": "auto_match"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(audit)
    await db_session.commit()

    result = await db_session.execute(select(AuditEvent).where(AuditEvent.id == "audit-1"))
    retrieved = result.scalar_one()
    assert retrieved.run_id == "run-1"
    assert retrieved.transaction_id == "txn-1"


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
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PROCESSED,
        created_at=datetime.now(timezone.utc),
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
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PROCESSED,
        metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(txn)
    await db_session.commit()

    result = await db_session.execute(select(Transaction).where(Transaction.id == "test-jsonb"))
    retrieved = result.scalar_one()
    assert retrieved.metadata == metadata
    assert retrieved.metadata["nested"]["number"] == 42


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
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PROCESSED,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(txn)
    await db_session.flush()

    # Create two runs
    run1 = ReconciliationRun(
        id="run-1",
        run_id="RUN-001",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        gateway_count=1,
        ledger_count=1,
        bank_count=1,
        match_count=1,
        exception_count=0,
        created_at=datetime.now(timezone.utc),
    )
    run2 = ReconciliationRun(
        id="run-2",
        run_id="RUN-002",
        status=ReconciliationRunStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        gateway_count=1,
        ledger_count=1,
        bank_count=1,
        match_count=1,
        exception_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([run1, run2])
    await db_session.flush()

    # Add the same transaction to both runs
    item1 = ReconciliationItem(
        id="item-1",
        run_id=run1.id,
        transaction_id=txn.id,
        processing_status="matched",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    item2 = ReconciliationItem(
        id="item-2",
        run_id=run2.id,
        transaction_id=txn.id,
        processing_status="matched",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
    from app.database.models import Transaction, ReconciliationItem, TransactionSource, TransactionStatus
    from sqlalchemy.exc import IntegrityError

    # Create transaction
    txn = Transaction(
        id="fk-test-txn",
        domain_transaction_id="FK001",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PROCESSED,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(txn)
    await db_session.flush()

    # Create item referencing transaction
    item = ReconciliationItem(
        id="fk-test-item",
        run_id="run-1",
        transaction_id=txn.id,
        processing_status="matched",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(item)
    await db_session.commit()

    # Try to delete the transaction (should fail due to RESTRICT)
    await db_session.execute(select(Transaction).where(Transaction.id == "fk-test-txn"))
    txn_to_delete = await db_session.get(Transaction, "fk-test-txn")
    db_session.delete(txn_to_delete)

    with pytest.raises(IntegrityError):
        await db_session.commit()
