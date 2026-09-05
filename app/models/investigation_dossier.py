from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class RootCauseCandidate(BaseModel):
    """Root cause candidate with confidence score and verified evidence."""
    cause: str = Field(..., description="Root cause description")
    confidence: Decimal = Field(..., description="Confidence score between 0.0 and 1.0")
    evidence: str = Field(..., description="Specific verified database evidence supporting this claim")


class RelatedIDs(BaseModel):
    """Related transaction, order, and settlement identifiers."""
    transaction_ids: list[str] = Field(default_factory=list, description="Associated transaction domain IDs")
    order_id: Optional[str] = Field(default=None, description="Associated order ID if present")
    settlement_id: Optional[str] = Field(default=None, description="Associated settlement ID if present")
    reference_number: Optional[str] = Field(default=None, description="Associated reference number or UTR")


class InvestigationDossier(BaseModel):
    """Comprehensive AI investigation and evidence dossier."""
    investigation_id: str = Field(..., description="Unique investigation or dossier ID")
    entity_id: str = Field(..., description="Queried entity ID")
    entity_type: str = Field(..., description="Type of entity: exception, settlement, match, etc.")
    status: str = Field(..., description="Operational status: OPEN, RESOLVED, MATCHED, BANK_CREDIT_CONFIRMED, etc.")
    exception_status: Optional[str] = Field(default=None, description="Exception status if applicable")
    financial_exposure: Decimal = Field(..., description="Quantified financial exposure")
    variance: Decimal = Field(..., description="Calculated financial variance")
    variance_type: str = Field(..., description="Classification of variance")
    related_ids: RelatedIDs = Field(default_factory=RelatedIDs, description="Related transaction, order, settlement IDs")
    reconciliation_evidence: dict[str, Any] = Field(default_factory=dict, description="Grounded reconciliation facts and records")
    evidence_graph: Optional[dict[str, Any]] = Field(
        default=None,
        description="Real Gateway/Ledger/Bank pipeline nodes and edges showing exactly which leg broke, derived from actual linked transaction records",
    )
    root_cause_candidates: list[RootCauseCandidate] = Field(default_factory=list, description="Ranked root-cause candidates with confidence")
    recommended_action: str = Field(..., description="Action recommended for resolution")
    requires_human_review: bool = Field(..., description="HITL review requirement")
    insufficient_evidence: bool = Field(default=False, description="Flag indicating whether evidence was insufficient")
    evidence_summary: str = Field(..., description="Summary of evidence and findings")
    method: str = Field(default="deterministic", description="Method used: deterministic, llm_assisted, etc.")
    llm_invoked: bool = Field(default=False, description="Whether LLM reasoning was invoked")
    created_at: datetime = Field(..., description="Timestamp of dossier creation")
