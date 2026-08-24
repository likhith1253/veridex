from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import InvestigationMethod, InvestigationStatus


class InvestigationResponse(BaseModel):
    """Response schema for investigation retrieval."""
    investigation_id: str = Field(..., description="Unique investigation identifier")
    exception_id: str = Field(..., description="Associated exception ID")
    run_id: str = Field(..., description="Reconciliation run ID")
    method: InvestigationMethod = Field(..., description="Method used for investigation")
    root_cause: str = Field(..., description="Root cause explanation")
    classification: ExceptionCategory = Field(..., description="Exception category classification")
    confidence: Decimal = Field(..., description="Confidence score")
    financial_exposure: Decimal = Field(..., description="Calculated financial exposure")
    expected_cost: Decimal = Field(..., description="Calculated expected cost of error")
    recommended_action: str = Field(..., description="Recommended resolution action")
    requires_human_review: bool = Field(..., description="Whether human review is required")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Structured evidence dictionary")
    llm_invoked: bool = Field(default=False, description="Whether LLM was invoked")
    llm_error: Optional[str] = Field(default=None, description="LLM error if any")
    historical_cases_used: int = Field(default=0, description="Number of historical cases used")
    status: InvestigationStatus = Field(default=InvestigationStatus.COMPLETED, description="Status of investigation")
    created_at: datetime = Field(..., description="Timestamp of investigation creation")
