from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.exception_record import ExceptionCategory
from simulator.ground_truth import GroundTruthRecord


DEFAULT_MDR_RATE = Decimal("0.02")
GST_RATE = Decimal("0.18")


def _fee_and_tax(amount: Decimal, mdr_rate: Decimal = DEFAULT_MDR_RATE) -> tuple[Decimal, Decimal]:
    """Compute fee-based MDR and GST with cent-level precision."""
    fee = (amount * mdr_rate).quantize(Decimal("0.01"))
    tax = (fee * GST_RATE).quantize(Decimal("0.01"))
    return fee, tax


def _net_settlement(amount: Decimal, fee: Decimal, tax: Decimal, refund: Decimal = Decimal("0")) -> Decimal:
    """Compute expected net settlement after deductions."""
    return amount - fee - tax - refund


@dataclass
class GatewayRecord:
    settlement_id: str
    transaction_id: str
    order_id: str
    utr: str
    gross_amount: Decimal
    fee: Decimal
    tax: Decimal
    net_amount: Decimal
    settlement_date: datetime
    currency: str
    status: str


@dataclass
class LedgerRecord:
    order_id: str
    customer_id: str
    transaction_amount: Decimal
    refund_amount: Decimal
    order_date: datetime
    payment_status: str
    currency: str
    internal_reference: str


@dataclass
class BankRecord:
    bank_transaction_id: str
    utr: str
    credit_amount: Decimal
    debit_amount: Decimal
    value_date: datetime
    narration: str
    currency: str


def generate_normal(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    utr = f"UTR{logical_id[-12:]}"
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=logical_id,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date,
        narration=f"SETTLEMENT {utr}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=None,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=Decimal("0"),
    )
    
    return gateway, ledger, bank, ground_truth


def generate_delayed_settlement(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    utr = f"UTR{logical_id[-12:]}"
    delay_days = 5
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date + timedelta(days=delay_days),
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=logical_id,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date + timedelta(days=delay_days),
        narration=f"SETTLEMENT {utr}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.DELAYED_SETTLEMENT,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date + timedelta(days=delay_days),
        financial_exposure=Decimal("0"),
    )
    
    return gateway, ledger, bank, ground_truth


def generate_fee_mismatch(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    utr = f"UTR{logical_id[-12:]}"
    expected_fee, expected_tax = _fee_and_tax(amount)
    observed_fee = (amount * Decimal("0.03")).quantize(Decimal("0.01"))
    observed_tax = (observed_fee * GST_RATE).quantize(Decimal("0.01"))
    fee_discrepancy = (observed_fee - expected_fee).quantize(Decimal("0.01"))
    tax_discrepancy = (observed_tax - expected_tax).quantize(Decimal("0.01"))
    net_amount = _net_settlement(amount, observed_fee, observed_tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=observed_fee,
        tax=observed_tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=logical_id,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date,
        narration=f"SETTLEMENT {utr}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.FEE_MISMATCH,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=(abs(fee_discrepancy) + abs(tax_discrepancy)).quantize(Decimal("0.01")),
    )
    
    return gateway, ledger, bank, ground_truth


def generate_partial_refund(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    utr = f"UTR{logical_id[-12:]}"
    refund_amount = amount * Decimal("0.3")
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax, refund_amount)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=refund_amount,
        order_date=date,
        payment_status="PARTIALLY_REFUNDED",
        currency=currency,
        internal_reference=logical_id,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date,
        narration=f"SETTLEMENT {utr}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.PARTIAL_REFUND,
        true_amount=amount,
        true_refund=refund_amount,
        true_settlement_date=date,
        financial_exposure=Decimal("0"),
    )
    
    return gateway, ledger, bank, ground_truth


def generate_duplicate(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    utr = f"UTR{logical_id[-12:]}"
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=logical_id,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date,
        narration=f"SETTLEMENT {utr}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=False,
        true_exception=ExceptionCategory.DUPLICATE_ENTRY,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=amount,
    )
    
    return gateway, ledger, bank, ground_truth


def generate_rounding(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    utr = f"UTR{logical_id[-12:]}"
    rounding_diff = Decimal("0.01")
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax, rounding_diff)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=logical_id,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date,
        narration=f"SETTLEMENT {utr}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.CURRENCY_ROUNDING,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=rounding_diff,
    )
    
    return gateway, ledger, bank, ground_truth


def generate_wrong_reference(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    """Corrupted references across sources (e.g. typos, altered characters)."""
    utr = f"UTR{logical_id[-12:]}"
    corrupted_order_id = f"{ledger_id}_ERR"
    corrupted_utr = f"{utr}_ERR"
    wrong_ref = f"{logical_id}_ERR"
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=corrupted_order_id,
        utr=utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=wrong_ref,
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=corrupted_utr,
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date + timedelta(days=1),
        narration=f"SETTLEMENT {ledger_id}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.WRONG_REFERENCE,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=Decimal("0"),
    )
    
    return gateway, ledger, bank, ground_truth


def generate_ambiguous(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    """Ambiguous candidate matching with altered keys and close amounts/dates."""
    amb_order_id = f"AMB_{ledger_id[-6:]}"
    amb_utr = f"AMB_{logical_id[-8:]}"
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=amb_order_id,
        utr=amb_utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date,
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=f"REF_{amb_order_id}",
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=f"BK_{amb_utr}",
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date,
        narration=f"SETTLEMENT BATCH {amount}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.AMBIGUOUS_MATCH,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=Decimal("0"),
    )
    
    return gateway, ledger, bank, ground_truth


def generate_unexplained(
    logical_id: str,
    gateway_id: str,
    ledger_id: str,
    bank_id: str,
    amount: Decimal,
    date: datetime,
    currency: str,
) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
    """Corrupted order ID and cross-source mismatch requiring ML resolution."""
    alt_order_id = f"GW_{ledger_id[-6:]}"
    alt_utr = f"GW_UTR_{logical_id[-6:]}"
    fee, tax = _fee_and_tax(amount)
    net_amount = _net_settlement(amount, fee, tax)
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=alt_order_id,
        utr=alt_utr,
        gross_amount=amount,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        settlement_date=date + timedelta(days=1),
        currency=currency,
        status="SETTLED",
    )
    
    ledger = LedgerRecord(
        order_id=ledger_id,
        customer_id=f"CUST{logical_id[-6:]}",
        transaction_amount=amount,
        refund_amount=Decimal("0"),
        order_date=date,
        payment_status="PAID",
        currency=currency,
        internal_reference=f"REF_{logical_id[-6:]}",
    )
    
    bank = BankRecord(
        bank_transaction_id=bank_id,
        utr=f"BK_UTR_{logical_id[-6:]}",
        credit_amount=net_amount,
        debit_amount=Decimal("0"),
        value_date=date + timedelta(days=1),
        narration=f"PAYMENT FOR {ledger_id}",
        currency=currency,
    )
    
    ground_truth = GroundTruthRecord(
        logical_transaction_id=logical_id,
        gateway_record_id=gateway_id,
        ledger_record_id=ledger_id,
        bank_record_id=bank_id,
        true_match=True,
        true_exception=ExceptionCategory.UNEXPLAINED,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=Decimal("0"),
    )
    
    return gateway, ledger, bank, ground_truth
