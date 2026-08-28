import os
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
import pytest_asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Transaction as TransactionORM,
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    Decision as DecisionORM,
)
from app.matching.deterministic import DeterministicMatcher
from app.models.match_result import MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.finance_controller import FinanceController
from app.services.reconciliation import ReconciliationService
from app.services.normalization import BankNormalizer
from simulator.scenarios import generate_wrong_reference, generate_normal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.database.session import create_app_engine
from sqlalchemy import text

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


@pytest.fixture
def sample_3way_feed():
    """Create a 3-way dataset: Gateway, Ledger, Bank for 3 transactions."""
    txns_by_source = {
        TransactionSource.GATEWAY: [],
        TransactionSource.LEDGER: [],
        TransactionSource.BANK: [],
    }
    for i in range(1, 4):
        g = Transaction(
            txn_id=f"gw_{i}",
            source=TransactionSource.GATEWAY,
            reference_number=f"UTR_TXN_{i:04d}",
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1, 10, i),
            status=TransactionStatus.COMPLETED,
            order_id=f"ORD_TXN_{i:04d}",
        )
        l = Transaction(
            txn_id=f"ld_{i}",
            source=TransactionSource.LEDGER,
            reference_number=f"REF_TXN_{i:04d}",
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1, 10, i),
            status=TransactionStatus.COMPLETED,
            order_id=f"ORD_TXN_{i:04d}",
        )
        b = Transaction(
            txn_id=f"bk_{i}",
            source=TransactionSource.BANK,
            reference_number=f"UTR_TXN_{i:04d}",
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 2, 10, i),
            status=TransactionStatus.COMPLETED,
            order_id=None,
            narration=f"SETTLEMENT ORD_TXN_{i:04d}",
        )
        txns_by_source[TransactionSource.GATEWAY].append(g)
        txns_by_source[TransactionSource.LEDGER].append(l)
        txns_by_source[TransactionSource.BANK].append(b)

    return txns_by_source


def test_deterministic_produces_true_3way_matches(sample_3way_feed):
    """Verify that 3 matching feeds produce true 3-way matches (ISSUE-AUD-052)."""
    matcher = DeterministicMatcher(sample_3way_feed)
    matches = matcher.match_all()

    assert len(matches) == 3
    for m in matches:
        assert len(m.transaction_ids) == 3
        assert m.match_type == MatchType.EXACT
        assert m.evidence.get("three_way_match") is True
        assert set(m.evidence.get("sources", [])) == {"gateway", "ledger", "bank"}


def test_no_transaction_in_multiple_matches(sample_3way_feed):
    """Verify physical transaction cardinality invariant: 1 match per txn (ISSUE-AUD-053)."""
    matcher = DeterministicMatcher(sample_3way_feed)
    matches = matcher.match_all()

    assigned_txns = []
    for m in matches:
        assigned_txns.extend(m.transaction_ids)

    # Every transaction ID must appear exactly once
    assert len(assigned_txns) == len(set(assigned_txns))
    assert len(assigned_txns) == 9  # 3 * 3


