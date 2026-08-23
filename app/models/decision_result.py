from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DecisionAction(str, Enum):
    """Action to take based on reconciliation decision."""
    AUTO_MATCH = "auto_match"
    PROPOSE_MATCH = "propose_match"
    MANUAL_REVIEW = "manual_review"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    REJECT = "reject"


class DecisionResult(BaseModel):
    """Decision result combining deterministic and ML evidence."""
    transaction_ids: list[str] = Field(..., description="List of transaction IDs involved")
    action: DecisionAction = Field(..., description="Recommended action")
    confidence: Decimal = Field(..., description="Confidence score (0-1)", ge=0, le=1)
    evidence: dict[str, Any] = Field(..., description="Supporting evidence with standardized keys")
    reason: str = Field(..., description="Explanation of the decision")
