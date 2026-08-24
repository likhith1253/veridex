"""
Razorpay Test Mode Integration Adapter for Project Sentinel.

Translates Razorpay Payment & Order entities into canonical Sentinel Transactions:
- Payment Webhook payload parsing (payment.captured, payment.failed, order.paid)
- Cryptographic HMAC-SHA256 webhook signature verification
- Safe Test-Mode execution without live API or exposed secrets
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.models.transaction import Transaction, TransactionSource, TransactionStatus

logger = logging.getLogger(__name__)


class RazorpayAdapter:
    """Adapter transforming Razorpay payment & settlement events into Sentinel transactions."""

    def __init__(self, webhook_secret: Optional[str] = None):
        self.webhook_secret = webhook_secret or "rzp_test_secret_sentinel"

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature from Razorpay webhook headers."""
        if not signature or not self.webhook_secret:
            return False
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_payment_event(self, event_payload: dict[str, Any]) -> Transaction:
        """Convert a Razorpay payment entity into a canonical Sentinel Transaction."""
        payment = event_payload.get("payload", {}).get("payment", {}).get("entity", event_payload)
        payment_id = payment.get("id", "pay_test_001")
        order_id = payment.get("order_id", "order_test_001")
        amount_paise = payment.get("amount", 10000)
        currency = payment.get("currency", "INR")
        status_str = payment.get("status", "captured")
        created_at_ts = payment.get("created_at", int(datetime.now(timezone.utc).timestamp()))
        dt = datetime.fromtimestamp(created_at_ts, tz=timezone.utc)

        amount_inr = Decimal(str(amount_paise)) / Decimal("100")
        status = TransactionStatus.COMPLETED if status_str in ("captured", "paid") else TransactionStatus.PENDING

        return Transaction(
            txn_id=payment_id,
            source=TransactionSource.GATEWAY,
            amount=amount_inr,
            currency=currency,
            timestamp=dt,
            status=status,
            order_id=order_id,
            reference_number=payment.get("acquirer_data", {}).get("rrn") or payment.get("acquirer_data", {}).get("utr"),
            narration=f"Razorpay settlement for {order_id} ({payment_id})",
            metadata={
                "gateway": "razorpay",
                "method": payment.get("method", "upi"),
                "fee": str(Decimal(str(payment.get("fee", 0))) / Decimal("100")),
                "tax": str(Decimal(str(payment.get("tax", 0))) / Decimal("100")),
            },
        )
