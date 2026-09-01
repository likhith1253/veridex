"""
Pydantic Schemas for Razorpay Integration in Project Sentinel.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class RazorpaySettlementState(str, Enum):
    """Lifecycle state of a Razorpay settlement."""
    RAZORPAY_PROCESSED = "RAZORPAY_PROCESSED"
    BANK_CREDIT_PENDING = "BANK_CREDIT_PENDING"
    BANK_CREDIT_CONFIRMED = "BANK_CREDIT_CONFIRMED"
    RECONCILED = "RECONCILED"
    EXCEPTION = "EXCEPTION"


class RazorpayStatusResponse(BaseModel):
    """Safe status metadata for Razorpay integration."""
    configured: bool
    mode: str
    key_id_prefix: str
    webhook_configured: bool
    api_reachable: bool = False
    last_sync_at: Optional[datetime] = None
    last_webhook_at: Optional[datetime] = None
    last_error: Optional[str] = None


class RazorpaySyncRequest(BaseModel):
    """Parameters for manual or scheduled sync."""
    limit: int = Field(default=50, ge=1, le=100)
    skip: int = Field(default=0, ge=0)
    from_timestamp: Optional[int] = None
    to_timestamp: Optional[int] = None
    auto_reconcile: bool = Field(default=True, description="Whether to trigger incremental 3-way reconciliation on synced items")
    use_fallback_if_unconfigured: bool = Field(default=True, description="Fall back to synthetic simulation if live credentials missing")


class RazorpaySyncResponse(BaseModel):
    """Result of a Razorpay data synchronization run."""
    source: str  # "razorpay_test", "razorpay_live", "synthetic_fallback"
    mode: str
    entity_type: str  # "payments", "settlements", "orders"
    records_fetched: int
    records_normalized: int
    records_rejected: int
    run_id: str
    duration_ms: float
    reconciliation_summary: Optional[dict[str, Any]] = None
    warning: Optional[str] = None


class RazorpayWebhookResponse(BaseModel):
    """Response returned upon processing a Razorpay webhook."""
    event_id: str
    event_type: str
    status: str  # "PROCESSED", "DUPLICATE_IGNORED", "FAILED", or reconciliation status (e.g. "MATCHED_DETERMINISTIC")
    transaction_id: Optional[str] = None
    reconciliation_status: Optional[str] = None
    action: Optional[str] = None
    match_id: Optional[str] = None
    matched_transaction_id: Optional[str] = None
    processing_time_ms: float
    message: Optional[str] = None

