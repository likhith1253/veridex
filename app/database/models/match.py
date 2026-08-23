from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class MatchType(str, Enum):
    EXACT = "exact"
    PROBABLE = "probable"
    PARTIAL = "partial"
    NONE = "none"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    match_type: Mapped[MatchType] = mapped_column(String(50), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(5000), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_matches_run_id", "run_id"),)

    # Relationships
    match_transactions: Mapped[list["MatchTransaction"]] = relationship(
        "MatchTransaction", back_populates="match", cascade="all, delete-orphan"
    )


class MatchTransaction(Base):
    __tablename__ = "match_transactions"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id", ondelete="RESTRICT"), primary_key=True
    )
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), primary_key=True
    )

    __table_args__ = (
        Index("ix_match_transactions_match_id", "match_id"),
        Index("ix_match_transactions_transaction_id", "transaction_id"),
    )

    # Relationships
    match: Mapped["Match"] = relationship("Match", back_populates="match_transactions")
