from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.matching.deterministic import (
    AMBIGUOUS_CONFIDENCE,
    AMOUNT_DATE_UNIQUE_CONFIDENCE,
    DATE_WINDOW_DAYS,
    DeterministicMatcher,
    EXACT_ORDER_ID_CONFIDENCE,
    EXACT_TXN_REF_CONFIDENCE,
    EXACT_UTR_CONFIDENCE,
)
from app.models.match_result import MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus


def test_exact_utr_match_produces_high_confidence():
    """Test 1: Exact UTR match produces high confidence (0.98)"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == EXACT_UTR_CONFIDENCE
    assert results[0].match_type == MatchType.EXACT


def test_exact_order_id_match_produces_high_confidence():
    """Test 2: Exact order ID match produces high confidence (0.95)"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        order_id="ORD123",
    )
    ledger_txn = Transaction(
        txn_id="l1",
        source=TransactionSource.LEDGER,
        reference_number="REF456",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        order_id="ORD123",
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.LEDGER: [ledger_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == EXACT_ORDER_ID_CONFIDENCE


def test_valid_gateway_ledger_relationship():
    """Test 3: Valid gateway↔ledger relationship"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        order_id="ORD123",
    )
    ledger_txn = Transaction(
        txn_id="l1",
        source=TransactionSource.LEDGER,
        reference_number="REF456",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        order_id="ORD123",
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.LEDGER: [ledger_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert set(results[0].transaction_ids) == {"g1", "l1"}


def test_valid_gateway_bank_relationship():
    """Test 4: Valid gateway↔bank relationship"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert set(results[0].transaction_ids) == {"g1", "b1"}


def test_exact_three_source_reconciliation():
    """Test 5: Exact three-source reconciliation"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        order_id="ORD123",
    )
    ledger_txn = Transaction(
        txn_id="l1",
        source=TransactionSource.LEDGER,
        reference_number="REF456",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        order_id="ORD123",
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {
            TransactionSource.GATEWAY: [gateway_txn],
            TransactionSource.LEDGER: [ledger_txn],
            TransactionSource.BANK: [bank_txn],
        }
    )
    results = matcher.match_all()

    # Should produce a single consolidated true 3-way match (gateway + ledger + bank)
    assert len(results) == 1
    assert set(results[0].transaction_ids) == {"g1", "l1", "b1"}
    assert results[0].evidence.get("three_way_match") is True


def test_different_references_do_not_automatically_match():
    """Test 6: Different references do not automatically match"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR456",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    # Should match by amount+date since it's unique
    assert len(results) == 1
    assert results[0].confidence == AMOUNT_DATE_UNIQUE_CONFIDENCE


def test_same_amount_alone_does_not_force_match():
    """Test 7: Same amount alone does not force match"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR456",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 10),  # Outside date window
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    # Should not match - outside date window
    assert len(results) == 0


def test_multiple_candidates_remain_unresolved():
    """Test 8: Multiple candidates remain unresolved/ambiguous"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn1 = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number=None,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn2 = Transaction(
        txn_id="b2",
        source=TransactionSource.BANK,
        reference_number=None,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 3),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn1, bank_txn2]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == AMBIGUOUS_CONFIDENCE


def test_duplicate_records_are_detected():
    """Test 9: Duplicate records are detected"""
    gateway_txn1 = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    gateway_txn2 = Transaction(
        txn_id="g2",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher({TransactionSource.GATEWAY: [gateway_txn1, gateway_txn2]})
    matcher.match_all()

    assert len(matcher.duplicates_detected) == 1
    assert matcher.duplicates_detected[0]["count"] == 2


def test_date_window_matching():
    """Test 10: Date-window matching (±3 days) behaves correctly"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number=None,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number=None,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 4),  # Exactly 3 days later
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == AMOUNT_DATE_UNIQUE_CONFIDENCE


def test_currency_mismatch_rejected():
    """Test 11: Currency mismatch is rejected"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="EUR",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    # Should not match due to currency mismatch
    assert len(results) == 0


def test_amount_conflict_handled_safely():
    """Test 12: Amount conflict handled safely"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("200.00"),  # Different amount
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    # Should not match due to amount conflict
    assert len(results) == 0


def test_deterministic_results_are_reproducible():
    """Test 13: Deterministic results are reproducible"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher1 = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results1 = matcher1.match_all()

    matcher2 = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results2 = matcher2.match_all()

    assert len(results1) == len(results2)
    assert results1[0].confidence == results2[0].confidence
    assert results1[0].transaction_ids == results2[0].transaction_ids


def test_fee_refund_calculation():
    """Test 15: Fee/refund calculation with expected bank amount"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        fee=Decimal("2.50"),
        tax=Decimal("5.00"),
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("92.50"),  # 100 - 2.5 - 5
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == EXACT_UTR_CONFIDENCE


def test_partial_refund_scenario():
    """Test 16: Partial refund scenario handled correctly"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
        metadata={"refund_amount": "20.00"},
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("80.00"),  # 100 - 20 refund
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == EXACT_UTR_CONFIDENCE


def test_wrong_reference_scenario():
    """Test 17: Wrong reference scenario detected"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR456",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    # Should match by amount+date, not by reference
    assert len(results) == 1
    assert results[0].confidence == AMOUNT_DATE_UNIQUE_CONFIDENCE


def test_ambiguous_scenario_remains_unresolved():
    """Test 18: Ambiguous scenario remains unresolved"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn1 = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number=None,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn2 = Transaction(
        txn_id="b2",
        source=TransactionSource.BANK,
        reference_number=None,
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 3),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn1, bank_txn2]}
    )
    results = matcher.match_all()

    assert len(results) == 1
    assert results[0].confidence == AMBIGUOUS_CONFIDENCE


def test_unmatched_transactions_have_no_match_result():
    """Test 19: Unmatched transactions have no MatchResult"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR456",
        amount=Decimal("200.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 10),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    # No match due to amount and date differences
    assert len(results) == 0


def test_confidence_values_match_documented_policy():
    """Test 20: Confidence values match documented policy"""
    gateway_txn = Transaction(
        txn_id="g1",
        source=TransactionSource.GATEWAY,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 1),
        status=TransactionStatus.COMPLETED,
    )
    bank_txn = Transaction(
        txn_id="b1",
        source=TransactionSource.BANK,
        reference_number="UTR123",
        amount=Decimal("100.00"),
        currency="USD",
        timestamp=datetime(2024, 1, 2),
        status=TransactionStatus.COMPLETED,
    )

    matcher = DeterministicMatcher(
        {TransactionSource.GATEWAY: [gateway_txn], TransactionSource.BANK: [bank_txn]}
    )
    results = matcher.match_all()

    assert results[0].confidence == EXACT_UTR_CONFIDENCE
    assert EXACT_UTR_CONFIDENCE == Decimal("0.98")
    assert EXACT_ORDER_ID_CONFIDENCE == Decimal("0.95")
    assert EXACT_TXN_REF_CONFIDENCE == Decimal("0.97")
    assert AMOUNT_DATE_UNIQUE_CONFIDENCE == Decimal("0.80")
    assert AMBIGUOUS_CONFIDENCE == Decimal("0.30")
