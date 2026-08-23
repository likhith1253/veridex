from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DecisionAction(str, Enum):
    AUTO_MATCH = "auto_match"
    PROPOSE_MATCH = "propose_match"
    MANUAL_REVIEW = "manual_review"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    REJECT = "reject"


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    match_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("matches.id", ondelete="RESTRICT"), nullable=True
    )
    decision_action: Mapped[DecisionAction] = mapped_column(String(50), nullable=False)
    deterministic_confidence: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    ml_probability: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    candidate_margin: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(String(5000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_decisions_run_id", "run_id"),
        Index("ix_decisions_match_id", "match_id"),
        Index("ix_decisions_decision_action", "decision_action"),
    )
