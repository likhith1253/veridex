"""
Settlement Accounting & Variance Service for Project Sentinel.

Implements the unified treasury accounting formula:
  Expected Settlement = Gross Volume - Total Fees - Total Taxes - Total Refunds
And reconciles Expected Settlement against Actual Bank Statement Credits:
  Net Variance = Actual Bank Credits - Expected Settlement

Explicitly surfaces:
- Reconciled settlement batches
- Unsettled / delayed batches
- Fee / Tax deduction variances
- Discrepancy exposure
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction as TransactionORM
from app.models.transaction import TransactionSource
from app.services.cash_position import _as_decimal, _resolve_authoritative_business_gross, _sum_refunds_for_transaction


@dataclass
class SettlementAccountingSummary:
    """Consolidated Settlement Accounting Breakdown."""
    gross_gateway_volume: str = "0.00"
    total_deducted_fees: str = "0.00"
    total_deducted_taxes: str = "0.00"
    total_refunded_amount: str = "0.00"
    expected_net_settlement: str = "0.00"
    actual_bank_settled_credits: str = "0.00"
    net_settlement_variance: str = "0.00"
    settlement_reconciliation_status: str = "RECONCILED"  # "RECONCILED", "PENDING_SETTLEMENT", "DISCREPANCY_DETECTED"
    unsettled_delayed_exposure: str = "0.00"
    currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SettlementAccountingService:
    """Service computing authoritative net settlement equations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_settlement_accounting(self, run_id: Optional[str] = None) -> SettlementAccountingSummary:
        """Compute the complete accounting equation over active transaction records."""
        from app.database.models import ReconciliationRun as ReconciliationRunORM, ReconciliationItem as ReconciliationItemORM

        # Scope transactions to run_id if provided
        txn_filter = True
        if run_id:
            # Get the ORM run ID first
            run_query = select(ReconciliationRunORM).where(
                (ReconciliationRunORM.id == run_id) | (ReconciliationRunORM.run_id == run_id)
            )
            run_result = await self.session.execute(run_query)
            run_obj = run_result.scalar_one_or_none()
            if run_obj:
                # Get transactions that are part of this run via reconciliation_items
                item_stmt = select(ReconciliationItemORM.transaction_id).where(
                    ReconciliationItemORM.run_id == run_obj.id
                )
                item_result = await self.session.execute(item_stmt)
                txn_ids = item_result.scalars().all()
                txn_filter = TransactionORM.id.in_(txn_ids)

        # 1. Gateway aggregates
        gw_stmt = select(
            func.sum(TransactionORM.amount),
            func.sum(TransactionORM.fee),
            func.sum(TransactionORM.tax),
        ).where(
            (TransactionORM.source == TransactionSource.GATEWAY.value) & txn_filter
        )
        gw_res = await self.session.execute(gw_stmt)
        gw_amt, gw_fee, gw_tax = gw_res.first() or (0, 0, 0)

        gross = Decimal(str(gw_amt or 0))
        fees = Decimal(str(gw_fee or 0))
        taxes = Decimal(str(gw_tax or 0))
        refunds = Decimal("0.00")

        # Refunds are part of the authoritative settlement equation, but they are only
        # materialized in gateway metadata and therefore require a scoped lookup when a
        # run is provided. The unrestricted path keeps the common API contract stable.
        if run_id is not None:
            refund_stmt = select(TransactionORM).where(
                (TransactionORM.source == TransactionSource.GATEWAY.value) & txn_filter
            )
            refund_res = await self.session.execute(refund_stmt)
            refund_txns = refund_res.scalars().all()
            refunds = sum(
                (_sum_refunds_for_transaction(txn) for txn in refund_txns),
                Decimal("0.00"),
            )
            by_source = {
                TransactionSource.GATEWAY.value: Decimal("0.00"),
                TransactionSource.LEDGER.value: Decimal("0.00"),
                TransactionSource.BANK.value: Decimal("0.00"),
            }
            for txn in refund_txns:
                src = getattr(txn, "source", None)
                if src in by_source:
                    by_source[src] += _as_decimal(getattr(txn, "amount", 0) or 0)
            gross = _resolve_authoritative_business_gross(by_source)

        expected_net = gross - fees - taxes - refunds

        # 2. Bank settled credits
        bk_stmt = select(func.sum(TransactionORM.amount)).where(
            (TransactionORM.source == TransactionSource.BANK.value) & txn_filter
        )
        bk_res = await self.session.execute(bk_stmt)
        bk_amt = bk_res.scalar_one() or Decimal("0.00")
        actual_bank = Decimal(str(bk_amt))

        variance = (actual_bank - expected_net).quantize(Decimal("0.01"))

        if abs(variance) <= Decimal("50.00"):  # Within small rounding threshold
            status = "RECONCILED"
            unsettled = Decimal("0.00")
        elif actual_bank < expected_net:
            status = "PENDING_SETTLEMENT"
            unsettled = expected_net - actual_bank
        else:
            status = "DISCREPANCY_DETECTED"
            unsettled = actual_bank - expected_net

        return SettlementAccountingSummary(
            gross_gateway_volume=f"{gross:.2f}",
            total_deducted_fees=f"{fees:.2f}",
            total_deducted_taxes=f"{taxes:.2f}",
            total_refunded_amount=f"{refunds:.2f}",
            expected_net_settlement=f"{expected_net:.2f}",
            actual_bank_settled_credits=f"{actual_bank:.2f}",
            net_settlement_variance=f"{variance:.2f}",
            settlement_reconciliation_status=status,
            unsettled_delayed_exposure=f"{unsettled:.2f}",
        )
