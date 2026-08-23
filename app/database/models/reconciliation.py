from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ReconciliationRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[ReconciliationRunStatus] = mapped_column(String(50), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    gateway_count: Mapped[int] = mapped_column(nullable=False)
    ledger_count: Mapped[int] = mapped_column(nullable=False)
    bank_count: Mapped[int] = mapped_column(nullable=False)
    match_count: Mapped[int] = mapped_column(nullable=False)
    exception_count: Mapped[int] = mapped_column(nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    # Relationships
    reconciliation_items: Mapped[list["ReconciliationItem"]] = relationship(
        "ReconciliationItem", back_populates="run", cascade="all, delete-orphan"
    )


class ReconciliationItem(Base):
    __tablename__ = "reconciliation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )
    processing_status: Mapped[str] = mapped_column(String(255), nullable=False)
    resulting_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_reconciliation_items_run_id", "run_id"),
        Index("ix_reconciliation_items_transaction_id", "transaction_id"),
    )

    # Relationships
    run: Mapped["ReconciliationRun"] = relationship(
        "ReconciliationRun", back_populates="reconciliation_items"
    )
