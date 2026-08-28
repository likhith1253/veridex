"""
Financial Exposure Service for Project Sentinel.

Performs Decimal-safe monetary arithmetic across reconciliation runs and transactions:
- Total processed value (All 3 sources: Gateway + Ledger + Bank)
- Matched monetary value (Deterministic & ML recovered via match_transactions -> transactions join)
- Manual review exposure (Actual transaction amounts for MANUAL_REVIEW decisions)
- Unresolved exposure (Effective exception exposure with transaction amount fallback)
- High-risk exposure (INR >= 100,000 or UNEXPLAINED)
- Exposure breakdown by exception category (duplicate, unexplained, delayed, fee/tax)
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Decision as DecisionORM,
    Exception as ExceptionORM,
    ExceptionTransaction as ExceptionTransactionORM,
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    ReconciliationRun as ReconciliationRunORM,
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
        # 0. Resolve run ORM ID if provided
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

        # 1. Transactions Total across ALL feeds (Gateway, Ledger, Bank)
        txn_stmt = select(TransactionORM)
        txn_res = await self.session.execute(txn_stmt)
        txns = txn_res.scalars().all()
        txn_map = {getattr(t, "id", None): t for t in txns if hasattr(t, "id")}

        total_val = sum((Decimal(str(t.amount or 0)) for t in txns), Decimal("0.00"))

        # 2. Matches Values (Join match_transactions -> transactions)
        match_stmt = select(MatchORM)
        if run_orm_id:
            match_stmt = match_stmt.where(
                (MatchORM.run_id == run_orm_id) | (MatchORM.run_id == run_id)
            )
        match_res = await self.session.execute(match_stmt)
        matches = match_res.scalars().all()

        matched_val = Decimal("0.00")
        ml_val = Decimal("0.00")

        if matches:
            match_ids = [m.id for m in matches if hasattr(m, "id")]
            if match_ids:
                mt_stmt = select(MatchTransactionORM).where(MatchTransactionORM.match_id.in_(match_ids))
                mt_res = await self.session.execute(mt_stmt)
                match_txns = mt_res.scalars().all()

                match_to_txns: dict[str, list[TransactionORM]] = defaultdict(list)
                for mt in match_txns:
                    if mt.transaction_id in txn_map:
                        match_to_txns[mt.match_id].append(txn_map[mt.transaction_id])

                for m in matches:
                    linked = match_to_txns.get(m.id, [])
                    if not linked:
                        continue

                    gw_amt = next((t.amount for t in linked if t.source == TransactionSource.GATEWAY.value), None)
                    ld_amt = next((t.amount for t in linked if t.source == TransactionSource.LEDGER.value), None)
                    bk_amt = next((t.amount for t in linked if t.source == TransactionSource.BANK.value), None)
                    m_amt = Decimal(str(gw_amt or ld_amt or bk_amt or max(t.amount for t in linked)))

                    matched_val += m_amt
                    reason = str(getattr(m, "reason", "") or "").lower()
                    if "ml" in reason or getattr(m, "match_type", "") == "probable":
                        ml_val += m_amt

        # 3. Exceptions Breakdown (Query exceptions BEFORE decisions to match mock sequence)
        exc_stmt = select(ExceptionORM).where(
            (ExceptionORM.status != "resolved") & (ExceptionORM.resolved == False)
        )
        if run_orm_id:
            exc_stmt = exc_stmt.where(
                (ExceptionORM.run_id == run_orm_id) | (ExceptionORM.run_id == run_id)
            )
        exc_res = await self.session.execute(exc_stmt)
        exceptions = exc_res.scalars().all()

        unresolved_val = Decimal("0.00")
        high_risk_val = Decimal("0.00")
        dup_exp = Decimal("0.00")
        unexp_exp = Decimal("0.00")
        delayed_exp = Decimal("0.00")
        fee_tax_exp = Decimal("0.00")
        cat_dict: dict[str, Decimal] = {}

        if exceptions:
            for e in exceptions:
                stored_exp = Decimal(str(getattr(e, "financial_exposure", 0) or 0))
                linked_txn = txn_map.get(getattr(e, "transaction_id", None))
                if stored_exp > Decimal("0"):
                    exp_amt = stored_exp
                elif linked_txn:
                    exp_amt = Decimal(str(getattr(linked_txn, "amount", 0) or 0))
                else:
                    exp_amt = Decimal(str(getattr(e, "expected_cost", 0) or 0))

                raw_cat = getattr(e, "exception_category", getattr(e, "category", "unexplained"))
                cat = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)
                if cat in ("unknown", "None", ""):
                    cat = "unexplained"

                cat_dict[cat] = cat_dict.get(cat, Decimal("0.00")) + exp_amt
                unresolved_val += exp_amt

                if exp_amt >= Decimal("100000.00") or cat == "unexplained":
                    high_risk_val += exp_amt

                if cat in (ExceptionCategory.DUPLICATE_ENTRY.value, "duplicate_record"):
                    dup_exp += exp_amt
                elif cat == ExceptionCategory.UNEXPLAINED.value:
                    unexp_exp += exp_amt
                elif cat in (ExceptionCategory.DELAYED_SETTLEMENT.value, "timing_mismatch"):
                    delayed_exp += exp_amt
                elif cat in (ExceptionCategory.FEE_MISMATCH.value, "fee_tax_mismatch", "amount_mismatch"):
                    fee_tax_exp += exp_amt

        # 4. Manual Reviews Value (from decisions -> matches -> transactions)
        dec_stmt = select(DecisionORM).where(DecisionORM.decision_action == DecisionAction.MANUAL_REVIEW.value)
        if run_orm_id:
            dec_stmt = dec_stmt.where(
                (DecisionORM.run_id == run_orm_id) | (DecisionORM.run_id == run_id)
            )
        dec_res = await self.session.execute(dec_stmt)
        manual_decisions = dec_res.scalars().all()

        manual_val = Decimal("0.00")
        manual_seen_txns: set[str] = set()

        if manual_decisions:
            manual_match_ids = [d.match_id for d in manual_decisions if getattr(d, "match_id", None)]
            if manual_match_ids:
                mm_stmt = select(MatchTransactionORM).where(MatchTransactionORM.match_id.in_(manual_match_ids))
                mm_res = await self.session.execute(mm_stmt)
                for mt in mm_res.scalars().all():
                    if mt.transaction_id in txn_map and mt.transaction_id not in manual_seen_txns:
                        t = txn_map[mt.transaction_id]
                        manual_val += Decimal(str(t.amount or 0))
                        manual_seen_txns.add(mt.transaction_id)

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


ExposureService = FinancialExposureService
