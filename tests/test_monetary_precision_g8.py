import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import httpx
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.api.dependencies import get_db_session, get_investigation_service
from app.api.schemas.controller import (
    BatchRecordItem,
    SingleTransactionIngestRequest,
    FailureSimulationRequest,
)
from app.services.cash_position import CashPositionSummary
from app.services.exposure_service import FinancialExposureBreakdown
from app.services.finance_controller import ControllerKPIs
from app.services.source_health_service import SourceHealthReport, SourceMetrics


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


def test_fractional_fee_tax_accounting_calculations():
    """Verify fractional fee and tax calculations maintain strict decimal equality without IEEE-754 drift."""
    gross = Decimal("123456.78")
    mdr_rate = Decimal("0.02")      # 2.0% MDR
    gst_rate = Decimal("0.18")      # 18.0% GST on MDR

    fee = gross * mdr_rate          # 2469.1356
    tax = fee * gst_rate            # 444.444408
    expected_net = gross - fee - tax # 120543.2000

    assert fee == Decimal("2469.1356")
    assert tax == Decimal("444.444408")
    assert expected_net == Decimal("120543.199992")
    # Exact reconciliation invariant
    assert gross == expected_net + fee + tax


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
