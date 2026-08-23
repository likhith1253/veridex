from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TransactionSource(str, Enum):
    GATEWAY = "gateway"
    LEDGER = "ledger"
    BANK = "bank"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    EXCEPTION = "exception"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    domain_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[TransactionSource] = mapped_column(String(50), nullable=False)
    reference_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    narration: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(19, 4), nullable=True)
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(19, 4), nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(String(50), nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "domain_transaction_id", name="uq_source_domain_id"),
        Index("ix_source_domain_id", "source", "domain_transaction_id"),
        Index("ix_reference_number", "reference_number"),
        Index("ix_order_id", "order_id"),
        Index("ix_timestamp", "timestamp"),
    )
