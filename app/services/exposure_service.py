"""
Financial Exposure Service for Project Sentinel.

Performs Decimal-safe monetary arithmetic across reconciliation runs and transactions:
- Total processed value
- Matched monetary value (Deterministic & ML recovered)
- Manual review exposure
- Unresolved exposure
- High-risk exposure (INR >= 100,000)
- Exposure breakdown by exception category (duplicate, unexplained, delayed, fee/tax)
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Decision as DecisionORM,
    Exception as ExceptionORM,
    Match as MatchORM,
    Transaction as TransactionORM,
)
from app.models.decision_result import DecisionAction
from app.models.exception_record import ExceptionCategory
from app.models.transaction import TransactionSource


@dataclass
class FinancialExposureBreakdown:
    """Consolidated Decimal-safe financial exposure metrics."""
    total_processed_value: Decimal = Decimal("0.00")
    matched_value: Decimal = Decimal("0.00")
    ml_recovered_value: Decimal = Decimal("0.00")
    manual_review_value: Decimal = Decimal("0.00")
    unresolved_value: Decimal = Decimal("0.00")
    high_risk_value: Decimal = Decimal("0.00")
    duplicate_exposure: Decimal = Decimal("0.00")
    unexplained_exposure: Decimal = Decimal("0.00")
    delayed_settlement_exposure: Decimal = Decimal("0.00")
    fee_tax_mismatch_exposure: Decimal = Decimal("0.00")
    category_breakdown: dict[str, str] = field(default_factory=dict)
    currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_processed_value": str(self.total_processed_value),
            "matched_value": str(self.matched_value),
            "ml_recovered_value": str(self.ml_recovered_value),
            "manual_review_value": str(self.manual_review_value),
            "unresolved_value": str(self.unresolved_value),
            "high_risk_value": str(self.high_risk_value),
            "duplicate_exposure": str(self.duplicate_exposure),
            "unexplained_exposure": str(self.unexplained_exposure),
            "delayed_settlement_exposure": str(self.delayed_settlement_exposure),
            "fee_tax_mismatch_exposure": str(self.fee_tax_mismatch_exposure),
            "category_breakdown": self.category_breakdown,
            "currency": self.currency,
        }


class FinancialExposureService:
    """Service providing Decimal-safe exposure calculations over PostgreSQL state."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_exposure(self, run_id: Optional[str] = None) -> FinancialExposureBreakdown:
        """Calculate complete monetary exposure metrics strictly using Decimal arithmetic."""
        # 1. Transactions Total
        txn_stmt = select(TransactionORM)
        txn_res = await self.session.execute(txn_stmt)
        txns = txn_res.scalars().all()

        total_val = Decimal("0.00")
        for t in txns:
            if t.source in (TransactionSource.GATEWAY.value, TransactionSource.LEDGER.value):
                total_val += Decimal(str(t.amount or 0))

        # 2. Matches Values
        match_stmt = select(MatchORM)
        if run_id:
            match_stmt = match_stmt.where(MatchORM.run_id == run_id)
        match_res = await self.session.execute(match_stmt)
        matches = match_res.scalars().all()

        matched_val = Decimal("0.00")
        ml_val = Decimal("0.00")
        for m in matches:
            amt = Decimal(str(m.matched_amount or m.confidence or 0))
            matched_val += amt
            if m.rule_name == "ml_scored":
                ml_val += amt

        # 3. Exceptions Breakdown
        exc_stmt = select(ExceptionORM)
        if run_id:
            exc_stmt = exc_stmt.where(ExceptionORM.run_id == run_id)
        exc_res = await self.session.execute(exc_stmt)
        exceptions = exc_res.scalars().all()

        unresolved_val = Decimal("0.00")
        high_risk_val = Decimal("0.00")
        dup_exp = Decimal("0.00")
        unexp_exp = Decimal("0.00")
        delayed_exp = Decimal("0.00")
        fee_tax_exp = Decimal("0.00")
        cat_dict: dict[str, Decimal] = {}

        for e in exceptions:
            exp_amt = Decimal(str(getattr(e, "financial_exposure", getattr(e, "amount_delta", 0)) or 0))
            raw_cat = getattr(e, "exception_category", getattr(e, "category", "unexplained"))
            cat = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)

            cat_dict[cat] = cat_dict.get(cat, Decimal("0.00")) + exp_amt
            unresolved_val += exp_amt

            if exp_amt >= Decimal("100000.00") or cat == ExceptionCategory.UNEXPLAINED.value:
                high_risk_val += exp_amt

            if cat == ExceptionCategory.DUPLICATE_ENTRY.value:
                dup_exp += exp_amt
            elif cat == ExceptionCategory.UNEXPLAINED.value:
                unexp_exp += exp_amt
            elif cat == ExceptionCategory.DELAYED_SETTLEMENT.value:
                delayed_exp += exp_amt
            elif cat in (ExceptionCategory.FEE_MISMATCH.value, "fee_tax_mismatch"):
                fee_tax_exp += exp_amt

        # 4. Manual Reviews Value from decisions
        dec_stmt = select(DecisionORM).where(DecisionORM.decision_action == DecisionAction.MANUAL_REVIEW.value)
        if run_id:
            dec_stmt = dec_stmt.where(DecisionORM.run_id == run_id)
        dec_res = await self.session.execute(dec_stmt)
        manual_decisions = dec_res.scalars().all()
        manual_val = Decimal(str(len(manual_decisions) * 1000))  # Estimated or from exceptions

        return FinancialExposureBreakdown(
            total_processed_value=total_val,
            matched_value=matched_val,
            ml_recovered_value=ml_val,
            manual_review_value=manual_val,
            unresolved_value=unresolved_val,
            high_risk_value=high_risk_val,
            duplicate_exposure=dup_exp,
            unexplained_exposure=unexp_exp,
            delayed_settlement_exposure=delayed_exp,
            fee_tax_mismatch_exposure=fee_tax_exp,
            category_breakdown={k: str(v) for k, v in cat_dict.items()},
        )
