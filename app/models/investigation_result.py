from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.exception_record import ExceptionCategory


class InvestigationMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"
    FALLBACK = "fallback"  # LLM failed or timed out, deterministic fallback used


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationConclusion(BaseModel):
    """Structured conclusion representing the final output of an investigation."""
    investigation_id: str = Field(..., description="Unique investigation identifier / idempotency key")
    exception_id: str = Field(..., description="Associated exception ID")
    run_id: str = Field(..., description="Reconciliation run ID")
    method: InvestigationMethod = Field(..., description="Method used for investigation")
    root_cause: str = Field(..., description="Root cause summary")
    classification: ExceptionCategory = Field(..., description="Root-cause exception category")
    confidence: Decimal = Field(..., description="Confidence score (0-1)", ge=0, le=1)
    financial_exposure: Decimal = Field(..., description="Financial exposure amount", ge=0)
    expected_cost: Decimal = Field(..., description="Expected cost / risk assessment", ge=0)
    recommended_action: str = Field(..., description="Action recommended for resolution")
    requires_human_review: bool = Field(default=False, description="Whether human review is required")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Structured evidence dictionary")
    llm_invoked: bool = Field(default=False, description="Whether an LLM was invoked")
    llm_error: Optional[str] = Field(default=None, description="LLM invocation error if any")
    historical_cases_used: int = Field(default=0, description="Number of historical Qdrant cases used")
    status: InvestigationStatus = Field(default=InvestigationStatus.COMPLETED, description="Status of investigation")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
