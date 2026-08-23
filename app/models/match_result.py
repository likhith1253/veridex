from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MatchType(str, Enum):
    EXACT = "exact"
    PROBABLE = "probable"
    PARTIAL = "partial"
    NONE = "none"


class MatchResult(BaseModel):
    transaction_ids: list[str] = Field(..., description="List of matched transaction IDs")
    confidence: Decimal = Field(..., description="Match confidence score (0-1)", ge=0, le=1)
    reason: str = Field(..., description="Explanation of the match")
    match_type: MatchType = Field(..., description="Type of match")
    evidence: Optional[dict[str, Any]] = Field(None, description="Supporting evidence")
    recommended_action: Optional[str] = Field(None, description="Recommended action")
