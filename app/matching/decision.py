from decimal import Decimal
from typing import Any, Optional

from app.matching.financial_utils import calculate_expected_bank_amount
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.match_result import MatchResult
from app.models.transaction import Transaction, TransactionSource

# Decision threshold constants
DETERMINISTIC_AUTO_MATCH_THRESHOLD = Decimal("0.95")
ML_PROPOSE_MATCH_THRESHOLD = 0.90
ML_MANUAL_REVIEW_THRESHOLD = 0.70
CANDIDATE_MARGIN_THRESHOLD = 0.10


class DecisionPolicy:
    """Policy layer combining deterministic and ML evidence into reconciliation decisions."""

    def __init__(self, thresholds: Optional[dict] = None):
        """Initialize with optional custom thresholds.
        
        Args:
            thresholds: Optional dict overriding default threshold values.
        """
        self.thresholds = thresholds or {}

    def make_decision(
        self,
        txn1: Transaction,
        txn2: Transaction,
        deterministic_result: Optional[MatchResult],
        ml_probability: float,
        transactions_by_source: dict[TransactionSource, list[Transaction]],
    ) -> DecisionResult:
        """Make a decision combining deterministic and ML evidence.
        
        Args:
            txn1: First transaction.
            txn2: Second transaction.
            deterministic_result: Optional deterministic match result.
            ml_probability: ML probability score for this pair.
            transactions_by_source: All transactions grouped by source.
            
        Returns:
            DecisionResult with action, confidence, and evidence.
        """
        # Check for currency mismatch first (hard reject)
        if txn1.currency != txn2.currency:
            return self._build_reject_result(
                [txn1.txn_id, txn2.txn_id],
                "Currency mismatch",
                {"currency1": txn1.currency, "currency2": txn2.currency},
            )

        # Check for financial contradiction
        financial_consistent, expected_amount, observed_amount = self.check_financial_consistency(
            txn1, txn2
        )
        if not financial_consistent:
            return self._build_reject_result(
                [txn1.txn_id, txn2.txn_id],
                "Financial contradiction",
                {
                    "expected_amount": str(expected_amount) if expected_amount else None,
                    "observed_amount": str(observed_amount) if observed_amount else None,
                },
            )

        # If we have a high-confidence deterministic result, use it
        if deterministic_result and deterministic_result.confidence >= DETERMINISTIC_AUTO_MATCH_THRESHOLD:
            return self.evaluate_deterministic(deterministic_result)

        # Otherwise, evaluate ML probability
        return self.evaluate_ml(txn1, txn2, ml_probability, transactions_by_source)

    def evaluate_deterministic(self, match_result: MatchResult) -> DecisionResult:
        """Evaluate a deterministic match result.
        
        Args:
            match_result: Deterministic match result.
            
        Returns:
            DecisionResult with AUTO_MATCH action for high-confidence deterministic matches.
        """
        confidence = match_result.confidence
        evidence = {
            "rule_used": match_result.reason,
            "deterministic_confidence": str(confidence),
        }
        if match_result.evidence:
            evidence.update(match_result.evidence)

        return DecisionResult(
            transaction_ids=match_result.transaction_ids,
            action=DecisionAction.AUTO_MATCH,
            confidence=confidence,
            evidence=evidence,
            reason=f"High-confidence deterministic match: {match_result.reason}",
        )

    def evaluate_ml(
        self,
        txn1: Transaction,
        txn2: Transaction,
        probability: float,
        transactions_by_source: dict[TransactionSource, list[Transaction]],
    ) -> DecisionResult:
        """Evaluate ML probability for a transaction pair.
        
        Args:
            txn1: First transaction.
            txn2: Second transaction.
            probability: ML probability score.
            transactions_by_source: All transactions grouped by source.
            
        Returns:
            DecisionResult based on ML probability and candidate margin.
        """
        # Check candidate margin (need to find all candidates for txn1)
        margin, second_best = self.check_candidate_margin(
            txn1, txn2, probability, transactions_by_source
        )

        evidence = {
            "ml_probability": probability,
            "second_best_probability": second_best,
            "candidate_margin": margin,
        }

        # High probability with strong margin
        if probability >= ML_PROPOSE_MATCH_THRESHOLD:
            if margin is None or margin >= CANDIDATE_MARGIN_THRESHOLD:
                return DecisionResult(
                    transaction_ids=[txn1.txn_id, txn2.txn_id],
                    action=DecisionAction.PROPOSE_MATCH,
                    confidence=Decimal(str(probability)),
                    evidence=evidence,
                    reason=f"High ML probability with strong margin: {probability:.3f}",
                )
            else:
                return DecisionResult(
                    transaction_ids=[txn1.txn_id, txn2.txn_id],
                    action=DecisionAction.AMBIGUOUS,
                    confidence=Decimal(str(probability)),
                    evidence=evidence,
                    reason=f"High ML probability but small candidate margin: {margin:.3f}",
                )

        # Medium probability
        if probability >= ML_MANUAL_REVIEW_THRESHOLD:
            return DecisionResult(
                transaction_ids=[txn1.txn_id, txn2.txn_id],
                action=DecisionAction.MANUAL_REVIEW,
                confidence=Decimal(str(probability)),
                evidence=evidence,
                reason=f"Medium ML probability: {probability:.3f}",
            )

        # Low probability
        return DecisionResult(
            transaction_ids=[txn1.txn_id, txn2.txn_id],
            action=DecisionAction.UNRESOLVED,
            confidence=Decimal(str(probability)),
            evidence=evidence,
            reason=f"Low ML probability: {probability:.3f}",
        )

    def check_financial_consistency(
        self, txn1: Transaction, txn2: Transaction
    ) -> tuple[bool, Optional[Decimal], Optional[Decimal]]:
        """Check if two transactions are financially consistent.
        
        Args:
            txn1: First transaction.
            txn2: Second transaction.
            
        Returns:
            Tuple of (is_consistent, expected_amount, observed_amount).
        """
        # If amounts match exactly, consistent
        if txn1.amount == txn2.amount:
            return True, None, None

        # If one is gateway and one is bank, check fee/tax adjustment
        gateway_txn = None
        bank_txn = None

        if txn1.source == TransactionSource.GATEWAY and txn2.source == TransactionSource.BANK:
            gateway_txn = txn1
            bank_txn = txn2
        elif txn2.source == TransactionSource.GATEWAY and txn1.source == TransactionSource.BANK:
            gateway_txn = txn2
            bank_txn = txn1

        if gateway_txn and bank_txn:
            expected_bank = calculate_expected_bank_amount(gateway_txn)
            if expected_bank and bank_txn.amount == expected_bank:
                return True, expected_bank, bank_txn.amount
            else:
                return False, expected_bank, bank_txn.amount

        # Otherwise, amounts don't match and no valid adjustment
        return False, txn1.amount, txn2.amount

    def check_candidate_margin(
        self,
        txn1: Transaction,
        txn2: Transaction,
        probability: float,
        transactions_by_source: dict[TransactionSource, list[Transaction]],
    ) -> tuple[float, Optional[float]]:
        """Check if the best candidate has a sufficient margin over second-best.
        
        Args:
            txn1: Query transaction.
            txn2: Best candidate transaction.
            probability: ML probability for the best candidate.
            transactions_by_source: All transactions grouped by source.
            
        Returns:
            Tuple of (margin, second_best_probability). Margin is None if only one candidate.
        """
        # Find all candidates from the same source as txn2
        candidates = transactions_by_source.get(txn2.source, [])
        
        # If only one candidate, margin doesn't apply
        if len(candidates) <= 1:
            return float("inf"), None

        # In a real implementation, we would compute ML probabilities for all candidates
        # and find the second-best. For now, we assume the provided probability is the best
        # and we don't have access to other probabilities.
        # This is a placeholder - the actual ML scorer would provide all probabilities.
        return float("inf"), None

    def _build_reject_result(
        self, transaction_ids: list[str], reason: str, evidence: dict[str, Any]
    ) -> DecisionResult:
        """Build a REJECT decision result.
        
        Args:
            transaction_ids: Transaction IDs involved.
            reason: Rejection reason.
            evidence: Supporting evidence.
            
        Returns:
            DecisionResult with REJECT action.
        """
        return DecisionResult(
            transaction_ids=transaction_ids,
            action=DecisionAction.REJECT,
            confidence=Decimal("0"),
            evidence=evidence,
            reason=reason,
        )
