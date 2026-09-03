from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.database.models.finance_action import ActionLifecycleState, FinanceActionType


class ActionRecommendRequest(BaseModel):
    entity_type: str = Field(..., description="Target entity type: exception, settlement, transaction")
    entity_id: str = Field(..., description="Target entity identifier")
    action_type: FinanceActionType = Field(..., description="Action to recommend")
    amount: Decimal = Field(default=Decimal("0.00"), description="Financial amount involved (must be bounded)")
    currency: str = Field(default="INR", description="Currency ISO code")
    recommended_by: str = Field(default="ai_investigation", description="Actor or component recommending the action")
    recommendation_reason: str = Field(..., description="Justification and root cause reasoning")
    evidence: Optional[dict[str, Any]] = Field(default=None, description="Supporting evidence dictionary")
    run_id: Optional[str] = Field(default=None, description="Associated reconciliation run ID")


class ActionDecisionRequest(BaseModel):
    actor: str = Field(..., description="Identity of the authorizing human actor")
    reason: str = Field(..., description="Explicit human rationale for decision")


class ActionExecuteRequest(BaseModel):
    actor: str = Field(..., description="Identity of the operator triggering execution")


class FinanceActionResponse(BaseModel):
    id: str
    run_id: str
    entity_type: str
    entity_id: str
    action_type: str
    state: str
    amount: Decimal
    currency: str
    recommended_by: str
    recommendation_reason: str
    evidence: Optional[dict[str, Any]] = None
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    decision_reason: Optional[str] = None
    execution_result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
