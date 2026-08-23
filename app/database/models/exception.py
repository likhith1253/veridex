from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ExceptionCategory(str, Enum):
    MISSING_RECORD = "missing_record"
    AMOUNT_MISMATCH = "amount_mismatch"
    TIMING_MISMATCH = "timing_mismatch"
    DUPLICATE_RECORD = "duplicate_record"
    DATA_QUALITY = "data_quality"
    UNKNOWN = "unknown"


class Exception(Base):
    __tablename__ = "exceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    exception_category: Mapped[ExceptionCategory] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(nullable=False)
    financial_exposure: Mapped[Decimal] = mapped_column(nullable=False)
    expected_cost: Mapped[Decimal] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(String(5000), nullable=False)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_exceptions_run_id", "run_id"),
        Index("ix_exceptions_status", "status"),
    )

    # Relationships
    exception_transactions: Mapped[list["ExceptionTransaction"]] = relationship(
        "ExceptionTransaction", back_populates="exception", cascade="all, delete-orphan"
    )


class ExceptionTransaction(Base):
    __tablename__ = "exception_transactions"

    exception_id: Mapped[str] = mapped_column(
        ForeignKey("exceptions.id", ondelete="RESTRICT"), primary_key=True
    )
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), primary_key=True
    )

    __table_args__ = (
        Index("ix_exception_transactions_exception_id", "exception_id"),
        Index("ix_exception_transactions_transaction_id", "transaction_id"),
    )

    # Relationships
    exception: Mapped["Exception"] = relationship(
        "Exception", back_populates="exception_transactions"
    )
