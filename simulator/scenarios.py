from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.exception_record import ExceptionCategory
from simulator.ground_truth import GroundTruthRecord


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
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount,
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
        credit_amount=amount,
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
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount,
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
        credit_amount=amount,
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
    fee_discrepancy = amount * Decimal("0.01")
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.03"),
        tax=amount * Decimal("0.18"),
        net_amount=amount - fee_discrepancy,
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
        credit_amount=amount - fee_discrepancy,
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
        financial_exposure=fee_discrepancy,
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
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount - refund_amount,
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
        credit_amount=amount - refund_amount,
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
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount,
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
        credit_amount=amount,
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
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount - rounding_diff,
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
        credit_amount=amount - rounding_diff,
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
    utr = f"UTR{logical_id[-12:]}"
    wrong_ref = logical_id[:-2] + "XX"
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount,
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
        utr=utr,
        credit_amount=amount,
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
    utr = f"UTR{logical_id[-12:]}"
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount,
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
        credit_amount=amount,
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
    utr = f"UTR{logical_id[-12:]}"
    
    gateway = GatewayRecord(
        settlement_id=gateway_id,
        transaction_id=logical_id,
        order_id=ledger_id,
        utr=utr,
        gross_amount=amount,
        fee=amount * Decimal("0.02"),
        tax=amount * Decimal("0.18"),
        net_amount=amount + Decimal("10"),
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
        credit_amount=amount + Decimal("10"),
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
        true_exception=ExceptionCategory.UNEXPLAINED,
        true_amount=amount,
        true_refund=None,
        true_settlement_date=date,
        financial_exposure=Decimal("10"),
    )
    
    return gateway, ledger, bank, ground_truth
