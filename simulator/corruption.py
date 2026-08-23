import random
import string
from datetime import datetime, timedelta
from decimal import Decimal

from simulator.scenarios import GatewayRecord, LedgerRecord, BankRecord


def corrupt_reference(reference: str) -> str:
    """Introduce slight character changes to a reference string."""
    if len(reference) < 2:
        return reference
    
    chars = list(reference)
    pos = random.randint(0, len(chars) - 1)
    
    if chars[pos].isdigit():
        chars[pos] = str(random.randint(0, 9))
    elif chars[pos].isalpha():
        chars[pos] = random.choice(string.ascii_uppercase)
    
    return "".join(chars)


def corrupt_amount(amount: Decimal, max_change: Decimal = Decimal("10")) -> Decimal:
    """Introduce small value changes to an amount."""
    change = Decimal(str(random.uniform(-float(max_change), float(max_change))))
    new_amount = amount + change
    return max(new_amount, Decimal("0"))


def corrupt_timestamp(date: datetime, max_days: int = 3) -> datetime:
    """Shift date by a small number of days."""
    days_shift = random.randint(-max_days, max_days)
    return date + timedelta(days=days_shift)


def duplicate_record(record: GatewayRecord | LedgerRecord | BankRecord, new_id: str) -> GatewayRecord | LedgerRecord | BankRecord:
    """Create a duplicate record with a new ID."""
    if isinstance(record, GatewayRecord):
        return GatewayRecord(
            settlement_id=new_id,
            transaction_id=record.transaction_id,
            order_id=record.order_id,
            utr=record.utr,
            gross_amount=record.gross_amount,
            fee=record.fee,
            tax=record.tax,
            net_amount=record.net_amount,
            settlement_date=record.settlement_date,
            currency=record.currency,
            status=record.status,
        )
    elif isinstance(record, LedgerRecord):
        return LedgerRecord(
            order_id=new_id,
            customer_id=record.customer_id,
            transaction_amount=record.transaction_amount,
            refund_amount=record.refund_amount,
            order_date=record.order_date,
            payment_status=record.payment_status,
            currency=record.currency,
            internal_reference=record.internal_reference,
        )
    elif isinstance(record, BankRecord):
        return BankRecord(
            bank_transaction_id=new_id,
            utr=record.utr,
            credit_amount=record.credit_amount,
            debit_amount=record.debit_amount,
            value_date=record.value_date,
            narration=record.narration,
            currency=record.currency,
        )
    return record
