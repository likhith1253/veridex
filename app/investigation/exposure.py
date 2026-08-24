from decimal import Decimal
from typing import Optional

from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory
from app.models.transaction import Transaction


class ExposureCalculator:
    """Calculates financial exposure and determines LLM escalation eligibility."""

    # High value threshold above which LLM reasoning is conditionally permitted for ambiguous cases
    HIGH_VALUE_THRESHOLD = Decimal("100000")

    @classmethod
    def calculate_exposure(cls, transactions: list[Transaction]) -> Decimal:
        """Calculate total monetary exposure from involved transactions."""
        if not transactions:
            return Decimal("0")
        # In financial reconciliation, exposure is the maximum transaction amount at risk
        return max(t.amount for t in transactions)

    @classmethod
    def should_escalate_to_llm(
        cls,
        financial_exposure: Decimal,
        category: ExceptionCategory,
        deterministic_confidence: Decimal,
        is_duplicate: bool,
        decision: Optional[DecisionResult] = None,
    ) -> tuple[bool, str]:
        """Determine if an exception should be escalated to LLM reasoning.

        Returns:
            (should_escalate, escalation_reason)
        """
        # 1. Ambiguous match decisions always benefit from semantic reasoning
        if decision and decision.action == DecisionAction.AMBIGUOUS:
            return True, "Ambiguous match with multiple competing candidate pairs"

        # 2. Unexplained category with no confident deterministic classification
        if category == ExceptionCategory.UNEXPLAINED:
            return True, "Unexplained anomaly with no matching deterministic rule"

        # 3. High value transactions with low/medium deterministic confidence
        if financial_exposure >= cls.HIGH_VALUE_THRESHOLD and deterministic_confidence < Decimal("0.85"):
            return True, f"High financial exposure (INR {financial_exposure:,.2f}) with moderate confidence"

        # 4. Duplicate cases that have ambiguous source attributions
        if is_duplicate and deterministic_confidence < Decimal("0.70"):
            return True, "Complex duplicate entry with unresolved multi-source attribution"

        return False, "Resolved by deterministic investigation rules"
