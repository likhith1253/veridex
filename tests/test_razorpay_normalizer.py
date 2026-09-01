"""
Unit tests for Razorpay Entity Normalization to Sentinel canonical Transaction models.
"""

from decimal import Decimal
from app.integrations.razorpay.normalizer import RazorpayNormalizer
from app.models.transaction import TransactionSource, TransactionStatus


def test_normalize_payment_success():
    raw_payment = {
        "id": "pay_test_999888",
        "entity": "payment",
        "amount": 105000,  # 1,050.00 INR
        "currency": "INR",
        "status": "captured",
        "order_id": "order_abc_123",
        "method": "upi",
        "fee": 2100,  # 21.00 INR
        "tax": 378,   # 3.78 INR
        "created_at": 1725200000,
        "acquirer_data": {
            "rrn": "424512345678",
            "utr": "UTR1234567890",
        },
        "email": "test@example.com",
    }

    txn = RazorpayNormalizer.normalize_payment(raw_payment)
    assert txn.txn_id == "pay_test_999888"
    assert txn.source == TransactionSource.GATEWAY
    assert txn.amount == Decimal("1050.00")
    assert txn.currency == "INR"
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.order_id == "order_abc_123"
    assert txn.reference_number == "424512345678"
    assert txn.fee == Decimal("21.00")
    assert txn.tax == Decimal("3.78")
    assert txn.metadata["gateway"] == "razorpay"
    assert txn.metadata["method"] == "upi"


def test_normalize_settlement_success():
    raw_settlement = {
        "id": "setl_test_777",
        "entity": "settlement",
        "amount": 5000000,  # 50,000.00 INR
        "currency": "INR",
        "status": "processed",
        "fees": 100000,     # 1,000.00 INR
        "tax": 18000,       # 180.00 INR
        "utr": "AXISN12345678",
        "created_at": 1725200000,
    }

    txn = RazorpayNormalizer.normalize_settlement(raw_settlement)
    assert txn.txn_id == "setl_test_777"
    assert txn.source == TransactionSource.GATEWAY
    assert txn.amount == Decimal("50000.00")
    assert txn.currency == "INR"
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.reference_number == "AXISN12345678"
    assert txn.fee == Decimal("1000.00")
    assert txn.tax == Decimal("180.00")
    assert txn.metadata["type"] == "settlement"
