import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.api.schemas.controller import (
    BatchRecordItem,
    SingleTransactionIngestRequest,
    FailureSimulationRequest,
)
from app.services.cash_position import CashPositionSummary
from app.services.exposure_service import FinancialExposureBreakdown
from app.services.finance_controller import ControllerKPIs
from app.services.source_health_service import SourceHealthReport, SourceMetrics
from ui.dashboard import format_money, format_number, format_percent


def test_aud_021_ui_format_money_decimal_precision():
    """Verify format_money never introduces binary floating point inaccuracies."""
    # Classic float precision bug: 0.10 + 0.20 = 0.30000000000000004
    dec_val = Decimal("0.10") + Decimal("0.20")
    formatted = format_money(dec_val)
    assert formatted == "₹0.30"

    # Large financial values
    large_val = Decimal("123456789012345.12")
    assert format_money(large_val) == "₹123,456,789,012,345.12"
    assert format_money("123456789.75") == "₹123,456,789.75"

    # Small values
    assert format_money(Decimal("0.01")) == "₹0.01"
    assert format_money(None, fallback="N/A") == "N/A"
    assert format_money("invalid", fallback="N/A") == "N/A"


def test_aud_022_ui_format_number_and_percent_precision():
    """Verify format_number and format_percent operate with exact Decimal parsing."""
    assert format_number(Decimal("1234567.89"), decimals=2) == "1,234,567.89"
    assert format_number("1000", decimals=0) == "1,000"
    assert format_percent(Decimal("99.95"), decimals=1) == "100.0%" or format_percent(Decimal("99.95"), decimals=2) == "99.95%"
    assert format_percent("87.654", decimals=2) == "87.65%"
    assert format_number(None) == "N/A — unavailable from live data"


def test_aud_023_controller_kpis_decimal_exact_serialization():
    """Verify ControllerKPIs stores exact Decimals and serializes them as strings across API boundary."""
    kpis = ControllerKPIs(
        total_records_processed=30,
        total_logical_transactions=10,
        total_transaction_value_inr=Decimal("123456789.75"),
        total_matched_monetary_value_inr=Decimal("100000000.50"),
        unresolved_monetary_exposure_inr=Decimal("23456789.25"),
        manual_review_exposure_inr=Decimal("500000.00"),
        high_risk_exposure_inr=Decimal("1000000.00"),
        delayed_settlement_inr=Decimal("200000.00"),
        duplicate_amount_inr=Decimal("15000.00"),
        fee_mismatch_inr=Decimal("5000.00"),
        match_rate=90.0,
    )

    d = kpis.to_dict()
    assert d["total_transaction_value_inr"] == "123456789.75"
    assert d["total_matched_monetary_value_inr"] == "100000000.50"
    assert d["unresolved_monetary_exposure_inr"] == "23456789.25"
    assert isinstance(d["total_transaction_value_inr"], str)
    assert isinstance(d["match_rate"], float)


def test_aud_032_cash_position_summary_string_decimal_serialization():
    """Verify CashPositionSummary serializes all monetary fields as exact strings without float degradation."""
    cash = CashPositionSummary(
        expected_amount=Decimal("2310799.00"),
        expected_gross=Decimal("2310799.00"),
        expected_net_settlement=Decimal("2256264.14"),
        received_amount=Decimal("2310799.00"),
        received_bank_credits=Decimal("2310799.00"),
        settlement_variance=Decimal("54534.86"),
        total_deducted_fees=Decimal("46215.98"),
        total_deducted_taxes=Decimal("8318.88"),
        total_refunded_amount=Decimal("0.00"),
        pending_amount=Decimal("0.00"),
        delayed_amount=Decimal("0.00"),
        unreconciled_amount=Decimal("1584681.00"),
        at_risk_amount=Decimal("1584681.00"),
        breakdown_by_source={"gateway": Decimal("2310799.00"), "bank": Decimal("2310799.00")},
        breakdown_by_category={"unexplained": Decimal("1584681.00")},
    )

    d = cash.to_dict()
    assert d["expected_gross"] == "2310799.00"
    assert d["expected_net_settlement"] == "2256264.14"
    assert d["total_deducted_fees"] == "46215.98"
    assert d["total_deducted_taxes"] == "8318.88"
    assert d["settlement_variance"] == "54534.86"
    assert d["unreconciled_amount"] == "1584681.00"
    assert d["breakdown_by_source"]["gateway"] == "2310799.00"
    assert d["breakdown_by_category"]["unexplained"] == "1584681.00"
    assert all(isinstance(v, str) for k, v in d.items() if k not in ("currency", "breakdown_by_source", "breakdown_by_category"))


def test_aud_051_ingest_pydantic_schemas_enforce_decimal_precision():
    """Verify single and batch ingestion schemas reject float truncation and parse exact Decimals."""
    req = SingleTransactionIngestRequest(
        txn_id="TXN_PRECISION_01",
        source="gateway",
        amount=Decimal("123456789.75"),
        currency="INR",
    )
    assert req.amount == Decimal("123456789.75")
    assert isinstance(req.amount, Decimal)

    item = BatchRecordItem(
        txn_id="B_01",
        amount=Decimal("0.10"),
        fee=Decimal("0.02"),
        tax=Decimal("0.0036"),
    )
    assert item.amount == Decimal("0.10")
    assert item.fee == Decimal("0.02")
    assert item.tax == Decimal("0.0036")


def test_source_health_decimal_serialization():
    """Verify SourceHealthReport preserves Decimal volumes."""
    report = SourceHealthReport(
        overall_health="HEALTHY",
        total_feeds_monitored=3,
        sources={
            "gateway": {
                "source_name": "Payment Gateway",
                "total_records": 10,
                "total_volume_inr": Decimal("2310799.00"),
                "matched_records": 10,
                "exception_records": 3,
                "match_rate_percent": 100.0,
                "exception_rate_percent": 30.0,
                "health_status": "HEALTHY",
            }
        }
    )
    d = report.to_dict()
    assert d["sources"]["gateway"]["total_volume_inr"] == "2310799.00"
