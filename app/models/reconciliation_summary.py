from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReconciliationSummary(BaseModel):
    """Summary of a reconciliation run execution."""
    
    run_id: str = Field(..., description="Unique identifier for the reconciliation run")
    total_transactions: int = Field(..., description="Total number of transactions processed")
    deterministic_matches: int = Field(..., description="Number of deterministic matches found")
    ml_proposals: int = Field(..., description="Number of ML-based match proposals")
    manual_reviews: int = Field(..., description="Number of transactions requiring manual review")
    ambiguous: int = Field(..., description="Number of ambiguous cases")
    unresolved: int = Field(..., description="Number of unresolved transactions")
    rejected: int = Field(..., description="Number of rejected matches")
    exceptions_created: int = Field(..., description="Number of exceptions created")
    completed_successfully: bool = Field(..., description="Whether the run completed without errors")
    started_at: datetime = Field(..., description="Timestamp when the run started")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the run completed")
