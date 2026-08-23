from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransactionSource(str, Enum):
    GATEWAY = "gateway"
    LEDGER = "ledger"
    BANK = "bank"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Transaction(BaseModel):
    txn_id: str = Field(..., description="Unique transaction identifier")
    source: TransactionSource = Field(..., description="Data source (gateway/ledger/bank)")
    reference_number: Optional[str] = Field(None, description="External reference number")
    amount: Decimal = Field(..., description="Transaction amount", gt=0)
    currency: str = Field(..., description="Currency code (e.g., USD, EUR)")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    narration: Optional[str] = Field(None, description="Transaction description/narration")
    fee: Optional[Decimal] = Field(None, description="Transaction fee", ge=0)
    tax: Optional[Decimal] = Field(None, description="Tax amount", ge=0)
    status: TransactionStatus = Field(..., description="Transaction status")
    order_id: Optional[str] = Field(None, description="Associated order ID")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
