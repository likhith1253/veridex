import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from app.models.transaction import Transaction, TransactionSource, TransactionStatus


class NormalizationError(Exception):
    """Base class for normalization errors."""
    pass


class MissingColumnError(NormalizationError):
    """Raised when a required column is missing."""
    pass


class InvalidValueError(NormalizationError):
    """Raised when a value cannot be parsed or is invalid."""
    pass


class GatewayNormalizer:
    """Normalizes gateway CSV data to canonical Transaction model."""

    REQUIRED_COLUMNS = {
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
    }

    STATUS_MAP = {
        "SETTLED": TransactionStatus.COMPLETED,
        "PENDING": TransactionStatus.PENDING,
        "FAILED": TransactionStatus.FAILED,
        "REFUNDED": TransactionStatus.REFUNDED,
    }

    @classmethod
    def normalize_row(cls, row: dict) -> Transaction:
        """Normalize a single gateway CSV row to a Transaction."""
        cls._validate_columns(row)

        try:
            txn_id = row["transaction_id"]
            amount = Decimal(row["gross_amount"])
            currency = row["currency"]
            timestamp = datetime.fromisoformat(row["settlement_date"])
            status = cls._normalize_status(row["status"])
            order_id = row["order_id"]
            reference_number = row["utr"]
            fee = Decimal(row["fee"]) if row["fee"] else None
            tax = Decimal(row["tax"]) if row["tax"] else None

            metadata = {
                "settlement_id": row["settlement_id"],
                "gross_amount": row["gross_amount"],
                "net_amount": row["net_amount"],
            }

            return Transaction(
                txn_id=txn_id,
                source=TransactionSource.GATEWAY,
                reference_number=reference_number,
                amount=amount,
                currency=currency,
                timestamp=timestamp,
                status=status,
                order_id=order_id,
                fee=fee,
                tax=tax,
                metadata=metadata,
            )
        except (InvalidOperation, ValueError) as e:
            raise InvalidValueError(f"Invalid value in row {txn_id}: {e}")

    @classmethod
    def _validate_columns(cls, row: dict) -> None:
        missing = cls.REQUIRED_COLUMNS - set(row.keys())
        if missing:
            raise MissingColumnError(f"Missing required columns: {missing}")

    @classmethod
    def _normalize_status(cls, status: str) -> TransactionStatus:
        normalized = cls.STATUS_MAP.get(status.upper())
        if normalized is None:
            raise InvalidValueError(f"Invalid status: {status}")
        return normalized

    @classmethod
    def load_csv(cls, filepath: Path) -> list[Transaction]:
        """Load and normalize all rows from a gateway CSV file."""
        transactions = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    txn = cls.normalize_row(row)
                    transactions.append(txn)
                except NormalizationError as e:
                    raise NormalizationError(f"Row {reader.line_num}: {e}")
        return transactions


class LedgerNormalizer:
    """Normalizes ledger CSV data to canonical Transaction model."""

    REQUIRED_COLUMNS = {
        "order_id",
        "customer_id",
        "transaction_amount",
        "refund_amount",
        "order_date",
        "payment_status",
        "currency",
        "internal_reference",
    }

    STATUS_MAP = {
        "PAID": TransactionStatus.COMPLETED,
        "PENDING": TransactionStatus.PENDING,
        "FAILED": TransactionStatus.FAILED,
        "REFUNDED": TransactionStatus.REFUNDED,
        "PARTIALLY_REFUNDED": TransactionStatus.PARTIALLY_REFUNDED,
    }

    @classmethod
    def normalize_row(cls, row: dict) -> Transaction:
        """Normalize a single ledger CSV row to a Transaction."""
        cls._validate_columns(row)

        try:
            txn_id = row["order_id"]
            amount = Decimal(row["transaction_amount"])
            currency = row["currency"]
            timestamp = datetime.fromisoformat(row["order_date"])
            status = cls._normalize_status(row["payment_status"])
            order_id = row["order_id"]
            reference_number = row["internal_reference"]

            metadata = {
                "customer_id": row["customer_id"],
                "refund_amount": row["refund_amount"],
            }

            return Transaction(
                txn_id=txn_id,
                source=TransactionSource.LEDGER,
                reference_number=reference_number,
                amount=amount,
                currency=currency,
                timestamp=timestamp,
                status=status,
                order_id=order_id,
                metadata=metadata,
            )
        except (InvalidOperation, ValueError) as e:
            raise InvalidValueError(f"Invalid value in row {txn_id}: {e}")

    @classmethod
    def _validate_columns(cls, row: dict) -> None:
        missing = cls.REQUIRED_COLUMNS - set(row.keys())
        if missing:
            raise MissingColumnError(f"Missing required columns: {missing}")

    @classmethod
    def _normalize_status(cls, status: str) -> TransactionStatus:
        normalized = cls.STATUS_MAP.get(status.upper())
        if normalized is None:
            raise InvalidValueError(f"Invalid status: {status}")
        return normalized

    @classmethod
    def load_csv(cls, filepath: Path) -> list[Transaction]:
        """Load and normalize all rows from a ledger CSV file."""
        transactions = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    txn = cls.normalize_row(row)
                    transactions.append(txn)
                except NormalizationError as e:
                    raise NormalizationError(f"Row {reader.line_num}: {e}")
        return transactions


