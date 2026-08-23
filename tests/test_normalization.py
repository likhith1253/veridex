import csv
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.transaction import TransactionSource, TransactionStatus
from app.services.normalization import (
    BankNormalizer,
    GatewayNormalizer,
    InvalidValueError,
    LedgerNormalizer,
    MissingColumnError,
    NormalizationError,
    NormalizationService,
)


def test_valid_gateway_row():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "SETTLED",
    }

    txn = GatewayNormalizer.normalize_row(row)

    assert txn.txn_id == "TXN00000001"
    assert txn.source == TransactionSource.GATEWAY
    assert txn.amount == Decimal("1000.00")
    assert txn.currency == "INR"
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.order_id == "ORD00000001"
    assert txn.reference_number == "UTR1234567890"
    assert txn.fee == Decimal("20.00")
    assert txn.tax == Decimal("180.00")


def test_valid_ledger_row():
    row = {
        "order_id": "ORD00000001",
        "customer_id": "CUST123456",
        "transaction_amount": "1000.00",
        "refund_amount": "0.00",
        "order_date": "2024-01-01T00:00:00",
        "payment_status": "PAID",
        "currency": "INR",
        "internal_reference": "TXN00000001",
    }

    txn = LedgerNormalizer.normalize_row(row)

    assert txn.txn_id == "ORD00000001"
    assert txn.source == TransactionSource.LEDGER
    assert txn.amount == Decimal("1000.00")
    assert txn.currency == "INR"
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.order_id == "ORD00000001"
    assert txn.reference_number == "TXN00000001"


def test_valid_bank_row():
    row = {
        "bank_transaction_id": "BANK00000001",
        "utr": "UTR1234567890",
        "credit_amount": "1000.00",
        "debit_amount": "0.00",
        "value_date": "2024-01-01T00:00:00",
        "narration": "SETTLEMENT UTR1234567890",
        "currency": "INR",
    }

    txn = BankNormalizer.normalize_row(row)

    assert txn.txn_id == "BANK00000001"
    assert txn.source == TransactionSource.BANK
    assert txn.amount == Decimal("1000.00")
    assert txn.currency == "INR"
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.reference_number == "UTR1234567890"
    assert txn.narration == "SETTLEMENT UTR1234567890"


def test_decimal_conversion():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.50",
        "fee": "20.10",
        "tax": "180.09",
        "net_amount": "1000.50",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "SETTLED",
    }

    txn = GatewayNormalizer.normalize_row(row)

    assert txn.amount == Decimal("1000.50")
    assert txn.fee == Decimal("20.10")
    assert txn.tax == Decimal("180.09")
    assert isinstance(txn.amount, Decimal)


def test_date_time_conversion():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-15T12:30:45",
        "currency": "INR",
        "status": "SETTLED",
    }

    txn = GatewayNormalizer.normalize_row(row)

    assert txn.timestamp == datetime(2024, 1, 15, 12, 30, 45)
    assert isinstance(txn.timestamp, datetime)


def test_source_assignment():
    gateway_row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "SETTLED",
    }

    ledger_row = {
        "order_id": "ORD00000001",
        "customer_id": "CUST123456",
        "transaction_amount": "1000.00",
        "refund_amount": "0.00",
        "order_date": "2024-01-01T00:00:00",
        "payment_status": "PAID",
        "currency": "INR",
        "internal_reference": "TXN00000001",
    }

    bank_row = {
        "bank_transaction_id": "BANK00000001",
        "utr": "UTR1234567890",
        "credit_amount": "1000.00",
        "debit_amount": "0.00",
        "value_date": "2024-01-01T00:00:00",
        "narration": "SETTLEMENT",
        "currency": "INR",
    }

    gateway_txn = GatewayNormalizer.normalize_row(gateway_row)
    ledger_txn = LedgerNormalizer.normalize_row(ledger_row)
    bank_txn = BankNormalizer.normalize_row(bank_row)

    assert gateway_txn.source == TransactionSource.GATEWAY
    assert ledger_txn.source == TransactionSource.LEDGER
    assert bank_txn.source == TransactionSource.BANK


