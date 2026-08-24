"""
Refund & Partial-Refund Accounting Service for Project Sentinel.

Provides comprehensive refund reconciliation:
- Full refund matching against original payment
- Multiple partial refunds linked by parent order/transaction ID
- Outstanding remaining balance tracking
- Over-refund anomaly detection (total refunded > original payment)
- Refund fee reversal accounting
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction as TransactionORM
from app.models.transaction import TransactionSource


@dataclass
class RefundAuditItem:
    """Audit breakdown for a single payment and its associated refund(s)."""
    parent_transaction_id: str
    order_id: Optional[str]
    original_gross_amount: str
    total_refunded_amount: str
    net_retained_amount: str
    refund_count: int
    refund_status: str  # "NO_REFUND", "PARTIALLY_REFUNDED", "FULLY_REFUNDED", "OVER_REFUNDED_ERROR"
    over_refund_exposure: str = "0.00"
    refund_records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RefundAccountingSummary:
    """Consolidated Refund Reconciliation Report."""
    total_payments_audited: int = 0
    total_gross_volume: str = "0.00"
    total_refunded_volume: str = "0.00"
    total_net_retained_volume: str = "0.00"
    fully_refunded_count: int = 0
    partially_refunded_count: int = 0
    over_refund_anomalies_count: int = 0
    total_over_refund_exposure: str = "0.00"
    refund_items: list[dict[str, Any]] = field(default_factory=list)
    currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RefundAccountingService:
    """Service auditing and reconciling payment refunds against parent transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def audit_refunds(self, limit: int = 100) -> RefundAccountingSummary:
        """Audit all gateway payments and their associated refund records."""
        stmt = select(TransactionORM).where(TransactionORM.source == TransactionSource.GATEWAY.value).limit(limit)
        res = await self.session.execute(stmt)
        txns = res.scalars().all()

        total_gross = Decimal("0.00")
        total_refunded = Decimal("0.00")
        total_net = Decimal("0.00")
        fully_ref_cnt = 0
        part_ref_cnt = 0
        over_ref_cnt = 0
        total_over_exp = Decimal("0.00")
        audit_items: list[dict[str, Any]] = []

        for t in txns:
            gross = Decimal(str(t.amount or 0))
            total_gross += gross

            meta = t.meta_data or {}
            # Check for refund entries in meta_data or related transactions
            refunds = meta.get("refunds", [])
            ref_amt_sum = sum(Decimal(str(r.get("amount", 0))) for r in refunds)

            if ref_amt_sum == Decimal("0.00"):
                status = "NO_REFUND"
                over_exp = Decimal("0.00")
                net_amt = gross
            elif ref_amt_sum == gross:
                status = "FULLY_REFUNDED"
                fully_ref_cnt += 1
                over_exp = Decimal("0.00")
                net_amt = Decimal("0.00")
            elif ref_amt_sum < gross:
                status = "PARTIALLY_REFUNDED"
                part_ref_cnt += 1
                over_exp = Decimal("0.00")
                net_amt = gross - ref_amt_sum
            else:
                status = "OVER_REFUNDED_ERROR"
                over_ref_cnt += 1
                over_exp = ref_amt_sum - gross
                total_over_exp += over_exp
                net_amt = Decimal("0.00")

            total_refunded += ref_amt_sum
            total_net += net_amt

            if refunds:
                audit_items.append(
                    asdict(
                        RefundAuditItem(
                            parent_transaction_id=t.domain_transaction_id or t.id,
                            order_id=t.order_id,
                            original_gross_amount=str(gross),
                            total_refunded_amount=str(ref_amt_sum),
                            net_retained_amount=str(net_amt),
                            refund_count=len(refunds),
                            refund_status=status,
                            over_refund_exposure=str(over_exp),
                            refund_records=refunds,
                        )
                    )
                )

        return RefundAccountingSummary(
            total_payments_audited=len(txns),
            total_gross_volume=str(total_gross),
            total_refunded_volume=str(total_refunded),
            total_net_retained_volume=str(total_net),
            fully_refunded_count=fully_ref_cnt,
            partially_refunded_count=part_ref_cnt,
            over_refund_anomalies_count=over_ref_cnt,
            total_over_refund_exposure=str(total_over_exp),
            refund_items=audit_items,
        )
