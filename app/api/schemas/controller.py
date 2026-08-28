"""
Pydantic API Schemas for the Finance Controller layer.
"""

from decimal import Decimal
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class BatchRecordItem(BaseModel):
    txn_id: str = Field(..., description="Unique transaction ID within source")
    amount: Decimal = Field(..., description="Monetary transaction amount", gt=Decimal("0.0"))
    currency: str = Field("INR", description="3-letter currency code")
    order_id: Optional[str] = Field(None, description="Associated Order ID")
    reference_number: Optional[str] = Field(None, description="UTR or Bank Reference")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")
    fee: Optional[Decimal] = Field(Decimal("0.0"), description="Deducted fee", ge=Decimal("0.0"))
    tax: Optional[Decimal] = Field(Decimal("0.0"), description="Deducted tax", ge=Decimal("0.0"))
    narration: Optional[str] = Field(None, description="Transaction narration string")


class BatchIngestRequest(BaseModel):
    batch_id: Optional[str] = Field(None, description="Optional batch tracking ID")
    gateway_records: list[BatchRecordItem] = Field(default_factory=list, description="Gateway settlement records")
    ledger_records: list[BatchRecordItem] = Field(default_factory=list, description="Internal ledger records")
    bank_records: list[BatchRecordItem] = Field(default_factory=list, description="Bank statement records")


class BatchIngestResponse(BaseModel):
    batch_id: str
    run_id: str
    records_received: int
    records_normalized: int
    processing_status: str
    processing_duration_ms: float
    reconciliation_status: str
    auto_matched_count: int
    ml_recovered_count: int
    manual_review_count: int
    unresolved_count: int


class SingleTransactionIngestRequest(BaseModel):
    txn_id: str = Field(..., min_length=1, description="Unique transaction ID")
    source: Literal["gateway", "ledger", "bank"] = Field(..., description="Transaction feed source")
    amount: Decimal = Field(..., description="Monetary transaction amount", gt=Decimal("0.0"))
    currency: str = Field("INR", description="3-letter currency code")
    order_id: Optional[str] = Field(None, description="Associated Order ID")
    reference_number: Optional[str] = Field(None, description="UTR or Bank Reference")
    narration: Optional[str] = Field(None, description="Transaction narration string")


class HumanDecisionRequest(BaseModel):
    action: Literal["approve", "reject", "escalate", "resolve"] = Field(..., description="Human action")
    actor: str = Field("finance_controller_user", description="Identifier of human decision-maker")
    reason: Optional[str] = Field(None, description="Optional explanation for audit log")


class FailureSimulationRequest(BaseModel):
    scenario: Literal[
        "corrupted_utr",
        "delayed_settlement",
        "duplicate",
        "ambiguous",
        "groq_unavailable",
        "groq_api_down",
        "db_timeout",
        "qdrant_unreachable",
    ] = Field(..., description="Failure simulation scenario")
    amount: Decimal = Field(Decimal("50000.00"), description="Transaction amount for test scenario", ge=Decimal("0.01"))


class CopilotQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Finance question to resolve using grounded controller data")
    run_id: Optional[str] = Field(None, description="Optional run scope for the query")


class CopilotQueryResponse(BaseModel):
    question: str
    answer: str
    interpretation: str
    recommendation: str
    fact_summary: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "deterministic"
    needs_human_review: bool = False


class CopilotBriefRequest(BaseModel):
    run_id: Optional[str] = Field(None, description="Optional run scope for the brief")


class CopilotBriefResponse(BaseModel):
    status: str
    money_at_risk_inr: float
    reconciliation_match_rate_percent: float
    highest_risk_exception: Optional[str]
    why: str
    recommended_action: str
    human_review_required: bool
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    source_health: str = "HEALTHY"
    summary: dict[str, Any] = Field(default_factory=dict)
