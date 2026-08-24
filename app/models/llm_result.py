from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.exception_record import ExceptionCategory


class RecommendedAction(str, Enum):
    APPROVE_MATCH = "approve_match"
    FLAG_DUPLICATE = "flag_duplicate"
    REQUEST_CREDIT_NOTE = "request_credit_note"
    ESCALATE_MANUAL = "escalate_manual"
    WRITE_OFF = "write_off"
    INVESTIGATE_FURTHER = "investigate_further"


class LLMEvidenceItem(BaseModel):
    observation: str = Field(..., description="Observed factual point from data")
    source: str = Field(..., description="Source of observation (e.g. gateway, ledger, bank, historical)")
    relevance: str = Field(..., description="How this observation relates to the root cause")


class LLMInvestigationResult(BaseModel):
    """Strict structured Pydantic schema for LLM output."""
    root_cause: str = Field(..., min_length=10, max_length=500, description="Precise root cause of the anomaly")
    classification: str = Field(..., description="Exception category enum value string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in reasoning (0.0 - 1.0)")
    evidence: list[LLMEvidenceItem] = Field(..., min_length=1, description="List of evidence observations")
    financial_exposure: Decimal = Field(..., ge=0, description="Financial amount at risk")
    recommended_action: RecommendedAction = Field(..., description="Concrete resolution action")
    requires_human_review: bool = Field(..., description="Flag indicating human oversight requirement")
    reasoning_summary: str = Field(..., min_length=20, max_length=1500, description="Step-by-step reasoning")

    @field_validator("classification")
    @classmethod
    def validate_classification(cls, v: str) -> str:
        valid_categories = {e.value for e in ExceptionCategory}
        if v not in valid_categories:
            raise ValueError(f"classification must be one of {sorted(valid_categories)}, got '{v}'")
        return v
