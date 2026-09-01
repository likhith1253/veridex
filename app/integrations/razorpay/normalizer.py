"""
Razorpay Entity Normalizer for Project Sentinel.

Transforms raw Razorpay API and Webhook payloads into canonical Sentinel Domain Models:
- Converts paise integer amounts to Decimal INR values
- Converts Unix epoch timestamps into UTC timezone-aware datetimes
- Extracts and standardizes MDR fees, GST tax line items, UTRs, and RRNs
- Accurately maps payment and settlement lifecycle statuses
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import logging
from typing import Any, Optional

from app.models.transaction import Transaction, TransactionSource, TransactionStatus

logger = logging.getLogger(__name__)


class RazorpayNormalizer:
    """Normalizes Razorpay payment, order, and settlement payloads into canonical Transaction models."""

    PAYMENT_STATUS_MAP = {
        "captured": TransactionStatus.COMPLETED,
        "paid": TransactionStatus.COMPLETED,
        "authorized": TransactionStatus.PENDING,
        "created": TransactionStatus.PENDING,
        "pending": TransactionStatus.PENDING,
        "failed": TransactionStatus.FAILED,
        "refunded": TransactionStatus.REFUNDED,
        "partially_refunded": TransactionStatus.PARTIALLY_REFUNDED,
    }

    SETTLEMENT_STATUS_MAP = {
        "processed": TransactionStatus.COMPLETED,
        "settled": TransactionStatus.COMPLETED,
        "created": TransactionStatus.PENDING,
        "pending": TransactionStatus.PENDING,
        "failed": TransactionStatus.FAILED,
    }

    @classmethod
    def _paise_to_rupees(cls, paise_val: Any) -> Decimal:
        """Convert paise integer/string to INR Decimal."""
        if paise_val is None:
            return Decimal("0.00")
        try:
            return Decimal(str(paise_val)) / Decimal("100")
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @classmethod
    def _epoch_to_datetime(cls, epoch_val: Any) -> datetime:
        """Convert Unix epoch seconds into a UTC datetime."""
        if not epoch_val:
            return datetime.now(timezone.utc)
        try:
            ts = int(epoch_val)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    @classmethod
    def _extract_raw_entity(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Extract entity dict from nested payload structures safely."""
        if not isinstance(data, dict):
            return {}
        # If payload wraps with {"entity": {...}}
        entity = data.get("entity")
        if isinstance(entity, dict):
            return entity
        # If payload wraps with {"payment": {"entity": {...}}}
        if "payment" in data and isinstance(data["payment"], dict):
            p_entity = data["payment"].get("entity")
            if isinstance(p_entity, dict):
                return p_entity
        # If payload wraps with {"settlement": {"entity": {...}}}
        if "settlement" in data and isinstance(data["settlement"], dict):
            s_entity = data["settlement"].get("entity")
            if isinstance(s_entity, dict):
                return s_entity
        return data

    @classmethod
    def normalize_payment(cls, payment: dict[str, Any]) -> Transaction:
        """Normalize a Razorpay Payment entity to a canonical Sentinel Transaction."""
        raw = cls._extract_raw_entity(payment)
        payment_id = str(raw.get("id") or "pay_unknown")
        order_id = raw.get("order_id")
        amount = cls._paise_to_rupees(raw.get("amount", 0))
        if amount <= 0:
            amount = Decimal("1.00")  # Sentinel requires gt=0

        currency = str(raw.get("currency") or "INR").upper()
        raw_status = str(raw.get("status") or "created").lower()
        status = cls.PAYMENT_STATUS_MAP.get(raw_status, TransactionStatus.PENDING)
        dt = cls._epoch_to_datetime(raw.get("created_at"))

        # Fee & Tax breakdown
        fee = cls._paise_to_rupees(raw.get("fee")) if raw.get("fee") is not None else None
        tax = cls._paise_to_rupees(raw.get("tax")) if raw.get("tax") is not None else None

        # Reference numbers (RRN or UTR from acquirer data)
        acquirer_data = raw.get("acquirer_data") or {}
        reference_number = acquirer_data.get("rrn") or acquirer_data.get("utr") or acquirer_data.get("bank_transaction_id") or payment_id

        # Method and narration
        method = raw.get("method") or "unknown"
        narration = f"Razorpay payment {payment_id} via {method}"
        if order_id:
            narration += f" for order {order_id}"

        metadata = {
            "gateway": "razorpay",
            "method": method,
            "email": raw.get("email"),
            "contact": raw.get("contact"),
            "notes": raw.get("notes") or {},
            "raw_status": raw_status,
        }

        return Transaction(
            txn_id=payment_id,
            source=TransactionSource.GATEWAY,
            reference_number=str(reference_number),
            amount=amount,
            currency=currency,
            timestamp=dt,
            narration=narration,
            fee=fee,
            tax=tax,
            status=status,
            order_id=str(order_id) if order_id else None,
            metadata=metadata,
        )

    @classmethod
    def normalize_settlement(cls, settlement: dict[str, Any]) -> Transaction:
        """Normalize a Razorpay Settlement entity into a canonical Sentinel Transaction."""
        raw = cls._extract_raw_entity(settlement)
        settlement_id = str(raw.get("id") or "setl_unknown")
        amount = cls._paise_to_rupees(raw.get("amount", 0))
        if amount <= 0:
            amount = Decimal("1.00")

        currency = str(raw.get("currency") or "INR").upper()
        raw_status = str(raw.get("status") or "processed").lower()
        status = cls.SETTLEMENT_STATUS_MAP.get(raw_status, TransactionStatus.COMPLETED)
        dt = cls._epoch_to_datetime(raw.get("created_at"))

        fee = cls._paise_to_rupees(raw.get("fees")) if raw.get("fees") is not None else None
        tax = cls._paise_to_rupees(raw.get("tax")) if raw.get("tax") is not None else None
        utr = raw.get("utr") or settlement_id

        metadata = {
            "gateway": "razorpay",
            "type": "settlement",
            "utr": utr,
            "raw_status": raw_status,
        }

        return Transaction(
            txn_id=settlement_id,
            source=TransactionSource.GATEWAY,
            reference_number=str(utr),
            amount=amount,
            currency=currency,
            timestamp=dt,
            narration=f"Razorpay settlement payout {settlement_id} (UTR: {utr})",
            fee=fee,
            tax=tax,
            status=status,
            order_id=None,
            metadata=metadata,
        )
