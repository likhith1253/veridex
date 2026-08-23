from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationRun(BaseModel):
    run_id: str = Field(..., description="Unique run identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    ended_at: Optional[datetime] = Field(None, description="End timestamp")
    status: RunStatus = Field(default=RunStatus.PENDING, description="Run status")
    gateway_count: int = Field(default=0, description="Number of gateway transactions")
    ledger_count: int = Field(default=0, description="Number of ledger transactions")
    bank_count: int = Field(default=0, description="Number of bank transactions")
    match_count: int = Field(default=0, description="Number of matches")
    exception_count: int = Field(default=0, description="Number of exceptions")
    summary: Optional[str] = Field(None, description="Run summary")