class BankNormalizer:
    """Normalizes bank CSV data to canonical Transaction model."""

    REQUIRED_COLUMNS = {
        "bank_transaction_id",
        "utr",
        "credit_amount",
        "debit_amount",
        "value_date",
        "narration",
        "currency",
    }

    @classmethod
    def normalize_row(cls, row: dict) -> Transaction:
        """Normalize a single bank CSV row to a Transaction."""
        cls._validate_columns(row)

        try:
            txn_id = row["bank_transaction_id"]
            credit_amount = Decimal(row["credit_amount"])
            debit_amount = Decimal(row["debit_amount"])
            currency = row["currency"]
            timestamp = datetime.fromisoformat(row["value_date"])
            narration = row["narration"]
            reference_number = row["utr"]

            amount = credit_amount if credit_amount > 0 else debit_amount
            if amount <= 0:
                raise InvalidValueError(f"Both credit and debit amounts are zero or negative")

            metadata = {
                "credit_amount": row["credit_amount"],
                "debit_amount": row["debit_amount"],
            }

            order_id = row.get("order_id")
            if not order_id and narration:
                import re
                ord_match = re.search(r"\b(ORD[A-Za-z0-9_-]+)\b", narration, re.IGNORECASE)
                if ord_match:
                    order_id = ord_match.group(1)

            return Transaction(
                txn_id=txn_id,
                source=TransactionSource.BANK,
                reference_number=reference_number,
                amount=amount,
                currency=currency,
                timestamp=timestamp,
                narration=narration,
                status=TransactionStatus.COMPLETED,
                order_id=order_id,
                metadata=metadata,
            )
        except (InvalidOperation, ValueError) as e:
            raise InvalidValueError(f"Invalid value in row {txn_id}: {e}")

    @classmethod
    def _validate_columns(cls, row: dict) -> None:
        missing = cls.REQUIRED_COLUMNS - set(row.keys())
        if missing:
            raise MissingColumnError(f"Missing required columns: {missing}")

    @classmethod
    def load_csv(cls, filepath: Path) -> list[Transaction]:
        """Load and normalize all rows from a bank CSV file."""
        transactions = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    txn = cls.normalize_row(row)
                    transactions.append(txn)
                except NormalizationError as e:
                    raise NormalizationError(f"Row {reader.line_num}: {e}")
        return transactions


class NormalizationService:
    """Service-level interface for data normalization."""

    @staticmethod
    def load_gateway(filepath: Path) -> list[Transaction]:
        """Load gateway CSV and return normalized transactions."""
        return GatewayNormalizer.load_csv(filepath)

    @staticmethod
    def load_ledger(filepath: Path) -> list[Transaction]:
        """Load ledger CSV and return normalized transactions."""
        return LedgerNormalizer.load_csv(filepath)

    @staticmethod
    def load_bank(filepath: Path) -> list[Transaction]:
        """Load bank CSV and return normalized transactions."""
        return BankNormalizer.load_csv(filepath)

    @staticmethod
    def load_all(
        gateway_path: Path, ledger_path: Path, bank_path: Path
    ) -> dict[TransactionSource, list[Transaction]]:
        """Load all three sources and return normalized transactions by source."""
        return {
            TransactionSource.GATEWAY: NormalizationService.load_gateway(gateway_path),
            TransactionSource.LEDGER: NormalizationService.load_ledger(ledger_path),
            TransactionSource.BANK: NormalizationService.load_bank(bank_path),
        }
