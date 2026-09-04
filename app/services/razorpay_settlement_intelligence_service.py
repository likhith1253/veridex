"""
Razorpay Settlement Intelligence Service for Project Sentinel.

Provides detailed financial breakdown, transaction linking, bank reconciliation,
and variance analysis for individual Razorpay settlements.

Key capabilities:
- Settlement → transaction linking (which payments belong to which settlement)
- Financial decomposition (gross, fees, taxes, expected net, bank received, variance)
- Bank reconciliation state tracking
- Settlement exception dossier creation
- "Explain this settlement" capability
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction as TransactionORM, Exception as ExceptionORM
from app.models.transaction import TransactionSource
from app.integrations.razorpay.schemas import RazorpaySettlementState


class SettlementVarianceType(str, Enum):
    """Classification of settlement variance."""
    NO_VARIANCE = "NO_VARIANCE"
    FEE_VARIANCE = "FEE_VARIANCE"
    TAX_VARIANCE = "TAX_VARIANCE"
    AMOUNT_VARIANCE = "AMOUNT_VARIANCE"
    MISSING_BANK_CREDIT = "MISSING_BANK_CREDIT"
    UNEXPECTED_BANK_CREDIT = "UNEXPECTED_BANK_CREDIT"
    UNKNOWN_VARIANCE = "UNKNOWN_VARIANCE"


@dataclass
class SettlementFinancialBreakdown:
    """Financial decomposition of a settlement."""
    settlement_id: str
    gross_amount: Decimal
    fee_amount: Decimal
    tax_amount: Decimal
    adjustment_amount: Decimal
    expected_net_amount: Decimal
    bank_received_amount: Decimal
    bank_matched: bool
    variance: Decimal
    currency: str
    variance_type: SettlementVarianceType

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["variance_type"] = self.variance_type.value
        # Convert Decimal to string for JSON serialization
        for key in ["gross_amount", "fee_amount", "tax_amount", "adjustment_amount", 
                    "expected_net_amount", "bank_received_amount", "variance"]:
            if isinstance(data[key], Decimal):
                data[key] = str(data[key])
        return data


@dataclass
class SettlementTransactionLinkage:
    """Which transactions belong to a settlement."""
    settlement_id: str
    linked_transaction_count: int
    matched_transaction_count: int
    unmatched_transaction_count: int
    linked_transaction_ids: list[str]
    matched_transaction_ids: list[str]
    unmatched_transaction_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SettlementBankReconciliation:
    """Bank reconciliation state for a settlement."""
    settlement_id: str
    settlement_status: RazorpaySettlementState
    utr: Optional[str]
    bank_matched: bool
    bank_transaction_id: Optional[str]
    bank_amount: Optional[Decimal]
    bank_date: Optional[datetime]
    bank_match_confidence: Optional[Decimal]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["settlement_status"] = self.settlement_status.value
        if isinstance(data.get("bank_amount"), Decimal):
            data["bank_amount"] = str(data["bank_amount"])
        if isinstance(data.get("bank_match_confidence"), Decimal):
            data["bank_match_confidence"] = str(data["bank_match_confidence"])
        if data.get("bank_date"):
            data["bank_date"] = data["bank_date"].isoformat()
        return data


@dataclass
class SettlementExceptionDossier:
    """Structured investigation object for settlement exceptions."""
    settlement_id: str
    settlement_status: str
    settlement_period: Optional[str]
    gross_amount: Decimal
    fee_amount: Decimal
    tax_amount: Decimal
    expected_net_amount: Decimal
    bank_received_amount: Decimal
    variance: Decimal
    linked_transaction_count: int
    matched_transaction_count: int
    unmatched_transaction_count: int
    exception_type: str
    confidence: Decimal
    evidence: dict[str, Any]
    root_cause_candidates: list[str]
    recommended_next_action: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Convert Decimal to string
        for key in ["gross_amount", "fee_amount", "tax_amount", "expected_net_amount", 
                    "bank_received_amount", "variance", "confidence"]:
            if isinstance(data[key], Decimal):
                data[key] = str(data[key])
        return data


@dataclass
class SettlementExplanation:
    """Complete explanation of a settlement for finance operators."""
    # Summary
    settlement_id: str
    settlement_status: str
    expected_amount: Decimal
    bank_amount: Optional[Decimal]
    variance: Decimal
    
    # Composition
    gross_amount: Decimal
    fee_amount: Decimal
    tax_amount: Decimal
    adjustment_amount: Decimal
    net_amount: Decimal
    
    # Transaction evidence
    linked_transaction_count: int
    matched_transaction_count: int
    unmatched_transaction_count: int
    transaction_ids: list[str]
    
    # Bank evidence
    utr: Optional[str]
    bank_matched: bool
    bank_transaction_id: Optional[str]
    bank_date: Optional[datetime]
    
    # Root cause and action
    variance_type: SettlementVarianceType
    root_cause: Optional[str]
    recommended_action: Optional[str]
    
    # Evidence references
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["variance_type"] = self.variance_type.value
        # Convert Decimal to string
        for key in ["expected_amount", "bank_amount", "variance", "gross_amount", 
                    "fee_amount", "tax_amount", "adjustment_amount", "net_amount"]:
            val = data[key]
            if isinstance(val, Decimal):
                data[key] = str(val)
            elif val is None:
                data[key] = None
        if data.get("bank_date"):
            data["bank_date"] = data["bank_date"].isoformat()
        return data


class RazorpaySettlementIntelligenceService:
    """Service for Razorpay settlement intelligence and investigation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_settlement_financial_breakdown(
        self, 
        settlement_id: str
    ) -> SettlementFinancialBreakdown:
        """Calculate financial decomposition for a settlement."""
        # Get the settlement transaction
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.domain_transaction_id == settlement_id,
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement"
            )
        )
        result = await self.session.execute(stmt)
        settlement = result.scalar_one_or_none()
        
        if not settlement:
            raise ValueError(f"Settlement not found: {settlement_id}")
        
        gross = settlement.amount or Decimal("0")
        fee = settlement.fee or Decimal("0")
        tax = settlement.tax or Decimal("0")
        adjustment = Decimal("0")  # No adjustment field in current model
        currency = settlement.currency or "INR"
        
        # Calculate expected net
        expected_net = gross - fee - tax + adjustment
        
        # Find matching bank transaction
        bank_amount = await self._find_bank_match_for_settlement(settlement)
        bank_matched = bank_amount is not None

        # Calculate variance. When no bank transaction has matched yet, the
        # variance is NOT zero — it's the full expected amount still
        # outstanding. Fabricating a variance of exactly 0 here previously
        # made an unconfirmed settlement look identical to a perfectly
        # reconciled one ("PARITY CONFIRMED") in the UI, directly
        # contradicting the settlements list view (which correctly showed
        # EXCEPTION / pending confirmation for the same settlement).
        variance = (bank_amount - expected_net) if bank_matched else -expected_net

        # Classify variance
        variance_type = self._classify_variance(variance, fee, tax, bank_matched)

        return SettlementFinancialBreakdown(
            settlement_id=settlement_id,
            gross_amount=gross,
            fee_amount=fee,
            tax_amount=tax,
            adjustment_amount=adjustment,
            expected_net_amount=expected_net,
            bank_received_amount=bank_amount or Decimal("0"),
            bank_matched=bank_matched,
            variance=variance,
            currency=currency,
            variance_type=variance_type,
        )

    async def audit_settlement_tax(self, settlement_id: str):
        """Audit settlement tax lines against expected tax recorded in Sentinel."""
        from app.services.tax_auditor_service import TaxAuditorService
        auditor = TaxAuditorService(self.session)
        return await auditor.audit_settlement_tax(settlement_id)

    async def get_settlement_transaction_linkage(
        self, 
        settlement_id: str
    ) -> SettlementTransactionLinkage:
        """Determine which transactions belong to a settlement."""
        # For Razorpay, we need to find payments that were settled in this batch
        # This is complex because Razorpay doesn't always provide direct settlement→payment linkage
        # We use heuristic: payments with order_id and matching metadata
        
        # Get settlement metadata for period info
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.domain_transaction_id == settlement_id,
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement"
            )
        )
        result = await self.session.execute(stmt)
        settlement = result.scalar_one_or_none()
        
        if not settlement:
            raise ValueError(f"Settlement not found: {settlement_id}")
        
        # Heuristic: find payments in the same time window (settlement typically T+1 or T+2)
        settlement_date = settlement.timestamp.date()
        
        # Get all gateway payments around this period
        from datetime import timedelta
        window_start = settlement_date - timedelta(days=3)
        window_end = settlement_date + timedelta(days=1)
        
        payment_stmt = select(TransactionORM).where(
            and_(
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "payment",
                TransactionORM.timestamp >= window_start,
                TransactionORM.timestamp <= window_end
            )
        )
        payment_result = await self.session.execute(payment_stmt)
        payments = payment_result.scalars().all()
        
        linked_ids = [p.domain_transaction_id for p in payments]
        
        # Check which payments are matched (have corresponding ledger entries)
        matched_ids = []
        unmatched_ids = []
        
        for payment in payments:
            # Check if this payment has a match in the matching system
            # This would typically be done via the match_transactions table
            # For now, we use a simpler heuristic: does it have a corresponding ledger entry?
            ledger_stmt = select(TransactionORM).where(
                and_(
                    TransactionORM.source == TransactionSource.LEDGER.value,
                    TransactionORM.order_id == payment.order_id
                )
            )
            ledger_result = await self.session.execute(ledger_stmt)
            ledger_txn = ledger_result.scalar_one_or_none()
            
            if ledger_txn:
                matched_ids.append(payment.domain_transaction_id)
            else:
                unmatched_ids.append(payment.domain_transaction_id)
        
        return SettlementTransactionLinkage(
            settlement_id=settlement_id,
            linked_transaction_count=len(linked_ids),
            matched_transaction_count=len(matched_ids),
            unmatched_transaction_count=len(unmatched_ids),
            linked_transaction_ids=linked_ids,
            matched_transaction_ids=matched_ids,
            unmatched_transaction_ids=unmatched_ids,
        )

    async def get_settlement_bank_reconciliation(
        self, 
        settlement_id: str
    ) -> SettlementBankReconciliation:
        """Get bank reconciliation state for a settlement."""
        # Get the settlement transaction
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.domain_transaction_id == settlement_id,
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement"
            )
        )
        result = await self.session.execute(stmt)
        settlement = result.scalar_one_or_none()
        
        if not settlement:
            raise ValueError(f"Settlement not found: {settlement_id}")
        
        # Get UTR from metadata
        utr = settlement.meta_data.get("utr") if settlement.meta_data else None
        reference_number = settlement.reference_number
        
        # Try to find matching bank transaction
        bank_match = await self._find_bank_transaction_for_settlement(settlement)
        
        if bank_match:
            settlement_status = RazorpaySettlementState.BANK_CREDIT_CONFIRMED
            bank_matched = True
            bank_txn_id = bank_match.domain_transaction_id
            bank_amount = bank_match.amount
            bank_date = bank_match.timestamp
            bank_match_confidence = Decimal("1.00")  # Deterministic match
        else:
            # Check if settlement is marked as processed by Razorpay
            lifecycle_state = settlement.meta_data.get("lifecycle_state", "RAZORPAY_PROCESSED") if settlement.meta_data else "RAZORPAY_PROCESSED"
            if lifecycle_state == "BANK_CREDIT_PENDING":
                settlement_status = RazorpaySettlementState.BANK_CREDIT_PENDING
            else:
                settlement_status = RazorpaySettlementState.RAZORPAY_PROCESSED
            bank_matched = False
            bank_txn_id = None
            bank_amount = None
            bank_date = None
            bank_match_confidence = None
        
        return SettlementBankReconciliation(
            settlement_id=settlement_id,
            settlement_status=settlement_status,
            utr=utr or reference_number,
            bank_matched=bank_matched,
            bank_transaction_id=bank_txn_id,
            bank_amount=bank_amount,
            bank_date=bank_date,
            bank_match_confidence=bank_match_confidence,
        )

    async def create_settlement_exception_dossier(
        self, 
        settlement_id: str,
        exception_type: str,
        confidence: Decimal
    ) -> SettlementExceptionDossier:
        """Create structured investigation object for settlement exceptions."""
        # Get financial breakdown
        financial = await self.get_settlement_financial_breakdown(settlement_id)
        
        # Get transaction linkage
        linkage = await self.get_settlement_transaction_linkage(settlement_id)
        
        # Get bank reconciliation
        bank_recon = await self.get_settlement_bank_reconciliation(settlement_id)
        
        # Gather evidence
        evidence = {
            "financial_breakdown": financial.to_dict(),
            "transaction_linkage": linkage.to_dict(),
            "bank_reconciliation": bank_recon.to_dict(),
        }
        
        # Determine root cause candidates based on exception/variance type
        effective_variance_type = None
        if exception_type:
            try:
                effective_variance_type = SettlementVarianceType(exception_type)
            except ValueError:
                try:
                    effective_variance_type = SettlementVarianceType[exception_type]
                except KeyError:
                    effective_variance_type = None
        if not effective_variance_type:
            effective_variance_type = financial.variance_type

        root_cause_candidates = self._determine_root_cause_candidates(
            effective_variance_type, 
            financial.variance,
            bank_recon.settlement_status
        )
        
        # Determine recommended action
        recommended_action = self._determine_recommended_action(
            effective_variance_type,
            bank_recon.settlement_status,
            financial.variance
        )
        
        # Get settlement period from timestamp
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.domain_transaction_id == settlement_id,
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement"
            )
        )
        result = await self.session.execute(stmt)
        settlement = result.scalar_one_or_none()
        settlement_period = settlement.timestamp.strftime("%Y-%m") if settlement else None
        
        return SettlementExceptionDossier(
            settlement_id=settlement_id,
            settlement_status=bank_recon.settlement_status.value,
            settlement_period=settlement_period,
            gross_amount=financial.gross_amount,
            fee_amount=financial.fee_amount,
            tax_amount=financial.tax_amount,
            expected_net_amount=financial.expected_net_amount,
            bank_received_amount=financial.bank_received_amount,
            variance=financial.variance,
            linked_transaction_count=linkage.linked_transaction_count,
            matched_transaction_count=linkage.matched_transaction_count,
            unmatched_transaction_count=linkage.unmatched_transaction_count,
            exception_type=exception_type,
            confidence=confidence,
            evidence=evidence,
            root_cause_candidates=root_cause_candidates,
            recommended_next_action=recommended_action,
        )

    async def explain_settlement(
        self, 
        settlement_id: str
    ) -> SettlementExplanation:
        """Provide complete explanation of a settlement for finance operators."""
        # Get financial breakdown
        financial = await self.get_settlement_financial_breakdown(settlement_id)
        
        # Get transaction linkage
        linkage = await self.get_settlement_transaction_linkage(settlement_id)
        
        # Get bank reconciliation
        bank_recon = await self.get_settlement_bank_reconciliation(settlement_id)
        
        # Determine root cause if there's variance
        root_cause = None
        if financial.variance != Decimal("0"):
            root_cause = self._explain_variance(
                financial.variance_type,
                financial.variance,
                bank_recon.settlement_status
            )
        
        # Determine recommended action
        recommended_action = self._determine_recommended_action(
            financial.variance_type,
            bank_recon.settlement_status,
            financial.variance
        )
        
        # Build evidence references
        evidence = {
            "settlement_id": settlement_id,
            "financial_breakdown": financial.to_dict(),
            "transaction_linkage": linkage.to_dict(),
            "bank_reconciliation": bank_recon.to_dict(),
        }
        
        return SettlementExplanation(
            settlement_id=settlement_id,
            settlement_status=bank_recon.settlement_status.value,
            expected_amount=financial.expected_net_amount,
            bank_amount=financial.bank_received_amount if bank_recon.bank_matched else None,
            variance=financial.variance,
            gross_amount=financial.gross_amount,
            fee_amount=financial.fee_amount,
            tax_amount=financial.tax_amount,
            adjustment_amount=financial.adjustment_amount,
            net_amount=financial.expected_net_amount,
            linked_transaction_count=linkage.linked_transaction_count,
            matched_transaction_count=linkage.matched_transaction_count,
            unmatched_transaction_count=linkage.unmatched_transaction_count,
            transaction_ids=linkage.linked_transaction_ids[:20],  # Limit for display
            utr=bank_recon.utr,
            bank_matched=bank_recon.bank_matched,
            bank_transaction_id=bank_recon.bank_transaction_id,
            bank_date=bank_recon.bank_date,
            variance_type=financial.variance_type,
            root_cause=root_cause,
            recommended_action=recommended_action,
            evidence=evidence,
        )

    async def _find_bank_match_for_settlement(
        self, 
        settlement: TransactionORM
    ) -> Optional[Decimal]:
        """Find matching bank transaction amount for a settlement."""
        bank_match = await self._find_bank_transaction_for_settlement(settlement)
        return bank_match.amount if bank_match else None

    async def _find_bank_transaction_for_settlement(
        self, 
        settlement: TransactionORM
    ) -> Optional[TransactionORM]:
        """Find matching bank transaction for a settlement."""
        # Try to match by UTR/reference number
        utr = settlement.meta_data.get("utr") if settlement.meta_data else None
        reference_number = settlement.reference_number
        
        if utr:
            stmt = select(TransactionORM).where(
                and_(
                    TransactionORM.source == TransactionSource.BANK.value,
                    or_(
                        TransactionORM.reference_number == utr,
                        TransactionORM.narration.contains(utr)
                    )
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        
        if reference_number:
            stmt = select(TransactionORM).where(
                and_(
                    TransactionORM.source == TransactionSource.BANK.value,
                    or_(
                        TransactionORM.reference_number == reference_number,
                        TransactionORM.narration.contains(reference_number)
                    )
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        
        # Fallback: try amount and date match
        from datetime import timedelta
        settlement_date = settlement.timestamp.date()
        window_start = settlement_date - timedelta(days=2)
        window_end = settlement_date + timedelta(days=2)
        
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.source == TransactionSource.BANK.value,
                TransactionORM.amount == settlement.amount,
                TransactionORM.timestamp >= window_start,
                TransactionORM.timestamp <= window_end
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _classify_variance(
        self, 
        variance: Decimal, 
        fee: Decimal, 
        tax: Decimal, 
        has_bank_credit: bool
    ) -> SettlementVarianceType:
        """Classify the type of variance."""
        if not has_bank_credit:
            return SettlementVarianceType.MISSING_BANK_CREDIT
        
        if abs(variance) <= Decimal("0.01"):  # Within rounding precision
            return SettlementVarianceType.NO_VARIANCE
        
        if abs(variance - fee) <= Decimal("1.00"):
            return SettlementVarianceType.FEE_VARIANCE
        
        if abs(variance - tax) <= Decimal("1.00"):
            return SettlementVarianceType.TAX_VARIANCE
        
        if variance > Decimal("0"):
            return SettlementVarianceType.UNEXPECTED_BANK_CREDIT
        
        return SettlementVarianceType.AMOUNT_VARIANCE

    def _determine_root_cause_candidates(
        self, 
        variance_type: SettlementVarianceType, 
        variance: Decimal,
        settlement_status: RazorpaySettlementState
    ) -> list[str]:
        """Determine potential root causes for the variance."""
        candidates = []
        
        if variance_type == SettlementVarianceType.MISSING_BANK_CREDIT:
            candidates.extend([
                "Settlement not yet processed by bank",
                "Bank processing delay",
                "UTR mismatch or incorrect reference",
                "Settlement failed at Razorpay but not reflected",
            ])
        elif variance_type == SettlementVarianceType.FEE_VARIANCE:
            candidates.extend([
                "Razorpay fee structure change",
                "Incorrect fee calculation in normalization",
                "Tiered pricing not reflected",
            ])
        elif variance_type == SettlementVarianceType.TAX_VARIANCE:
            candidates.extend([
                "GST rate change",
                "Tax calculation discrepancy",
                "Inter-state vs intra-state tax difference",
            ])
        elif variance_type == SettlementVarianceType.AMOUNT_VARIANCE:
            candidates.extend([
                "Partial settlement processing",
                "Deduction for chargebacks",
                "Adjustment for previous overpayment",
                "Currency conversion difference",
            ])
        elif variance_type == SettlementVarianceType.UNEXPECTED_BANK_CREDIT:
            candidates.extend([
                "Multiple settlements combined",
                "Manual bank adjustment",
                "Reversal of previous deduction",
            ])
        
        return candidates

    def _determine_recommended_action(
        self, 
        variance_type: SettlementVarianceType,
        settlement_status: RazorpaySettlementState,
        variance: Decimal
    ) -> str:
        """Determine recommended action for the operator."""
        if variance_type == SettlementVarianceType.NO_VARIANCE:
            return "No action required - settlement reconciled"
        
        if variance_type == SettlementVarianceType.MISSING_BANK_CREDIT:
            if settlement_status == RazorpaySettlementState.BANK_CREDIT_PENDING:
                return "Monitor for bank credit - verify with bank if not received within T+3"
            else:
                return "Investigate with Razorpay support - settlement marked processed but bank credit missing"
        
        if variance_type in {SettlementVarianceType.FEE_VARIANCE, SettlementVarianceType.TAX_VARIANCE}:
            return "Review fee/tax structure with Razorpay - update normalization if rate changed"
        
        if variance_type == SettlementVarianceType.AMOUNT_VARIANCE:
            if abs(variance) > Decimal("1000"):
                return "High variance - escalate to finance lead for investigation"
            else:
                return "Review settlement details and bank statement for adjustments"
        
        if variance_type == SettlementVarianceType.UNEXPECTED_BANK_CREDIT:
            return "Verify with bank - may indicate combined settlement or manual adjustment"
        
        return "Review settlement details and escalate if variance persists"

    def _explain_variance(
        self, 
        variance_type: SettlementVarianceType, 
        variance: Decimal,
        settlement_status: RazorpaySettlementState
    ) -> str:
        """Provide human-readable explanation of variance."""
        if variance_type == SettlementVarianceType.NO_VARIANCE:
            return "Settlement amount matches bank credit exactly"
        
        if variance_type == SettlementVarianceType.MISSING_BANK_CREDIT:
            return f"Expected ₹{variance:.2f} but no matching bank credit found"
        
        if variance_type == SettlementVarianceType.FEE_VARIANCE:
            return f"Variance of ₹{variance:.2f} likely due to fee structure difference"
        
        if variance_type == SettlementVarianceType.TAX_VARIANCE:
            return f"Variance of ₹{variance:.2f} likely due to tax calculation difference"
        
        if variance_type == SettlementVarianceType.AMOUNT_VARIANCE:
            return f"Variance of ₹{variance:.2f} indicates amount mismatch - possible adjustments or deductions"
        
        if variance_type == SettlementVarianceType.UNEXPECTED_BANK_CREDIT:
            return f"Bank credit exceeds expected by ₹{variance:.2f} - possible combined settlement"
        
        return f"Unexplained variance of ₹{variance:.2f}"
