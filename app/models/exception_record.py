from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExceptionCategory(str, Enum):
    CURRENCY_ROUNDING = "currency_rounding"
    PARTIAL_REFUND = "partial_refund"
    DELAYED_SETTLEMENT = "delayed_settlement"
    DUPLICATE_ENTRY = "duplicate_entry"
    FEE_MISMATCH = "fee_mismatch"
    WRONG_REFERENCE = "wrong_reference"
    AMBIGUOUS_MATCH = "ambiguous_match"
    UNEXPLAINED = "unexplained"


class ExceptionRecord(BaseModel):
    transaction_id: str = Field(..., description="Associated transaction ID")
    category: ExceptionCategory = Field(..., description="Root-cause category")
    confidence: Decimal = Field(..., description="Classification confidence (0-1)", ge=0, le=1)
    financial_exposure: Decimal = Field(..., description="Financial exposure amount", ge=0)
    expected_cost: Decimal = Field(..., description="Expected cost of error", ge=0)
    explanation: str = Field(..., description="Explanation of the exception")
    evidence: Optional[dict[str, Any]] = Field(None, description="Supporting evidence")
    recommended_action: Optional[str] = Field(None, description="Recommended action")
    resolved: bool = Field(default=False, description="Resolution status")
