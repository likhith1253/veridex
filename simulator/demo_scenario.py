"""
Deterministic Demo Scenario Generator for Investigation Workflow.

Produces a reproducible scenario with:
- Matched transactions (deterministic)
- ML-recovered transactions  
- At least one meaningful exception with financial exposure
- Intelligence classification
- Human-review case
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from simulator.scenarios import (
    generate_normal,
    generate_fee_mismatch,
    generate_delayed_settlement,
    generate_ambiguous,
    generate_duplicate,
)


def generate_investigation_demo_scenario() -> dict[str, Any]:
    """
    Generate a deterministic demo scenario for the investigation workflow.
    
    Returns:
        Dictionary with gateway_records, ledger_records, bank_records, and expected_results
    """
    base_date = datetime.now(timezone.utc)
    currency = "INR"
    
    gateway_records = []
    ledger_records = []
    bank_records = []
    
    # 1. Normal matched transactions (deterministic matches)
    for i in range(5):
        logical_id = f"TXN_NORMAL_{i:03d}"
        gateway_id = f"GW_{logical_id}"
        ledger_id = f"ORD_{logical_id}"
        bank_id = f"BK_{logical_id}"
        amount = Decimal("10000.00") + Decimal(str(i * 1000))
        
        gw, ld, bk, _ = generate_normal(
            logical_id, gateway_id, ledger_id, bank_id, amount, base_date, currency
        )
        gateway_records.append(gw)
        ledger_records.append(ld)
        bank_records.append(bk)
    
    # 2. Fee mismatch exception (meaningful exception with financial exposure)
    logical_id = "TXN_FEE_MISMATCH_001"
    gateway_id = f"GW_{logical_id}"
    ledger_id = f"ORD_{logical_id}"
    bank_id = f"BK_{logical_id}"
    amount = Decimal("50000.00")
    
    gw_fee, ld_fee, bk_fee, _ = generate_fee_mismatch(
        logical_id, gateway_id, ledger_id, bank_id, amount, base_date + timedelta(days=1), currency
    )
    gateway_records.append(gw_fee)
    ledger_records.append(ld_fee)
    bank_records.append(bk_fee)
    
    # 3. Delayed settlement exception (ML-recovered, human-review case)
    logical_id = "TXN_DELAYED_001"
    gateway_id = f"GW_{logical_id}"
    ledger_id = f"ORD_{logical_id}"
    bank_id = f"BK_{logical_id}"
    amount = Decimal("150000.00")  # High value for human review
    
    gw_delayed, ld_delayed, bk_delayed, _ = generate_delayed_settlement(
        logical_id, gateway_id, ledger_id, bank_id, amount, base_date + timedelta(days=2), currency
    )
    gateway_records.append(gw_delayed)
    ledger_records.append(ld_delayed)
    bank_records.append(bk_delayed)
    
    # 4. Ambiguous match exception (requires investigation)
    logical_id = "TXN_AMBIGUOUS_001"
    gateway_id = f"GW_{logical_id}"
    ledger_id = f"ORD_{logical_id}"
    bank_id = f"BK_{logical_id}"
    amount = Decimal("75000.00")
    
    gw_amb, ld_amb, bk_amb, _ = generate_ambiguous(
        logical_id, gateway_id, ledger_id, bank_id, amount, base_date + timedelta(days=3), currency
    )
    gateway_records.append(gw_amb)
    ledger_records.append(ld_amb)
    bank_records.append(bk_amb)
    
    # 5. Duplicate entry exception (high risk)
    logical_id = "TXN_DUPLICATE_001"
    gateway_id = f"GW_{logical_id}"
    ledger_id = f"ORD_{logical_id}"
    bank_id = f"BK_{logical_id}"
    amount = Decimal("25000.00")
    
    gw_dup, ld_dup, bk_dup, _ = generate_duplicate(
        logical_id, gateway_id, ledger_id, bank_id, amount, base_date + timedelta(days=4), currency
    )
    gateway_records.append(gw_dup)
    ledger_records.append(ld_dup)
    bank_records.append(bk_dup)
    
    # Expected results for validation
    expected_results = {
        "total_transactions": 9,
        "expected_matches": 5,  # The normal ones
        "expected_exceptions": 4,  # fee_mismatch, delayed_settlement, ambiguous, duplicate
        "expected_ml_recovered": 2,  # delayed_settlement, ambiguous
        "expected_human_review": 2,  # delayed_settlement (high value), duplicate (high risk)
        "highest_exposure_exception": "TXN_FEE_MISMATCH_001",
        "expected_exposure_amount": "500.00",  # fee discrepancy from 50000 * 0.01
    }
    
    return {
        "gateway_records": gateway_records,
        "ledger_records": ledger_records,
        "bank_records": bank_records,
        "expected_results": expected_results,
        "scenario_description": "Investigation workflow demo with matched transactions, fee mismatch, delayed settlement, ambiguous match, and duplicate entry exceptions",
    }


def serialize_for_api(record: Any) -> dict[str, Any]:
    """Convert simulator records to API-compatible format."""
    if hasattr(record, "settlement_id"):
        # GatewayRecord
        return {
            "txn_id": record.transaction_id,
            "amount": float(record.gross_amount),
            "currency": record.currency,
            "timestamp": record.settlement_date.isoformat(),
            "order_id": record.order_id,
            "reference_number": record.utr,
            "fee": float(record.fee),
            "tax": float(record.tax),
            "narration": f"Settlement {record.settlement_id}",
        }
    elif hasattr(record, "customer_id"):
        # LedgerRecord
        return {
            "txn_id": record.internal_reference,
            "amount": float(record.transaction_amount),
            "currency": record.currency,
            "timestamp": record.order_date.isoformat(),
            "order_id": record.order_id,
            "reference_number": record.internal_reference,
            "narration": f"Customer {record.customer_id}",
        }
    elif hasattr(record, "bank_transaction_id"):
        # BankRecord
        return {
            "txn_id": record.bank_transaction_id,
            "amount": float(record.credit_amount),
            "currency": record.currency,
            "timestamp": record.value_date.isoformat(),
            "reference_number": record.utr,
            "narration": record.narration,
        }
    return {}