def test_required_column_validation_gateway():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
    }

    with pytest.raises(MissingColumnError):
        GatewayNormalizer.normalize_row(row)


def test_required_column_validation_ledger():
    row = {
        "order_id": "ORD00000001",
        "customer_id": "CUST123456",
        "transaction_amount": "1000.00",
        "refund_amount": "0.00",
        "order_date": "2024-01-01T00:00:00",
        "payment_status": "PAID",
        "currency": "INR",
    }

    with pytest.raises(MissingColumnError):
        LedgerNormalizer.normalize_row(row)


def test_required_column_validation_bank():
    row = {
        "bank_transaction_id": "BANK00000001",
        "utr": "UTR1234567890",
        "credit_amount": "1000.00",
        "debit_amount": "0.00",
        "value_date": "2024-01-01T00:00:00",
        "narration": "SETTLEMENT",
    }

    with pytest.raises(MissingColumnError):
        BankNormalizer.normalize_row(row)


def test_malformed_amount_handling():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "invalid",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "SETTLED",
    }

    with pytest.raises(InvalidValueError):
        GatewayNormalizer.normalize_row(row)


def test_malformed_date_handling():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "invalid-date",
        "currency": "INR",
        "status": "SETTLED",
    }

    with pytest.raises(InvalidValueError):
        GatewayNormalizer.normalize_row(row)


def test_optional_fields_gateway():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "",
        "tax": "",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "SETTLED",
    }

    txn = GatewayNormalizer.normalize_row(row)

    assert txn.fee is None
    assert txn.tax is None


def test_normalization_of_references():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "SETTLED",
    }

    txn = GatewayNormalizer.normalize_row(row)

    assert txn.reference_number == "UTR1234567890"
    assert isinstance(txn.reference_number, str)


def test_gateway_csv_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "gateway.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "settlement_id",
                    "transaction_id",
                    "order_id",
                    "utr",
                    "gross_amount",
                    "fee",
                    "tax",
                    "net_amount",
                    "settlement_date",
                    "currency",
                    "status",
                ]
            )
            writer.writerow(
                [
                    "STL00000001",
                    "TXN00000001",
                    "ORD00000001",
                    "UTR1234567890",
                    "1000.00",
                    "20.00",
                    "180.00",
                    "1000.00",
                    "2024-01-01T00:00:00",
                    "INR",
                    "SETTLED",
                ]
            )

        transactions = GatewayNormalizer.load_csv(filepath)

        assert len(transactions) == 1
        assert transactions[0].txn_id == "TXN00000001"
        assert transactions[0].source == TransactionSource.GATEWAY


def test_ledger_csv_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "ledger.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "order_id",
                    "customer_id",
                    "transaction_amount",
                    "refund_amount",
                    "order_date",
                    "payment_status",
                    "currency",
                    "internal_reference",
                ]
            )
            writer.writerow(
                [
                    "ORD00000001",
                    "CUST123456",
                    "1000.00",
                    "0.00",
                    "2024-01-01T00:00:00",
                    "PAID",
                    "INR",
                    "TXN00000001",
                ]
            )

        transactions = LedgerNormalizer.load_csv(filepath)

        assert len(transactions) == 1
        assert transactions[0].txn_id == "ORD00000001"
        assert transactions[0].source == TransactionSource.LEDGER


def test_bank_csv_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "bank.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["bank_transaction_id", "utr", "credit_amount", "debit_amount", "value_date", "narration", "currency"]
            )
            writer.writerow(
                ["BANK00000001", "UTR1234567890", "1000.00", "0.00", "2024-01-01T00:00:00", "SETTLEMENT", "INR"]
            )

        transactions = BankNormalizer.load_csv(filepath)

        assert len(transactions) == 1
        assert transactions[0].txn_id == "BANK00000001"
        assert transactions[0].source == TransactionSource.BANK


