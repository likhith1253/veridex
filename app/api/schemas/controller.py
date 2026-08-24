"""
Pydantic API Schemas for the Finance Controller layer.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class BatchRecordItem(BaseModel):
    txn_id: str = Field(..., description="Unique transaction ID within source")
    amount: float = Field(..., description="Monetary transaction amount", ge=0.0)
    currency: str = Field("INR", description="3-letter currency code")
    order_id: Optional[str] = Field(None, description="Associated Order ID")
    reference_number: Optional[str] = Field(None, description="UTR or Bank Reference")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")
    fee: Optional[float] = Field(0.0, description="Deducted fee")
    tax: Optional[float] = Field(0.0, description="Deducted tax")
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


class HumanDecisionRequest(BaseModel):
    action: str = Field(..., description="Human action: 'approve', 'reject', 'escalate', 'resolve'")
    actor: str = Field("finance_controller_user", description="Identifier of human decision-maker")
    reason: Optional[str] = Field(None, description="Optional explanation for audit log")


class FailureSimulationRequest(BaseModel):
    scenario: str = Field(..., description="Failure scenario: 'corrupted_utr', 'delayed_settlement', 'duplicate', 'ambiguous', 'groq_unavailable'")
    amount: float = Field(50000.0, description="Transaction amount for test scenario")
