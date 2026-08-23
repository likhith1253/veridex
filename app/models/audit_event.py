from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    run_id: str = Field(..., description="Reconciliation run identifier")
    transaction_id: Optional[str] = Field(None, description="Associated transaction ID")
    stage: str = Field(..., description="Pipeline stage")
    event: str = Field(..., description="Event or action")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Event timestamp")
    evidence: Optional[dict[str, Any]] = Field(None, description="Supporting evidence/metadata")
    decision: Optional[dict[str, Any]] = Field(None, description="Decision information")