def test_asymmetric_feed_matching():
    """Verify asymmetric feeds (missing feeds, partial matches)."""
    # 3 Gateway, 2 Ledger, 1 Bank
    # gw_1 has ld_1 and bk_1 -> 3-way match
    # gw_2 has ld_2 -> 2-way match
    # gw_3 is standalone -> unmatched
    g1 = Transaction(
        txn_id="g1", source=TransactionSource.GATEWAY, reference_number="UTR1",
        amount=Decimal("100.00"), currency="INR", timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED, order_id="ORD1",
    )
    l1 = Transaction(
        txn_id="l1", source=TransactionSource.LEDGER, reference_number="REF1",
        amount=Decimal("100.00"), currency="INR", timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED, order_id="ORD1",
    )
    b1 = Transaction(
        txn_id="b1", source=TransactionSource.BANK, reference_number="UTR1",
        amount=Decimal("100.00"), currency="INR", timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED, order_id=None,
    )

    g2 = Transaction(
        txn_id="g2", source=TransactionSource.GATEWAY, reference_number="UTR2",
        amount=Decimal("200.00"), currency="INR", timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED, order_id="ORD2",
    )
    l2 = Transaction(
        txn_id="l2", source=TransactionSource.LEDGER, reference_number="REF2",
        amount=Decimal("200.00"), currency="INR", timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED, order_id="ORD2",
    )

    g3 = Transaction(
        txn_id="g3", source=TransactionSource.GATEWAY, reference_number="UTR3",
        amount=Decimal("300.00"), currency="INR", timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED, order_id="ORD3",
    )

    feed = {
        TransactionSource.GATEWAY: [g1, g2, g3],
        TransactionSource.LEDGER: [l1, l2],
        TransactionSource.BANK: [b1],
    }

    matcher = DeterministicMatcher(feed)
    matches = matcher.match_all()

    # Should have 2 matches: one 3-way (g1, l1, b1) and one 2-way (g2, l2)
    assert len(matches) == 2
    three_way = [m for m in matches if len(m.transaction_ids) == 3]
    two_way = [m for m in matches if len(m.transaction_ids) == 2]

    assert len(three_way) == 1
    assert set(three_way[0].transaction_ids) == {"g1", "l1", "b1"}

    assert len(two_way) == 1
    assert set(two_way[0].transaction_ids) == {"g2", "l2"}

    # No double assignment
    all_matched = [tid for m in matches for tid in m.transaction_ids]
    assert len(all_matched) == len(set(all_matched))
    assert "g3" not in all_matched


def test_wrong_reference_scenario_uniqueness():
    """Verify that wrong reference generator creates distinct identifiers (ISSUE-AUD-054)."""
    r1 = generate_wrong_reference("TXN00000001", "GW001", "ORD00000001", "BK001", Decimal("100.00"), datetime(2024, 1, 1), "INR")
    r2 = generate_wrong_reference("TXN00000002", "GW002", "ORD00000002", "BK002", Decimal("100.00"), datetime(2024, 1, 1), "INR")

    # Corrupted references must not collide across different transactions
    assert r1[0].order_id != r2[0].order_id
    assert r1[2].utr != r2[2].utr
    assert r1[1].internal_reference != r2[1].internal_reference


def test_bank_normalizer_extracts_order_id_from_narration():
    """Verify bank normalizer extracts order_id from narration when order_id column is absent (ISSUE-AUD-055)."""
    row = {
        "bank_transaction_id": "BK_1001",
        "utr": "UTR1001",
        "credit_amount": "500.00",
        "debit_amount": "0.00",
        "value_date": "2024-01-02T10:00:00",
        "narration": "SETTLEMENT ORD_99999 FOR CLIENT",
        "currency": "INR",
    }
    txn = BankNormalizer.normalize_row(row)
    assert txn.order_id == "ORD_99999"
    assert txn.reference_number == "UTR1001"
    assert txn.amount == Decimal("500.00")


