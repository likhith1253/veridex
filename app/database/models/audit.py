from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    decision: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_audit_events_run_id", "run_id"),
        Index("ix_audit_events_transaction_id", "transaction_id"),
        Index("ix_audit_events_timestamp", "timestamp"),
    )
