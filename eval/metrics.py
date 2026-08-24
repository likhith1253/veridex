from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default on zero denominator."""
    if denominator == 0.0 or denominator == 0:
        return default
    return float(numerator) / float(denominator)


@dataclass
class MatchingMetrics:
    """Core transaction-level matching metrics."""
    total_proposed_matches: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    false_match_rate: float = 0.0
    unresolved_rate: float = 0.0
    accuracy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_proposed_matches": self.total_proposed_matches,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "false_match_rate": round(self.false_match_rate, 4),
            "unresolved_rate": round(self.unresolved_rate, 4),
            "accuracy": round(self.accuracy, 4),
        }


@dataclass
class DecisionDistributionMetrics:
    """Metrics tracking reconciliation decision distributions and calibrated precision."""
    total_decisions: int = 0
    auto_match_count: int = 0
    auto_match_rate: float = 0.0
    auto_match_precision: float = 0.0
    manual_review_count: int = 0
    manual_review_rate: float = 0.0
    ambiguous_count: int = 0
    ambiguous_rate: float = 0.0
    reject_count: int = 0
    reject_rate: float = 0.0
    unresolved_count: int = 0
    unresolved_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "auto_match": {
                "count": self.auto_match_count,
                "rate": round(self.auto_match_rate, 4),
                "precision": round(self.auto_match_precision, 4),
            },
            "manual_review": {
                "count": self.manual_review_count,
                "rate": round(self.manual_review_rate, 4),
            },
            "ambiguous": {
                "count": self.ambiguous_count,
                "rate": round(self.ambiguous_rate, 4),
            },
            "reject": {
                "count": self.reject_count,
                "rate": round(self.reject_rate, 4),
            },
            "unresolved": {
                "count": self.unresolved_count,
                "rate": round(self.unresolved_rate, 4),
            },
        }


@dataclass
class RulePerformanceMetrics:
    """Metrics for an individual matching rule."""
    rule_name: str
    matches_count: int = 0
    true_positives: int = 0
    false_positives: int = 0
    precision: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "matches_count": self.matches_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "precision": round(self.precision, 4),
        }


@dataclass
class ScenarioPerformanceMetrics:
    """Metrics broken down by corruption/scenario type."""
    scenario: str
    total_records: int = 0
    matched_records: int = 0
    correct_matches: int = 0       # TP
    false_matches: int = 0         # FP
    false_negatives: int = 0       # FN
    unresolved_records: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "total_records": self.total_records,
            "matched_records": self.matched_records,
            "correct_matches": self.correct_matches,
            "false_matches": self.false_matches,
            "false_negatives": self.false_negatives,
            "unresolved_records": self.unresolved_records,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
        }


@dataclass
class RiskBucketMetrics:
    """Metrics broken down by monetary value / risk bucket."""
    bucket_name: str
    min_amount: Decimal
    max_amount: Optional[Decimal]
    transaction_count: int = 0
    total_exposure_amount: Decimal = Decimal("0")
    matches_count: int = 0
    true_positives: int = 0
    false_positives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    false_positive_exposure: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket_name": self.bucket_name,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount) if self.max_amount is not None else "inf",
            "transaction_count": self.transaction_count,
            "total_exposure_amount": str(self.total_exposure_amount),
            "matches_count": self.matches_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "false_positive_exposure": str(self.false_positive_exposure),
        }


@dataclass
class EvaluationResult:
    """Comprehensive evaluation results container."""
    dataset_name: str
    total_transactions: int
    execution_time_seconds: float
    overall_matching: MatchingMetrics
    decision_distribution: DecisionDistributionMetrics
    rule_performance: dict[str, RulePerformanceMetrics] = field(default_factory=dict)
    scenario_performance: dict[str, ScenarioPerformanceMetrics] = field(default_factory=dict)
    risk_performance: dict[str, RiskBucketMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": {
                "name": self.dataset_name,
                "total_transactions": self.total_transactions,
                "execution_time_seconds": round(self.execution_time_seconds, 4),
            },
            "overall": self.overall_matching.to_dict(),
            "decision_distribution": self.decision_distribution.to_dict(),
            "deterministic_rules": {
                name: m.to_dict() for name, m in self.rule_performance.items()
            },
            "scenarios": {
                name: m.to_dict() for name, m in self.scenario_performance.items()
            },
            "risk_buckets": {
                name: m.to_dict() for name, m in self.risk_performance.items()
            },
        }
