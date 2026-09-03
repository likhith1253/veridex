"""
Settlement Investigation Service for Project Sentinel.

Connects Razorpay settlement intelligence to the existing AI investigation layer.
Provides structured evidence for LLM investigation of settlement exceptions.
"""

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.state import InvestigationState
from app.investigation.service import InvestigationService
from app.models.decision_result import DecisionResult
from app.models.transaction import Transaction
from app.services.razorpay_settlement_intelligence_service import (
    RazorpaySettlementIntelligenceService,
    SettlementExceptionDossier,
    SettlementExplanation,
)


class SettlementInvestigationService:
    """Service for investigating settlement exceptions using AI."""

    def __init__(
        self,
        session: AsyncSession,
        investigation_service: InvestigationService,
        settlement_intelligence: Optional[RazorpaySettlementIntelligenceService] = None,
    ):
        self.session = session
        self.investigation_service = investigation_service
        self.settlement_intelligence = settlement_intelligence or RazorpaySettlementIntelligenceService(session)

    async def investigate_settlement_exception(
        self,
        settlement_id: str,
        exception_id: str,
        run_id: str,
        exception_type: str,
        confidence: Decimal,
    ) -> dict[str, Any]:
        """Investigate a settlement exception using the AI investigation layer.

        Args:
            settlement_id: The Razorpay settlement ID
            exception_id: The exception record ID
            run_id: The reconciliation run ID
            exception_type: Type of settlement exception
            confidence: Confidence score for the exception

        Returns:
            Investigation result with structured evidence and AI analysis
        """
        # Create settlement exception dossier with structured evidence
        dossier = await self.settlement_intelligence.create_settlement_exception_dossier(
            settlement_id=settlement_id,
            exception_type=exception_type,
            confidence=confidence,
        )

        # Build investigation state with settlement-specific evidence
        investigation_state = self._build_settlement_investigation_state(
            settlement_id=settlement_id,
            exception_id=exception_id,
            run_id=run_id,
            dossier=dossier,
        )

        # Create minimal transaction objects for the investigation graph
        # The settlement itself is treated as a transaction for investigation purposes
        settlement_transaction = await self._create_settlement_transaction(settlement_id)

        # Run the investigation through the existing graph
        conclusion = await self.investigation_service.investigate(
            exception_id=exception_id,
            run_id=run_id,
            transactions=[settlement_transaction] if settlement_transaction else [],
            decision=None,  # Settlement exceptions don't have traditional match decisions
            investigation_id=f"setl_inv_{settlement_id}",
        )

        # Combine dossier evidence with investigation conclusion
        return {
            "settlement_id": settlement_id,
            "exception_id": exception_id,
            "dossier": dossier.to_dict(),
            "investigation": conclusion.model_dump(),
            "combined_evidence": self._combine_evidence(dossier, conclusion),
        }

    async def explain_settlement_with_ai(
        self,
        settlement_id: str,
    ) -> dict[str, Any]:
        """Provide AI-enhanced explanation of a settlement.

        This combines the deterministic settlement intelligence with AI investigation
        for cases where variance is detected or exceptions exist.
        """
        # Get the deterministic explanation first
        explanation = await self.settlement_intelligence.explain_settlement(settlement_id)

        # If there's variance, try to get AI insight
        if explanation.variance != Decimal("0"):
            # Check if there's an existing exception for this settlement
            from app.database.models import Exception as ExceptionORM
            from sqlalchemy import select

            stmt = select(ExceptionORM).where(
                ExceptionORM.evidence["settlement_id"].astext == settlement_id
            )
            result = await self.session.execute(stmt)
            exception = result.scalar_one_or_none()

            if exception:
                # Use existing investigation
                from app.database.models import Investigation as InvestigationORM
                inv_stmt = select(InvestigationORM).where(
                    InvestigationORM.exception_id == exception.id
                )
                inv_result = await self.session.execute(inv_stmt)
                investigation = inv_result.scalar_one_or_none()

                if investigation:
                    explanation.evidence["ai_investigation"] = {
                        "root_cause": investigation.root_cause,
                        "classification": investigation.classification,
                        "confidence": str(investigation.confidence),
                        "recommended_action": investigation.recommended_action,
                    }

        return explanation.to_dict()

    def _build_settlement_investigation_state(
        self,
        settlement_id: str,
        exception_id: str,
        run_id: str,
        dossier: SettlementExceptionDossier,
    ) -> InvestigationState:
        """Build investigation state with settlement-specific evidence."""
        return InvestigationState(
            investigation_id=f"setl_inv_{settlement_id}",
            exception_id=exception_id,
            run_id=run_id,
            decision=None,
            transactions=[],  # Settlements are handled differently
            transaction_evidence={
                "settlement_id": settlement_id,
                "financial_breakdown": dossier.evidence.get("financial_breakdown", {}),
                "transaction_linkage": dossier.evidence.get("transaction_linkage", {}),
                "bank_reconciliation": dossier.evidence.get("bank_reconciliation", {}),
                "variance": str(dossier.variance),
                "variance_type": dossier.evidence.get("financial_breakdown", {}).get("variance_type"),
                "exception_type": dossier.exception_type,
                "root_cause_candidates": dossier.root_cause_candidates,
            },
        )

    async def _create_settlement_transaction(self, settlement_id: str) -> Optional[Transaction]:
        """Create a Transaction object from settlement data for investigation."""
        from app.database.models import Transaction as TransactionORM
        from sqlalchemy import select
        from app.models.transaction import TransactionSource, TransactionStatus

        stmt = select(TransactionORM).where(
            TransactionORM.domain_transaction_id == settlement_id
        )
        result = await self.session.execute(stmt)
        settlement_orm = result.scalar_one_or_none()

        if not settlement_orm:
            return None

        return Transaction(
            txn_id=settlement_orm.domain_transaction_id,
            source=TransactionSource(settlement_orm.source),
            reference_number=settlement_orm.reference_number,
            amount=settlement_orm.amount,
            currency=settlement_orm.currency,
            timestamp=settlement_orm.timestamp,
            narration=settlement_orm.narration,
            fee=settlement_orm.fee,
            tax=settlement_orm.tax,
            status=TransactionStatus.PROCESSED,  # Settlements are typically processed
            order_id=settlement_orm.order_id,
            metadata=settlement_orm.meta_data,
        )

    def _combine_evidence(
        self,
        dossier: SettlementExceptionDossier,
        conclusion: Any,
    ) -> dict[str, Any]:
        """Combine settlement dossier evidence with investigation conclusion."""
        return {
            "settlement_financial_breakdown": dossier.evidence.get("financial_breakdown", {}),
            "transaction_linkage": dossier.evidence.get("transaction_linkage", {}),
            "bank_reconciliation": dossier.evidence.get("bank_reconciliation", {}),
            "variance_analysis": {
                "variance": str(dossier.variance),
                "variance_type": dossier.evidence.get("financial_breakdown", {}).get("variance_type"),
            },
            "investigation_conclusion": {
                "root_cause": conclusion.root_cause,
                "classification": conclusion.classification.value if hasattr(conclusion.classification, 'value') else str(conclusion.classification),
                "confidence": str(conclusion.confidence),
                "recommended_action": conclusion.recommended_action,
                "method": conclusion.method.value if hasattr(conclusion.method, 'value') else str(conclusion.method),
                "llm_invoked": conclusion.llm_invoked,
            },
            "root_cause_candidates": dossier.root_cause_candidates,
            "recommended_next_action": dossier.recommended_next_action,
        }

    async def get_settlement_for_investigation(
        self,
        settlement_id: str,
    ) -> dict[str, Any]:
        """Get settlement data formatted for investigation input.

        This provides the structured evidence that the LLM receives, ensuring
        it works with authoritative Sentinel data rather than inventing values.
        """
        explanation = await self.settlement_intelligence.explain_settlement(settlement_id)

        return {
            "settlement_id": settlement_id,
            "authoritative_financial_data": {
                "gross_amount": str(explanation.gross_amount),
                "fee_amount": str(explanation.fee_amount),
                "tax_amount": str(explanation.tax_amount),
                "expected_net_amount": str(explanation.net_amount),
                "bank_received_amount": str(explanation.bank_amount) if explanation.bank_amount else None,
                "variance": str(explanation.variance),
                "variance_type": explanation.variance_type.value,
            },
            "bank_reconciliation_status": {
                "settlement_status": explanation.settlement_status,
                "utr": explanation.utr,
                "bank_matched": explanation.bank_matched,
                "bank_transaction_id": explanation.bank_transaction_id,
                "bank_date": explanation.bank_date.isoformat() if explanation.bank_date else None,
            },
            "transaction_evidence": {
                "linked_transaction_count": explanation.linked_transaction_count,
                "matched_transaction_count": explanation.matched_transaction_count,
                "unmatched_transaction_count": explanation.unmatched_transaction_count,
                "sample_transaction_ids": explanation.transaction_ids[:10],
            },
            "constraints": {
                "llm_must_not_invent_amounts": True,
                "llm_must_use_authoritative_data": True,
                "llm_must_reference_actual_transaction_ids": True,
                "llm_must_declare_insufficient_evidence": True,
            },
        }
