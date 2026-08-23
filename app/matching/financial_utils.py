from decimal import Decimal
from typing import Optional

from app.models.transaction import Transaction


def calculate_expected_bank_amount(gateway_txn: Transaction) -> Optional[Decimal]:
    """Calculate expected bank amount accounting for fees, tax, and refunds.
    
    Args:
        gateway_txn: Gateway transaction to calculate expected bank amount for.
        
    Returns:
        Expected bank amount after subtracting fees, tax, and refunds, or None if result is non-positive.
    """
    expected = gateway_txn.amount

    # Subtract fee
    if gateway_txn.fee:
        expected -= gateway_txn.fee

    # Subtract tax
    if gateway_txn.tax:
        expected -= gateway_txn.tax

    # Handle refunds from metadata
    if gateway_txn.metadata and "refund_amount" in gateway_txn.metadata:
        refund_amount = Decimal(str(gateway_txn.metadata["refund_amount"]))
        expected -= refund_amount

    return expected if expected > 0 else None
