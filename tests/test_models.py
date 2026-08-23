from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models import (
    AuditEvent,
    ExceptionCategory,
    ExceptionRecord,
    MatchResult,
    MatchType,
    ReconciliationRun,
    RunStatus,
    Transaction,
    TransactionSource,
    TransactionStatus,
)


def test_valid_transaction():
    txn = Transaction(
        txn_id="TXN001",
        source=TransactionSource.GATEWAY,
        reference_number="REF123",
        amount=Decimal("100.50"),
        currency="USD",
        timestamp=datetime.now(timezone.utc),
        narration="Test transaction",
        fee=Decimal("2.50"),
        tax=Decimal("8.50"),
        status=TransactionStatus.COMPLETED,
        order_id="ORD001",
    )
    assert txn.txn_id == "TXN001"
    assert txn.source == TransactionSource.GATEWAY
    assert txn.amount == Decimal("100.50")


def test_transaction_decimal_amounts():
    txn = Transaction(
        txn_id="TXN002",
        source=TransactionSource.LEDGER,
        amount=Decimal("99.99"),
        currency="EUR",
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.PENDING,
    )
    assert isinstance(txn.amount, Decimal)
    assert txn.amount == Decimal("99.99")


def test_transaction_source_enum():
    assert TransactionSource.GATEWAY == "gateway"
    assert TransactionSource.LEDGER == "ledger"
    assert TransactionSource.BANK == "bank"


def test_transaction_status_enum():
    assert TransactionStatus.PENDING == "pending"
    assert TransactionStatus.COMPLETED == "completed"
    assert TransactionStatus.FAILED == "failed"
    assert TransactionStatus.REFUNDED == "refunded"
    assert TransactionStatus.PARTIALLY_REFUNDED == "partially_refunded"


def test_transaction_invalid_amount_negative():
    with pytest.raises(ValueError):
        Transaction(
            txn_id="TXN003",
            source=TransactionSource.BANK,
            amount=Decimal("-10.00"),
            currency="USD",
            timestamp=datetime.now(timezone.utc),
            status=TransactionStatus.COMPLETED,
        )


def test_transaction_invalid_fee_negative():
    with pytest.raises(ValueError):
        Transaction(
            txn_id="TXN004",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="USD",
            timestamp=datetime.now(timezone.utc),
            status=TransactionStatus.COMPLETED,
            fee=Decimal("-5.00"),
        )


def test_match_result():
    result = MatchResult(
        transaction_ids=["TXN001", "TXN002"],
        confidence=Decimal("0.95"),
        reason="Amount and timestamp match",
        match_type=MatchType.EXACT,
        evidence={"amount_diff": 0, "time_diff": 0},
        recommended_action="Accept",
    )
    assert result.transaction_ids == ["TXN001", "TXN002"]
    assert result.confidence == Decimal("0.95")
    assert result.match_type == MatchType.EXACT


def test_match_result_confidence_bounds():
    with pytest.raises(ValueError):
        MatchResult(
            transaction_ids=["TXN001"],
            confidence=Decimal("1.5"),
            reason="Test",
            match_type=MatchType.PROBABLE,
        )

    with pytest.raises(ValueError):
        MatchResult(
            transaction_ids=["TXN001"],
            confidence=Decimal("-0.1"),
            reason="Test",
            match_type=MatchType.PROBABLE,
        )


def test_match_type_enum():
    assert MatchType.EXACT == "exact"
    assert MatchType.PROBABLE == "probable"
    assert MatchType.PARTIAL == "partial"
    assert MatchType.NONE == "none"


def test_exception_record():
    exc = ExceptionRecord(
        transaction_id="TXN001",
        category=ExceptionCategory.CURRENCY_ROUNDING,
        confidence=Decimal("0.90"),
        financial_exposure=Decimal("0.01"),
        expected_cost=Decimal("0.01"),
        explanation="Rounding difference between sources",
        evidence={"gateway_amount": "10.00", "ledger_amount": "9.99"},
        recommended_action="Accept as rounding error",
    )
    assert exc.transaction_id == "TXN001"
    assert exc.category == ExceptionCategory.CURRENCY_ROUNDING
    assert exc.confidence == Decimal("0.90")


def test_exception_category_enum():
    assert ExceptionCategory.CURRENCY_ROUNDING == "currency_rounding"
    assert ExceptionCategory.PARTIAL_REFUND == "partial_refund"
    assert ExceptionCategory.DELAYED_SETTLEMENT == "delayed_settlement"
    assert ExceptionCategory.DUPLICATE_ENTRY == "duplicate_entry"
    assert ExceptionCategory.FEE_MISMATCH == "fee_mismatch"
    assert ExceptionCategory.WRONG_REFERENCE == "wrong_reference"
    assert ExceptionCategory.AMBIGUOUS_MATCH == "ambiguous_match"
    assert ExceptionCategory.UNEXPLAINED == "unexplained"


def test_exception_record_invalid_confidence():
    with pytest.raises(ValueError):
        ExceptionRecord(
            transaction_id="TXN001",
            category=ExceptionCategory.UNEXPLAINED,
            confidence=Decimal("1.5"),
            financial_exposure=Decimal("100.00"),
            expected_cost=Decimal("100.00"),
            explanation="Test",
        )


def test_exception_record_negative_exposure():
    with pytest.raises(ValueError):
        ExceptionRecord(
            transaction_id="TXN001",
            category=ExceptionCategory.UNEXPLAINED,
            confidence=Decimal("0.5"),
            financial_exposure=Decimal("-10.00"),
            expected_cost=Decimal("10.00"),
            explanation="Test",
        )


def test_audit_event():
    event = AuditEvent(
        run_id="RUN001",
        transaction_id="TXN001",
        stage="matching",
        event="exact_match_found",
        evidence={"match_score": 1.0},
        decision={"action": "accept"},
    )
    assert event.run_id == "RUN001"
    assert event.transaction_id == "TXN001"
    assert event.stage == "matching"
    assert event.event == "exact_match_found"


def test_audit_event_without_transaction():
    event = AuditEvent(
        run_id="RUN002",
        stage="validation",
        event="run_started",
    )
    assert event.run_id == "RUN002"
    assert event.transaction_id is None


def test_reconciliation_run():
    run = ReconciliationRun(
        run_id="RUN001",
        status=RunStatus.RUNNING,
        gateway_count=100,
        ledger_count=100,
        bank_count=100,
        match_count=95,
        exception_count=5,
        summary="Reconciliation completed with 5 exceptions",
    )
    assert run.run_id == "RUN001"
    assert run.status == RunStatus.RUNNING
    assert run.gateway_count == 100
    assert run.match_count == 95


def test_run_status_enum():
    assert RunStatus.PENDING == "pending"
    assert RunStatus.RUNNING == "running"
    assert RunStatus.COMPLETED == "completed"
    assert RunStatus.FAILED == "failed"


def test_reconciliation_run_defaults():
    run = ReconciliationRun(run_id="RUN003")
    assert run.status == RunStatus.PENDING
    assert run.gateway_count == 0
    assert run.ledger_count == 0
    assert run.bank_count == 0
    assert run.match_count == 0
    assert run.exception_count == 0
    assert run.created_at is not None
