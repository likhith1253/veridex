from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ActionLifecycleState(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    RECOMMENDED = "RECOMMENDED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class FinanceActionType(str, Enum):
    RECONCILE_MATCH = "RECONCILE_MATCH"
    POST_ADJUSTMENT = "POST_ADJUSTMENT"
    WRITE_OFF = "WRITE_OFF"
    INITIATE_INQUIRY = "INITIATE_INQUIRY"
    FLAG_INVESTIGATION = "FLAG_INVESTIGATION"


class FinanceAction(Base):
    __tablename__ = "finance_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default=ActionLifecycleState.DETECTED.value)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    
    recommended_by: Mapped[str] = mapped_column(String(100), nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    requested_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rejected_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    execution_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_finance_actions_entity_id", "entity_id"),
        Index("ix_finance_actions_state", "state"),
        Index("ix_finance_actions_run_id", "run_id"),
    )