def test_normalization_service_load_gateway():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "gateway.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "settlement_id",
                    "transaction_id",
                    "order_id",
                    "utr",
                    "gross_amount",
                    "fee",
                    "tax",
                    "net_amount",
                    "settlement_date",
                    "currency",
                    "status",
                ]
            )
            writer.writerow(
                [
                    "STL00000001",
                    "TXN00000001",
                    "ORD00000001",
                    "UTR1234567890",
                    "1000.00",
                    "20.00",
                    "180.00",
                    "1000.00",
                    "2024-01-01T00:00:00",
                    "INR",
                    "SETTLED",
                ]
            )

        transactions = NormalizationService.load_gateway(filepath)

        assert len(transactions) == 1
        assert transactions[0].source == TransactionSource.GATEWAY


def test_normalization_service_load_ledger():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "ledger.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "order_id",
                    "customer_id",
                    "transaction_amount",
                    "refund_amount",
                    "order_date",
                    "payment_status",
                    "currency",
                    "internal_reference",
                ]
            )
            writer.writerow(
                [
                    "ORD00000001",
                    "CUST123456",
                    "1000.00",
                    "0.00",
                    "2024-01-01T00:00:00",
                    "PAID",
                    "INR",
                    "TXN00000001",
                ]
            )

        transactions = NormalizationService.load_ledger(filepath)

        assert len(transactions) == 1
        assert transactions[0].source == TransactionSource.LEDGER


def test_normalization_service_load_bank():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "bank.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["bank_transaction_id", "utr", "credit_amount", "debit_amount", "value_date", "narration", "currency"]
            )
            writer.writerow(
                ["BANK00000001", "UTR1234567890", "1000.00", "0.00", "2024-01-01T00:00:00", "SETTLEMENT", "INR"]
            )

        transactions = NormalizationService.load_bank(filepath)

        assert len(transactions) == 1
        assert transactions[0].source == TransactionSource.BANK


def test_normalization_service_load_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        gateway_path = Path(tmpdir) / "gateway.csv"
        ledger_path = Path(tmpdir) / "ledger.csv"
        bank_path = Path(tmpdir) / "bank.csv"

        with open(gateway_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "settlement_id",
                    "transaction_id",
                    "order_id",
                    "utr",
                    "gross_amount",
                    "fee",
                    "tax",
                    "net_amount",
                    "settlement_date",
                    "currency",
                    "status",
                ]
            )
            writer.writerow(
                [
                    "STL00000001",
                    "TXN00000001",
                    "ORD00000001",
                    "UTR1234567890",
                    "1000.00",
                    "20.00",
                    "180.00",
                    "1000.00",
                    "2024-01-01T00:00:00",
                    "INR",
                    "SETTLED",
                ]
            )

        with open(ledger_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "order_id",
                    "customer_id",
                    "transaction_amount",
                    "refund_amount",
                    "order_date",
                    "payment_status",
                    "currency",
                    "internal_reference",
                ]
            )
            writer.writerow(
                [
                    "ORD00000001",
                    "CUST123456",
                    "1000.00",
                    "0.00",
                    "2024-01-01T00:00:00",
                    "PAID",
                    "INR",
                    "TXN00000001",
                ]
            )

        with open(bank_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["bank_transaction_id", "utr", "credit_amount", "debit_amount", "value_date", "narration", "currency"]
            )
            writer.writerow(
                ["BANK00000001", "UTR1234567890", "1000.00", "0.00", "2024-01-01T00:00:00", "SETTLEMENT", "INR"]
            )

        all_transactions = NormalizationService.load_all(gateway_path, ledger_path, bank_path)

        assert TransactionSource.GATEWAY in all_transactions
        assert TransactionSource.LEDGER in all_transactions
        assert TransactionSource.BANK in all_transactions
        assert len(all_transactions[TransactionSource.GATEWAY]) == 1
        assert len(all_transactions[TransactionSource.LEDGER]) == 1
        assert len(all_transactions[TransactionSource.BANK]) == 1


