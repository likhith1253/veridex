"""
Fee and Tax Control Service for Project Sentinel.

Reconciles expected vs. observed gateway merchant discount rates (MDR) and tax deductions:
- Expected MDR fee vs. actual fee charged by gateway
- Expected GST tax (18% on MDR) vs. actual tax deducted
- Computes fee leakage / excess deduction exposure
- Identifies specific affected transaction records
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction as TransactionORM
from app.models.transaction import TransactionSource


@dataclass
class FeeTaxDiscrepancyItem:
    """Individual fee/tax discrepancy item."""
    transaction_id: str
    order_id: Optional[str]
    gross_amount: str
    expected_fee: str
    observed_fee: str
    fee_difference: str
    expected_tax: str
    observed_tax: str
    tax_difference: str
    exposure: str


@dataclass
class FeeTaxReconciliationReport:
    """Consolidated Fee and Tax Control Report."""
    total_transactions_analyzed: int = 0
    total_gross_volume: str = "0.00"
    total_expected_fee: str = "0.00"
    total_observed_fee: str = "0.00"
    total_fee_variance: str = "0.00"
    total_expected_tax: str = "0.00"
    total_observed_tax: str = "0.00"
    total_tax_variance: str = "0.00"
    total_fee_tax_exposure: str = "0.00"
    discrepant_transactions_count: int = 0
    discrepancies: list[dict[str, Any]] = field(default_factory=list)
    currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FeeTaxService:
    """Service auditing and reconciling payment gateway fee and tax deductions."""

    DEFAULT_MDR_RATE = Decimal("0.02")  # 2.0% standard MDR
    GST_RATE = Decimal("0.18")  # 18% GST on fee

    def __init__(self, session: AsyncSession):
        self.session = session

    async def reconcile_fees_and_taxes(self, limit: int = 100) -> FeeTaxReconciliationReport:
        """Analyze gateway transactions for fee and tax variances."""
        stmt = select(TransactionORM).where(TransactionORM.source == TransactionSource.GATEWAY.value).limit(limit)
        res = await self.session.execute(stmt)
        gw_txns = res.scalars().all()

        total_gross = Decimal("0.00")
        exp_fee_tot = Decimal("0.00")
        obs_fee_tot = Decimal("0.00")
        exp_tax_tot = Decimal("0.00")
        obs_tax_tot = Decimal("0.00")
        discrepancies: list[dict[str, Any]] = []

        for t in gw_txns:
            gross = Decimal(str(t.amount or 0))
            total_gross += gross

            if t.fee is not None or t.tax is not None:
                exp_fee = (gross * self.DEFAULT_MDR_RATE).quantize(Decimal("0.01"))
                exp_tax = (exp_fee * self.GST_RATE).quantize(Decimal("0.01"))
                obs_fee = Decimal(str(t.fee or 0))
                obs_tax = Decimal(str(t.tax or 0))
            else:
                exp_fee = Decimal("0.00")
                exp_tax = Decimal("0.00")
                obs_fee = Decimal("0.00")
                obs_tax = Decimal("0.00")

            exp_fee_tot += exp_fee
            obs_fee_tot += obs_fee
            exp_tax_tot += exp_tax
            obs_tax_tot += obs_tax

            fee_diff = (obs_fee - exp_fee).quantize(Decimal("0.01"))
            tax_diff = (obs_tax - exp_tax).quantize(Decimal("0.01"))
            item_exposure = abs(fee_diff) + abs(tax_diff)

            if item_exposure > Decimal("0.50"):  # Tolerating rounding <= 50 paise
                discrepancies.append(
                    asdict(
                        FeeTaxDiscrepancyItem(
                            transaction_id=t.domain_transaction_id or t.id,
                            order_id=t.order_id,
                            gross_amount=str(gross),
                            expected_fee=str(exp_fee),
                            observed_fee=str(obs_fee),
                            fee_difference=str(fee_diff),
                            expected_tax=str(exp_tax),
                            observed_tax=str(obs_tax),
                            tax_difference=str(tax_diff),
                            exposure=str(item_exposure),
                        )
                    )
                )

        fee_var = (obs_fee_tot - exp_fee_tot).quantize(Decimal("0.01"))
        tax_var = (obs_tax_tot - exp_tax_tot).quantize(Decimal("0.01"))
        total_exp = (abs(fee_var) + abs(tax_var)).quantize(Decimal("0.01"))

        return FeeTaxReconciliationReport(
            total_transactions_analyzed=len(gw_txns),
            total_gross_volume=str(total_gross),
            total_expected_fee=str(exp_fee_tot),
            total_observed_fee=str(obs_fee_tot),
            total_fee_variance=str(fee_var),
            total_expected_tax=str(exp_tax_tot),
            total_observed_tax=str(obs_tax_tot),
            total_tax_variance=str(tax_var),
            total_fee_tax_exposure=str(total_exp),
            discrepant_transactions_count=len(discrepancies),
            discrepancies=discrepancies,
        )
