from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    exception_id: Mapped[str] = mapped_column(
        ForeignKey("exceptions.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    root_cause: Mapped[str] = mapped_column(String(1000), nullable=False)
    classification: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    financial_exposure: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    expected_cost: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(100), nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_invoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    historical_cases_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_raw_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_investigations_investigation_id", "investigation_id"),
        Index("ix_investigations_exception_id", "exception_id"),
        Index("ix_investigations_run_id", "run_id"),
        Index("ix_investigations_classification", "classification"),
        Index("ix_investigations_status", "status"),
    )

    # Relationships
    exception: Mapped["Exception"] = relationship("Exception", foreign_keys=[exception_id])
    run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", foreign_keys=[run_id])
