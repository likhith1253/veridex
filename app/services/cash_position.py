"""
Cash Position Aggregation Service for Project Sentinel.

Calculates real-time financial cash position:
- Expected amount (Gateway / Ledger gross orders)
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

from app.database.models import Exception as ExceptionORM, Match as MatchORM, Transaction as TransactionORM
from app.models.exception_record import ExceptionCategory
from app.models.transaction import TransactionSource, TransactionStatus


@dataclass
class CashPositionSummary:
    """Consolidated financial cash position summary."""
    expected_amount: Decimal = Decimal("0")
    received_amount: Decimal = Decimal("0")
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
            "expected_amount": float(self.expected_amount),
            "received_amount": float(self.received_amount),
            "pending_amount": float(self.pending_amount),
            "delayed_amount": float(self.delayed_amount),
            "unreconciled_amount": float(self.unreconciled_amount),
            "at_risk_amount": float(self.at_risk_amount),
            "currency": self.currency,
            "breakdown_by_source": {k: float(v) for k, v in self.breakdown_by_source.items()},
            "breakdown_by_category": {k: float(v) for k, v in self.breakdown_by_category.items()},
            "as_of": self.as_of.isoformat(),
        }


class CashPositionService:
    """Service calculating grounded cash position from database transactions and exceptions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cash_position(self, run_id: Optional[str] = None) -> CashPositionSummary:
        """Calculate live cash position across all transactions or scoped to a run."""
        # Query transactions
        stmt = select(TransactionORM)
        res = await self.session.execute(stmt)
        txns = res.scalars().all()

        # Query exceptions
        exc_stmt = select(ExceptionORM)
        if run_id:
            exc_stmt = exc_stmt.where(ExceptionORM.run_id == run_id)
        exc_res = await self.session.execute(exc_stmt)
        exceptions = exc_res.scalars().all()

        expected = Decimal("0")
        received = Decimal("0")
        pending = Decimal("0")
        by_source: dict[str, Decimal] = {
            TransactionSource.GATEWAY.value: Decimal("0"),
            TransactionSource.LEDGER.value: Decimal("0"),
            TransactionSource.BANK.value: Decimal("0"),
        }

        for t in txns:
            amt = Decimal(str(t.amount))
            src = t.source
            by_source[src] = by_source.get(src, Decimal("0")) + amt

            if src in (TransactionSource.GATEWAY.value, TransactionSource.LEDGER.value):
                expected += amt
            elif src == TransactionSource.BANK.value:
                received += amt

        # Expected cash from gateway/ledger vs bank
        net_expected = max(by_source.get(TransactionSource.GATEWAY.value, Decimal("0")),
                           by_source.get(TransactionSource.LEDGER.value, Decimal("0")))
        pending = max(Decimal("0"), net_expected - received)

        # Exception aggregations
        delayed = Decimal("0")
        unreconciled = Decimal("0")
        at_risk = Decimal("0")
        by_category: dict[str, Decimal] = {}

        for exc in exceptions:
            exp_amt = Decimal(str(getattr(exc, "financial_exposure", getattr(exc, "amount_delta", 0)) or 0))
            raw_cat = getattr(exc, "exception_category", getattr(exc, "category", "unexplained"))
            cat = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)
            by_category[cat] = by_category.get(cat, Decimal("0")) + exp_amt
            unreconciled += exp_amt

            if cat == ExceptionCategory.DELAYED_SETTLEMENT.value:
                delayed += exp_amt
            if exp_amt >= Decimal("100000") or cat == ExceptionCategory.UNEXPLAINED.value:
                at_risk += exp_amt

        return CashPositionSummary(
            expected_amount=net_expected,
            received_amount=received,
            pending_amount=pending,
            delayed_amount=delayed,
            unreconciled_amount=unreconciled,
            at_risk_amount=at_risk,
            breakdown_by_source=by_source,
            breakdown_by_category=by_category,
        )
