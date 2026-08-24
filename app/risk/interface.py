from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from app.models.exception_record import ExceptionCategory


class RiskBucket(str, Enum):
    LOW = "low"            # < 10,000 INR
    MEDIUM = "medium"      # 10,000 - 50,000 INR
    HIGH = "high"          # 50,000 - 200,000 INR
    CRITICAL = "critical"  # > 200,000 INR


@dataclass
class RiskInput:
    """Input parameters for deterministic risk evaluation."""
    category: ExceptionCategory
    financial_exposure: Decimal
    confidence: Decimal
    is_duplicate: bool = False
    is_high_value: bool = False
    historical_frequency: int = 0


@dataclass
class RiskOutput:
    """Deterministic risk assessment output."""
    risk_score: Decimal              # 0.00 to 1.00
    expected_cost: Decimal           # Exposure * risk_score
    risk_bucket: RiskBucket
    requires_immediate_review: bool
    risk_summary: str
