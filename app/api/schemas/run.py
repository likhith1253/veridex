from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.reconciliation_run import RunStatus


class RunSummaryResponse(BaseModel):
    """Response schema for reconciliation run summary."""
    run_id: str = Field(..., description="Unique run identifier")
    status: RunStatus = Field(..., description="Run status")
    started_at: Optional[datetime] = Field(None, description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    total_transactions: int = Field(..., description="Total transactions processed across all feeds")
    gateway_count: int = Field(..., description="Number of gateway transactions")
    ledger_count: int = Field(..., description="Number of ledger transactions")
    bank_count: int = Field(..., description="Number of bank transactions")
    match_count: int = Field(..., description="Number of matched transactions")
    exception_count: int = Field(..., description="Number of exceptions generated")
    summary: Optional[str] = Field(None, description="Run execution summary")
