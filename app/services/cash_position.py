"""
Cash Position Aggregation Service for Project Sentinel.

Calculates real-time financial cash position:
- Expected amount (Authoritative Gateway / Ledger gross orders)
- Received amount (Bank credit settlements confirmed)
- Pending amount (Orders placed but settlement window open)
- Delayed amount (Settlement exceeded normal SLA window)
- Unreconciled amount (Unmatched or exception transactions)
- At-risk amount (High financial exposure exceptions)

Grouped by source, date, settlement status, and exception category.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Exception as ExceptionORM, Transaction as TransactionORM
from app.models.exception_record import ExceptionCategory
from app.models.transaction import TransactionSource


@dataclass
class CashPositionSummary:
    """Consolidated financial cash position summary."""
    expected_amount: Decimal = Decimal("0")  # Retained for backwards compatibility (= expected_gross)
    expected_gross: Decimal = Decimal("0")
    expected_net_settlement: Decimal = Decimal("0")
    received_amount: Decimal = Decimal("0")  # Retained for backwards compatibility (= received_bank_credits)
    received_bank_credits: Decimal = Decimal("0")
    settlement_variance: Decimal = Decimal("0")
    total_deducted_fees: Decimal = Decimal("0")
    total_deducted_taxes: Decimal = Decimal("0")
    total_refunded_amount: Decimal = Decimal("0")
    pending_amount: Decimal = Decimal("0")
    delayed_amount: Decimal = Decimal("0")
    unreconciled_amount: Decimal = Decimal("0")
    at_risk_amount: Decimal = Decimal("0")
    currency: str = "INR"
    breakdown_by_source: dict[str, Decimal] = field(default_factory=dict)
    breakdown_by_category: dict[str, Decimal] = field(default_factory=dict)
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_amount": str(self.expected_amount),
            "expected_gross": str(self.expected_gross),
            "expected_net_settlement": str(self.expected_net_settlement),
            "received_amount": str(self.received_amount),
            "received_bank_credits": str(self.received_bank_credits),
            "settlement_variance": str(self.settlement_variance),
            "total_deducted_fees": str(self.total_deducted_fees),
            "total_deducted_taxes": str(self.total_deducted_taxes),
            "total_refunded_amount": str(self.total_refunded_amount),
            "pending_amount": str(self.pending_amount),
            "delayed_amount": str(self.delayed_amount),
            "unreconciled_amount": str(self.unreconciled_amount),
            "at_risk_amount": str(self.at_risk_amount),
            "currency": self.currency,
            "breakdown_by_source": {k: str(v) for k, v in self.breakdown_by_source.items()},
            "breakdown_by_category": {k: str(v) for k, v in self.breakdown_by_category.items()},
            "as_of": self.as_of.isoformat(),
        }


class CashPositionService:
    """Service calculating grounded cash position from database transactions and exceptions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cash_position(self, run_id: Optional[str] = None) -> CashPositionSummary:
        """Calculate live cash position across all transactions or scoped to a run."""
        # FIX: Scope transactions to the specified run_id for proper batch isolation
        from app.database.models import ReconciliationItem as ReconciliationItemORM, ReconciliationRun as ReconciliationRunORM
        
        # Resolve run ORM ID if provided
        run_orm_id = None
        if run_id:
            r_stmt = select(ReconciliationRunORM).where(
                (ReconciliationRunORM.id == run_id) | (ReconciliationRunORM.run_id == run_id)
            )
            r_res = await self.session.execute(r_stmt)
            r_obj = r_res.scalar_one_or_none()
            if r_obj:
                run_orm_id = r_obj.id
            else:
                run_orm_id = run_id
        
        # 1. Query transactions scoped to the run
        stmt = select(TransactionORM)
        if run_orm_id:
            # Get transactions that are part of this run via reconciliation_items
            item_stmt = select(ReconciliationItemORM.transaction_id).where(
                ReconciliationItemORM.run_id == run_orm_id
            )
            item_result = await self.session.execute(item_stmt)
            txn_ids = item_result.scalars().all()
            stmt = select(TransactionORM).where(TransactionORM.id.in_(txn_ids))
        
        res = await self.session.execute(stmt)
        txns = res.scalars().all()

        received = Decimal("0.00")
        fees = Decimal("0.00")
        taxes = Decimal("0.00")
        refunds = Decimal("0.00")
        by_source: dict[str, Decimal] = {
            TransactionSource.GATEWAY.value: Decimal("0.00"),
            TransactionSource.LEDGER.value: Decimal("0.00"),
            TransactionSource.BANK.value: Decimal("0.00"),
        }

        for t in txns:
            amt = Decimal(str(getattr(t, "amount", 0) or 0))
            src = getattr(t, "source", None)
            if src in by_source:
                by_source[src] += amt

            if src == TransactionSource.GATEWAY.value:
                if getattr(t, "fee", None) is not None:
                    fees += Decimal(str(t.fee))
                if getattr(t, "tax", None) is not None:
                    taxes += Decimal(str(t.tax))
            elif src == TransactionSource.BANK.value:
                received += amt

        # Authoritative gross volume (Gateway volume, fallback to Ledger volume)
        gw_gross = by_source.get(TransactionSource.GATEWAY.value, Decimal("0.00"))
        ld_gross = by_source.get(TransactionSource.LEDGER.value, Decimal("0.00"))
        expected_gross = gw_gross if gw_gross > Decimal("0.00") else ld_gross

        expected_net = expected_gross - fees - taxes - refunds
        variance = (received - expected_net).quantize(Decimal("0.01"))
        pending = max(Decimal("0.00"), expected_net - received)
        tolerance = Decimal("50.00")

        # 2. Query exceptions
        exc_stmt = select(ExceptionORM).where(
            (ExceptionORM.status != "resolved") & (ExceptionORM.resolved == False)
        )
        if run_id:
            exc_stmt = exc_stmt.where(
                (ExceptionORM.run_id == run_id)
            )
        exc_res = await self.session.execute(exc_stmt)
        exceptions = exc_res.scalars().all()

        delayed = Decimal("0.00")
        unreconciled = Decimal("0.00")
        at_risk = Decimal("0.00")
        by_category: dict[str, Decimal] = {}

        txn_map = {getattr(t, "id", None): t for t in txns if hasattr(t, "id")}

        for exc in exceptions:
            stored_exp = Decimal(str(getattr(exc, "financial_exposure", 0) or 0))
            linked_txn = txn_map.get(getattr(exc, "transaction_id", None))
            if stored_exp > Decimal("0"):
                exp_amt = stored_exp
            elif linked_txn:
                exp_amt = Decimal(str(getattr(linked_txn, "amount", 0) or 0))
            else:
                exp_amt = Decimal(str(getattr(exc, "expected_cost", 0) or 0))

            raw_cat = getattr(exc, "exception_category", getattr(exc, "category", "unexplained"))
            cat = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)
            if cat in ("unknown", "None", ""):
                cat = "unexplained"

            by_category[cat] = by_category.get(cat, Decimal("0.00")) + exp_amt
            unreconciled += exp_amt

            if exp_amt >= Decimal("100000.00") or cat == "unexplained":
                at_risk += exp_amt
            if cat in (ExceptionCategory.DELAYED_SETTLEMENT.value, "timing_mismatch"):
                delayed += exp_amt

        abs_variance = abs(variance)

        # unreconciled_amount is the authoritative settlement shortfall.
        # Exception exposures explain WHY there is a shortfall — they must not
        # be summed on top of abs_variance (that would double-count).
        # Use the larger of: the sum of exception exposures (known breakdown)
        # vs the raw settlement variance (accounting residual).
        # Any residual variance not covered by exceptions is categorised separately.
        if abs_variance > unreconciled and abs_variance > tolerance:
            # There is an unexplained residual between variance and known exceptions
            residual = (abs_variance - unreconciled).quantize(Decimal("0.01"))
            variance_cat = (
                ExceptionCategory.DELAYED_SETTLEMENT.value
                if variance < 0
                else ExceptionCategory.UNEXPLAINED.value
            )
            by_category[variance_cat] = by_category.get(variance_cat, Decimal("0.00")) + residual
            if variance < 0:
                delayed += residual
            if residual >= Decimal("100000.00") or variance > 0:
                at_risk += residual
            unreconciled = abs_variance
        elif abs_variance <= tolerance:
            # variance is within clearing tolerance — do not inflate unreconciled
            pass
        # else: exception exposures >= abs_variance — already captured above


        return CashPositionSummary(
            expected_amount=expected_gross,
            expected_gross=expected_gross,
            expected_net_settlement=expected_net,
            received_amount=received,
            received_bank_credits=received,
            settlement_variance=variance,
            total_deducted_fees=fees,
            total_deducted_taxes=taxes,
            total_refunded_amount=refunds,
            pending_amount=pending,
            delayed_amount=delayed,
            unreconciled_amount=unreconciled,
            at_risk_amount=at_risk,
            breakdown_by_source=by_source,
            breakdown_by_category=by_category,
        )
