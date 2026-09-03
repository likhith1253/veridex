"""
Pydantic Schemas for Razorpay Settlement Intelligence API.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class SettlementVarianceType(str, Enum):
    """Classification of settlement variance."""
    NO_VARIANCE = "NO_VARIANCE"
    FEE_VARIANCE = "FEE_VARIANCE"
    TAX_VARIANCE = "TAX_VARIANCE"
    AMOUNT_VARIANCE = "AMOUNT_VARIANCE"
    MISSING_BANK_CREDIT = "MISSING_BANK_CREDIT"
    UNEXPECTED_BANK_CREDIT = "UNEXPECTED_BANK_CREDIT"
    UNKNOWN_VARIANCE = "UNKNOWN_VARIANCE"


class SettlementStatusFilter(str, Enum):
    """Filter options for settlement status."""
    ALL = "ALL"
    RAZORPAY_PROCESSED = "RAZORPAY_PROCESSED"
    BANK_CREDIT_PENDING = "BANK_CREDIT_PENDING"
    BANK_CREDIT_CONFIRMED = "BANK_CREDIT_CONFIRMED"
    EXCEPTION = "EXCEPTION"


class SettlementFinancialBreakdownResponse(BaseModel):
    """Financial decomposition of a settlement."""
    settlement_id: str
    gross_amount: str
    fee_amount: str
    tax_amount: str
    adjustment_amount: str
    expected_net_amount: str
    bank_received_amount: str
    variance: str
    currency: str
    variance_type: SettlementVarianceType


class SettlementTransactionLinkageResponse(BaseModel):
    """Which transactions belong to a settlement."""
    settlement_id: str
    linked_transaction_count: int
    matched_transaction_count: int
    unmatched_transaction_count: int
    linked_transaction_ids: list[str]
    matched_transaction_ids: list[str]
    unmatched_transaction_ids: list[str]


class SettlementBankReconciliationResponse(BaseModel):
    """Bank reconciliation state for a settlement."""
    settlement_id: str
    settlement_status: str
    utr: Optional[str]
    bank_matched: bool
    bank_transaction_id: Optional[str]
    bank_amount: Optional[str]
    bank_date: Optional[str]
    bank_match_confidence: Optional[str]


class SettlementExceptionDossierResponse(BaseModel):
    """Structured investigation object for settlement exceptions."""
    settlement_id: str
    settlement_status: str
    settlement_period: Optional[str]
    gross_amount: str
    fee_amount: str
    tax_amount: str
    expected_net_amount: str
    bank_received_amount: str
    variance: str
    linked_transaction_count: int
    matched_transaction_count: int
    unmatched_transaction_count: int
    exception_type: str
    confidence: str
    evidence: dict[str, Any]
    root_cause_candidates: list[str]
    recommended_next_action: str


class SettlementExplanationResponse(BaseModel):
    """Complete explanation of a settlement for finance operators."""
    # Summary
    settlement_id: str
    settlement_status: str
    expected_amount: str
    bank_amount: Optional[str]
    variance: str
    
    # Composition
    gross_amount: str
    fee_amount: str
    tax_amount: str
    adjustment_amount: str
    net_amount: str
    
    # Transaction evidence
    linked_transaction_count: int
    matched_transaction_count: int
    unmatched_transaction_count: int
    transaction_ids: list[str]
    
    # Bank evidence
    utr: Optional[str]
    bank_matched: bool
    bank_transaction_id: Optional[str]
    bank_date: Optional[str]
    
    # Root cause and action
    variance_type: SettlementVarianceType
    root_cause: Optional[str]
    recommended_action: Optional[str]
    
    # Evidence references
    evidence: dict[str, Any]


class SettlementDashboardSummary(BaseModel):
    """Summary metrics for settlement dashboard."""
    total_settlements: int = Field(default=0)
    processed_settlements: int = Field(default=0)
    bank_confirmed_settlements: int = Field(default=0)
    pending_bank_credit: int = Field(default=0)
    matched_settlements: int = Field(default=0)
    exception_settlements: int = Field(default=0)
    
    # Financial aggregates
    total_gross: str = Field(default="0.00")
    total_fees: str = Field(default="0.00")
    total_taxes: str = Field(default="0.00")
    total_expected_net: str = Field(default="0.00")
    total_bank_received: str = Field(default="0.00")
    total_variance: str = Field(default="0.00")
    
    currency: str = Field(default="INR")


class SettlementListFilter(BaseModel):
    """Filter parameters for settlement list."""
    from_date: Optional[datetime] = Field(None, description="Start date for settlement period")
    to_date: Optional[datetime] = Field(None, description="End date for settlement period")
    status_filter: SettlementStatusFilter = Field(default=SettlementStatusFilter.ALL, description="Filter by settlement status")
    exception_type: Optional[str] = Field(None, description="Filter by exception type")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of settlements to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class SettlementListItem(BaseModel):
    """Compact representation of a settlement for list views."""
    settlement_id: str
    settlement_date: str
    status: str
    gross_amount: str
    expected_net_amount: str
    bank_received_amount: Optional[str]
    variance: str
    variance_type: SettlementVarianceType
    transaction_count: int
    has_exception: bool


class SettlementListResponse(BaseModel):
    """Response for settlement list endpoint."""
    settlements: list[SettlementListItem]
    total_count: int
    filter_applied: dict[str, Any]
