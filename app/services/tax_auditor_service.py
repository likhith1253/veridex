"""
Tax-Line Matcher / Auditor Service for Project Sentinel.

Audits Razorpay settlement tax deductions against authoritative expected tax
recorded by Sentinel in internal ledger records or settlement contract metadata.
Enforces Decimal precision, zero fabrication, and deterministic discrepancy detection.
"""

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    Transaction as TransactionORM,
    TransactionSource,
)


class TaxAuditStatus(str, Enum):
    MATCHED = "MATCHED"
    VARIANCE = "VARIANCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class TaxAuditResult(BaseModel):
    settlement_id: str
    gross_amount: Decimal
    reported_tax: Optional[Decimal] = None
    expected_tax: Optional[Decimal] = None
    tax_variance: Optional[Decimal] = None
    status: TaxAuditStatus
    explanation: str
    evidence_ids: list[str] = []
    currency: str = "INR"

    model_config = ConfigDict(from_attributes=True)


class TaxAuditorService:
    """Deterministic tax line auditor verifying gateway tax deductions against authoritative expected values."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def audit_settlement_tax(self, settlement_id: str) -> TaxAuditResult:
        """Audit settlement tax lines against expected tax recorded in Sentinel.
        
        Raises:
            ValueError: If settlement_id does not exist in the database.
        """
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.domain_transaction_id == settlement_id,
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement",
            )
        )
        res = await self.session.execute(stmt)
        settlement = res.scalar_one_or_none()

        if not settlement:
            raise ValueError(f"Settlement not found: {settlement_id}")

        evidence_ids = [settlement.id]
        currency = settlement.currency or "INR"

        # Validate gross amount
        gross = settlement.amount
        if gross is None or gross <= Decimal("0.00"):
            return TaxAuditResult(
                settlement_id=settlement_id,
                gross_amount=Decimal("0.00") if gross is None else gross,
                reported_tax=settlement.tax,
                expected_tax=None,
                tax_variance=None,
                status=TaxAuditStatus.INSUFFICIENT_EVIDENCE,
                explanation=f"Settlement has invalid gross amount: {gross}. Must be strictly positive for tax line audit.",
                evidence_ids=evidence_ids,
                currency=currency,
            )

        # Validate reported tax
        reported_tax = settlement.tax
        if reported_tax is not None and reported_tax < Decimal("0.00"):
            return TaxAuditResult(
                settlement_id=settlement_id,
                gross_amount=gross,
                reported_tax=reported_tax,
                expected_tax=None,
                tax_variance=None,
                status=TaxAuditStatus.INSUFFICIENT_EVIDENCE,
                explanation=f"Settlement has invalid negative reported tax: {reported_tax}.",
                evidence_ids=evidence_ids,
                currency=currency,
            )

        if reported_tax is None:
            return TaxAuditResult(
                settlement_id=settlement_id,
                gross_amount=gross,
                reported_tax=None,
                expected_tax=None,
                tax_variance=None,
                status=TaxAuditStatus.INSUFFICIENT_EVIDENCE,
                explanation="No Razorpay-reported tax line exists on settlement record.",
                evidence_ids=evidence_ids,
                currency=currency,
            )

        # Establish authoritative expected tax without fabrication
        expected_tax: Optional[Decimal] = None
        meta = settlement.meta_data or {}

        # 1. Check explicit metadata expected tax
        raw_exp = meta.get("expected_tax") or meta.get("ledger_tax") or meta.get("authoritative_tax")
        if raw_exp is not None:
            try:
                expected_tax = Decimal(str(raw_exp))
            except (InvalidOperation, ValueError):
                expected_tax = None

        # 2. Check linked ledger transactions
        if expected_tax is None:
            stmt_match = select(MatchTransactionORM.match_id).where(
                MatchTransactionORM.transaction_id == settlement.id
            )
            match_ids = (await self.session.execute(stmt_match)).scalars().all()
            if match_ids:
                stmt_counterparts = (
                    select(TransactionORM)
                    .join(MatchTransactionORM, MatchTransactionORM.transaction_id == TransactionORM.id)
                    .where(
                        and_(
                            MatchTransactionORM.match_id.in_(match_ids),
                            TransactionORM.source == TransactionSource.LEDGER.value,
                            TransactionORM.id != settlement.id,
                        )
                    )
                )
                ledger_txns = (await self.session.execute(stmt_counterparts)).scalars().all()
                if ledger_txns:
                    taxes = [t.tax for t in ledger_txns if t.tax is not None]
                    if len(taxes) == len(ledger_txns) and len(taxes) > 0:
                        expected_tax = sum(taxes, Decimal("0.00"))
                        for t in ledger_txns:
                            if t.id not in evidence_ids:
                                evidence_ids.append(t.id)

        # 3. Check explicit agreed contract tax rate in metadata on verified fee
        if expected_tax is None and meta.get("agreed_tax_rate") is not None and settlement.fee is not None:
            try:
                rate = Decimal(str(meta["agreed_tax_rate"]))
                if rate >= Decimal("0.00"):
                    expected_tax = (settlement.fee * rate).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                expected_tax = None

        # If expected tax cannot be established from authoritative data, return INSUFFICIENT_EVIDENCE
        if expected_tax is None or expected_tax < Decimal("0.00"):
            return TaxAuditResult(
                settlement_id=settlement_id,
                gross_amount=gross,
                reported_tax=reported_tax,
                expected_tax=None,
                tax_variance=None,
                status=TaxAuditStatus.INSUFFICIENT_EVIDENCE,
                explanation="Authoritative expected tax cannot be established from existing ledger records, matches, or settlement metadata.",
                evidence_ids=evidence_ids,
                currency=currency,
            )

        # Deterministic variance calculation: reported - expected
        tax_variance = (reported_tax - expected_tax).quantize(Decimal("0.01"))

        if abs(tax_variance) <= Decimal("0.01"):
            status = TaxAuditStatus.MATCHED
            explanation = f"Razorpay reported tax INR {reported_tax} exactly matches expected tax INR {expected_tax}."
        else:
            status = TaxAuditStatus.VARIANCE
            explanation = f"Tax discrepancy detected: Razorpay reported tax INR {reported_tax} deviates from expected tax INR {expected_tax} by INR {tax_variance}."

        return TaxAuditResult(
            settlement_id=settlement_id,
            gross_amount=gross,
            reported_tax=reported_tax,
            expected_tax=expected_tax,
            tax_variance=tax_variance,
            status=status,
            explanation=explanation,
            evidence_ids=evidence_ids,
            currency=currency,
        )