def test_simulator_data_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        from simulator.generator import generate_default

        output_path = Path(tmpdir)
        generate_default(output_path)

        gateway_path = output_path / "gateway.csv"
        ledger_path = output_path / "ledger.csv"
        bank_path = output_path / "bank.csv"

        gateway_txns = NormalizationService.load_gateway(gateway_path)
        ledger_txns = NormalizationService.load_ledger(ledger_path)
        bank_txns = NormalizationService.load_bank(bank_path)

        assert len(gateway_txns) > 0
        assert len(ledger_txns) > 0
        assert len(bank_txns) > 0

        assert all(t.source == TransactionSource.GATEWAY for t in gateway_txns)
        assert all(t.source == TransactionSource.LEDGER for t in ledger_txns)
        assert all(t.source == TransactionSource.BANK for t in bank_txns)

        assert all(t.currency == "INR" for t in gateway_txns)
        assert all(t.currency == "INR" for t in ledger_txns)
        assert all(t.currency == "INR" for t in bank_txns)


def test_bank_row_with_debit():
    row = {
        "bank_transaction_id": "BANK00000001",
        "utr": "UTR1234567890",
        "credit_amount": "0.00",
        "debit_amount": "1000.00",
        "value_date": "2024-01-01T00:00:00",
        "narration": "WITHDRAWAL",
        "currency": "INR",
    }

    txn = BankNormalizer.normalize_row(row)

    assert txn.amount == Decimal("1000.00")


def test_bank_row_zero_amounts():
    row = {
        "bank_transaction_id": "BANK00000001",
        "utr": "UTR1234567890",
        "credit_amount": "0.00",
        "debit_amount": "0.00",
        "value_date": "2024-01-01T00:00:00",
        "narration": "SETTLEMENT",
        "currency": "INR",
    }

    with pytest.raises(InvalidValueError):
        BankNormalizer.normalize_row(row)


def test_gateway_status_normalization():
    statuses = ["SETTLED", "PENDING", "FAILED", "REFUNDED"]
    for status in statuses:
        row = {
            "settlement_id": "STL00000001",
            "transaction_id": "TXN00000001",
            "order_id": "ORD00000001",
            "utr": "UTR1234567890",
            "gross_amount": "1000.00",
            "fee": "20.00",
            "tax": "180.00",
            "net_amount": "1000.00",
            "settlement_date": "2024-01-01T00:00:00",
            "currency": "INR",
            "status": status,
        }

        txn = GatewayNormalizer.normalize_row(row)
        assert txn.status is not None


def test_ledger_status_normalization():
    statuses = ["PAID", "PENDING", "FAILED", "REFUNDED", "PARTIALLY_REFUNDED"]
    for status in statuses:
        row = {
            "order_id": "ORD00000001",
            "customer_id": "CUST123456",
            "transaction_amount": "1000.00",
            "refund_amount": "0.00",
            "order_date": "2024-01-01T00:00:00",
            "payment_status": status,
            "currency": "INR",
            "internal_reference": "TXN00000001",
        }

        txn = LedgerNormalizer.normalize_row(row)
        assert txn.status is not None


def test_invalid_gateway_status():
    row = {
        "settlement_id": "STL00000001",
        "transaction_id": "TXN00000001",
        "order_id": "ORD00000001",
        "utr": "UTR1234567890",
        "gross_amount": "1000.00",
        "fee": "20.00",
        "tax": "180.00",
        "net_amount": "1000.00",
        "settlement_date": "2024-01-01T00:00:00",
        "currency": "INR",
        "status": "INVALID_STATUS",
    }

    with pytest.raises(InvalidValueError):
        GatewayNormalizer.normalize_row(row)


def test_csv_load_with_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "gateway.csv"
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "settlement_id",
                    "transaction_id",
                    "order_id",
                    "utr",
                    "gross_amount",
                    "fee",
                    "tax",
                    "net_amount",
                    "settlement_date",
                    "currency",
                    "status",
                ]
            )
            writer.writerow(
                [
                    "STL00000001",
                    "TXN00000001",
                    "ORD00000001",
                    "UTR1234567890",
                    "1000.00",
                    "invalid",
                    "180.00",
                    "1000.00",
                    "2024-01-01T00:00:00",
                    "INR",
                    "SETTLED",
                ]
            )

        with pytest.raises(NormalizationError):
            GatewayNormalizer.load_csv(filepath)