@pytest.mark.asyncio
async def test_logical_transactions_not_hardcoded_div_3(db_session: AsyncSession):
    """Verify total_logical_transactions is dynamically computed from real entities (ISSUE-AUD-009)."""
    # Insert 5 total transactions: 3 forming a 3-way match (1 logical), 2 unmatched (2 logical)
    # Total physical records = 5. Hardcoded 5 // 3 would give 1 (wrong). Correct count is 3!
    now = datetime.utcnow()
    g1 = TransactionORM(
        id="g1_uuid", domain_transaction_id="g1", source="gateway",
        order_id="ORD_A", reference_number="UTR_A", amount=Decimal("100.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )
    l1 = TransactionORM(
        id="l1_uuid", domain_transaction_id="l1", source="ledger",
        order_id="ORD_A", reference_number="REF_A", amount=Decimal("100.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )
    b1 = TransactionORM(
        id="b1_uuid", domain_transaction_id="b1", source="bank",
        order_id="ORD_A", reference_number="UTR_A", amount=Decimal("100.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )

    # Unmatched standalone records
    g_standalone = TransactionORM(
        id="g_standalone_uuid", domain_transaction_id="g_standalone", source="gateway",
        order_id="ORD_STANDALONE", reference_number="UTR_STANDALONE", amount=Decimal("250.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )
    b_standalone = TransactionORM(
        id="b_standalone_uuid", domain_transaction_id="b_standalone", source="bank",
        order_id=None, reference_number="UTR_BANK_STANDALONE", amount=Decimal("350.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )

    db_session.add_all([g1, l1, b1, g_standalone, b_standalone])
    await db_session.flush()

    from app.database.models import ReconciliationRun
    run_orm = ReconciliationRun(
        id="run_test",
        run_id="run_test",
        status="completed",
        started_at=now,
        completed_at=now,
        gateway_count=2,
        ledger_count=1,
        bank_count=2,
        match_count=1,
        exception_count=0,
        created_at=now,
    )
    db_session.add(run_orm)
    await db_session.flush()

    # Create 1 match covering (g1, l1, b1)
    match_orm = MatchORM(
        id="match_1_uuid",
        run_id="run_test",
        match_type="exact",
        confidence=Decimal("0.98"),
        reason="Exact 3-way match",
        evidence={"order_id": "ORD_A"},
        created_at=now,
    )
    db_session.add(match_orm)
    await db_session.flush()

    db_session.add_all([
        MatchTransactionORM(match_id="match_1_uuid", transaction_id="g1_uuid"),
        MatchTransactionORM(match_id="match_1_uuid", transaction_id="l1_uuid"),
        MatchTransactionORM(match_id="match_1_uuid", transaction_id="b1_uuid"),
    ])
    await db_session.flush()

    ctrl = FinanceController(db_session)
    kpis = await ctrl.get_summary_kpis()

    assert kpis.total_records_processed == 5
    # Must be 1 match + 2 unmatched clusters = 3 logical transactions (never 5 // 3 = 1)
    assert kpis.total_logical_transactions == 3


@pytest.mark.asyncio
async def test_duplicate_detection_reproducible_and_not_fabricated(db_session: AsyncSession):
    """Verify duplicate detection returns 0 incidents when clean, and exact incidents when present (ISSUE-AUD-042)."""
    now = datetime.utcnow()
    # 1. Clean transactions
    g1 = TransactionORM(
        id="g1_uuid", domain_transaction_id="g1", source="gateway",
        order_id="ORD_1", reference_number="UTR_1", amount=Decimal("100.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )
    g2 = TransactionORM(
        id="g2_uuid", domain_transaction_id="g2", source="gateway",
        order_id="ORD_2", reference_number="UTR_2", amount=Decimal("200.00"),
        currency="INR", timestamp=datetime(2024, 1, 1), status="completed",
        created_at=now,
    )
    db_session.add_all([g1, g2])
    await db_session.flush()

    dup_svc = DuplicateDetectionService(db_session)
    clean_report = await dup_svc.audit_duplicates()
    assert clean_report.total_incidents_detected == 0
    assert clean_report.duplicate_charges_count == 0
    assert clean_report.duplicate_charges_exposure == "0.00"

    # 2. Add an intentional duplicate charge on gateway for ORD_1
    g1_dup = TransactionORM(
        id="g1_dup_uuid", domain_transaction_id="g1_dup", source="gateway",
        order_id="ORD_1", reference_number="UTR_1_DUP", amount=Decimal("100.00"),
        currency="INR", timestamp=datetime(2024, 1, 1, 10, 5), status="completed",
        created_at=now,
    )
    db_session.add(g1_dup)
    await db_session.flush()

    dup_report = await dup_svc.audit_duplicates()
    assert dup_report.total_incidents_detected == 1
    assert dup_report.duplicate_charges_count == 1
    assert dup_report.duplicate_charges_exposure == "100.00"
    incident = dup_report.incidents[0]
    assert incident["identifier"] == "ORD_1"
    assert incident["record_count"] == 2
    assert set(incident["affected_transaction_ids"]) == {"g1", "g1_dup"}
