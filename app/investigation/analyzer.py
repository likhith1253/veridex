from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from app.investigation.evidence import InvestigationEvidence
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory
from app.models.transaction import Transaction, TransactionSource


@dataclass
class DeterministicAnalysisResult:
    """Result of deterministic rule analysis."""
    detected_category: ExceptionCategory
    confidence: Decimal
    root_cause: str
    explanation: str
    recommended_action: str
    requires_llm_escalation: bool
    evidence_summary: dict[str, Any]


class DeterministicAnalyzer:
    """Evaluates deterministic investigation rules against transaction evidence."""

    @classmethod
    def analyze(
        cls,
        evidence: InvestigationEvidence,
        transactions: list[Transaction],
        decision: Optional[DecisionResult] = None,
    ) -> DeterministicAnalysisResult:
        """Run hierarchical deterministic rules to establish root cause."""
        # 1. Check for Ambiguous decision
        if decision and decision.action == DecisionAction.AMBIGUOUS:
            return DeterministicAnalysisResult(
                detected_category=ExceptionCategory.AMBIGUOUS_MATCH,
                confidence=Decimal("0.50"),
                root_cause="Competing candidate matches detected during reconciliation",
                explanation=f"Decision policy marked transaction as ambiguous: {decision.reason}",
                recommended_action="escalate_manual",
                requires_llm_escalation=True,
                evidence_summary={
                    "rule": "ambiguous_decision_policy",
                    "competing_candidates": len(transactions),
                },
            )

        # 2. Check for Duplicate Entry
        if evidence.has_duplicate_identifiers:
            return DeterministicAnalysisResult(
                detected_category=ExceptionCategory.DUPLICATE_ENTRY,
                confidence=Decimal("0.95"),
                root_cause="Duplicate transaction records detected sharing identifiers",
                explanation=(
                    f"Multiple transaction records found with identical order/reference "
                    f"({len(transactions)} transactions involved across feeds)."
                ),
                recommended_action="flag_duplicate",
                requires_llm_escalation=False,
                evidence_summary={
                    "rule": "duplicate_record_detector",
                    "duplicate_count": len(transactions),
                    "unique_amounts": [str(a) for a in evidence.unique_amounts],
                },
            )

        # 3. Check for Currency Rounding
        if evidence.has_amount_difference and Decimal("0") < evidence.max_amount_delta <= Decimal("1.00"):
            return DeterministicAnalysisResult(
                detected_category=ExceptionCategory.CURRENCY_ROUNDING,
                confidence=Decimal("0.98"),
                root_cause="Minor currency rounding discrepancy within tolerance (<= 1.00)",
                explanation=(
                    f"Observed amount discrepancy of INR {evidence.max_amount_delta} "
                    f"is consistent with standard rounding variations."
                ),
                recommended_action="write_off",
                requires_llm_escalation=False,
                evidence_summary={
                    "rule": "rounding_tolerance",
                    "amount_delta": str(evidence.max_amount_delta),
                },
            )

        # 4. Check for Fee / Tax Mismatch
        if evidence.has_fee_difference:
            return DeterministicAnalysisResult(
                detected_category=ExceptionCategory.FEE_MISMATCH,
                confidence=Decimal("0.90"),
                root_cause="Payment gateway fee/tax calculation mismatch with settled bank amount",
                explanation=(
                    f"Gateway expected settlement of INR {evidence.expected_bank_amount} differs "
                    f"from observed bank settlement of INR {evidence.actual_bank_amount} "
                    f"(discrepancy: INR {evidence.fee_discrepancy})."
                ),
                recommended_action="request_credit_note",
                requires_llm_escalation=False,
                evidence_summary={
                    "rule": "fee_tax_equation",
                    "expected_bank_amount": str(evidence.expected_bank_amount),
                    "actual_bank_amount": str(evidence.actual_bank_amount),
                    "fee_discrepancy": str(evidence.fee_discrepancy),
                },
            )

        # 5. Check for Partial Refund
        if len(evidence.gateway_snapshots) >= 1 and len(evidence.ledger_snapshots) >= 1:
            gw = evidence.gateway_snapshots[0]
            ld = evidence.ledger_snapshots[0]
            if ld.amount < gw.amount:
                refund_amount = gw.amount - ld.amount
                return DeterministicAnalysisResult(
                    detected_category=ExceptionCategory.PARTIAL_REFUND,
                    confidence=Decimal("0.88"),
                    root_cause="Partial refund or deduction applied on order",
                    explanation=(
                        f"Ledger amount (INR {ld.amount}) is less than original gateway amount "
                        f"(INR {gw.amount}) indicating an adjusted partial refund of INR {refund_amount}."
                    ),
                    recommended_action="approve_match",
                    requires_llm_escalation=False,
                    evidence_summary={
                        "rule": "partial_refund_relation",
                        "original_amount": str(gw.amount),
                        "settled_amount": str(ld.amount),
                        "refund_amount": str(refund_amount),
                    },
                )

        # 6. Check for Delayed Settlement
        if evidence.time_span_seconds > (2 * 86400):  # More than 2 days
            return DeterministicAnalysisResult(
                detected_category=ExceptionCategory.DELAYED_SETTLEMENT,
                confidence=Decimal("0.85"),
                root_cause="Delayed settlement timing across gateway and bank",
                explanation=(
                    f"Transactions span {evidence.time_span_seconds / 86400:.1f} days between "
                    f"initiation and bank settlement."
                ),
                recommended_action="approve_match",
                requires_llm_escalation=False,
                evidence_summary={
                    "rule": "delayed_settlement_timing",
                    "time_span_days": evidence.time_span_seconds / 86400,
                },
            )

        # 7. Check for Wrong Reference
        if evidence.has_reference_mismatch and len(evidence.unique_orders) == 1:
            return DeterministicAnalysisResult(
                detected_category=ExceptionCategory.WRONG_REFERENCE,
                confidence=Decimal("0.80"),
                root_cause="Mismatched external reference / UTR across feeds despite matching order ID",
                explanation=(
                    f"Order ID matches ({evidence.unique_orders[0]}), but external references "
                    f"differ across feeds: {evidence.unique_references}."
                ),
                recommended_action="investigate_further",
                requires_llm_escalation=False,
                evidence_summary={
                    "rule": "reference_inconsistency",
                    "order_id": evidence.unique_orders[0],
                    "references": evidence.unique_references,
                },
            )

        # 8. Unexplained / Default Fallback -> Escalate to LLM
        return DeterministicAnalysisResult(
            detected_category=ExceptionCategory.UNEXPLAINED,
            confidence=Decimal("0.30"),
            root_cause="Unexplained reconciliation exception requiring deeper semantic reasoning",
            explanation="Deterministic rules could not establish a conclusive financial explanation.",
            recommended_action="escalate_manual",
            requires_llm_escalation=True,
            evidence_summary={
                "rule": "unexplained_fallback",
                "unique_amounts": [str(a) for a in evidence.unique_amounts],
            },
        )
