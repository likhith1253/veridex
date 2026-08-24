import uuid
from typing import Optional
from pydantic import BaseModel, Field

from app.models.reconciliation_summary import ReconciliationSummary
from app.models.transaction import Transaction, TransactionSource


class ReconciliationRunRequest(BaseModel):
    """Request payload for triggering a reconciliation run."""

    run_id: Optional[str] = Field(
        None,
        description="Optional unique identifier for the reconciliation run; generated if omitted",
    )
    gateway: list[Transaction] = Field(
        default_factory=list,
        description="List of transactions from the payment gateway feed",
    )
    ledger: list[Transaction] = Field(
        default_factory=list,
        description="List of transactions from the internal ledger feed",
    )
    bank: list[Transaction] = Field(
        default_factory=list,
        description="List of transactions from the bank statement feed",
    )

    def to_transactions_by_source(self) -> dict[TransactionSource, list[Transaction]]:
        """Convert the request feeds into a dictionary grouped by TransactionSource."""
        gateway_txns = []
        for txn in self.gateway:
            if txn.source != TransactionSource.GATEWAY:
                txn = txn.model_copy(update={"source": TransactionSource.GATEWAY})
            gateway_txns.append(txn)

        ledger_txns = []
        for txn in self.ledger:
            if txn.source != TransactionSource.LEDGER:
                txn = txn.model_copy(update={"source": TransactionSource.LEDGER})
            ledger_txns.append(txn)

        bank_txns = []
        for txn in self.bank:
            if txn.source != TransactionSource.BANK:
                txn = txn.model_copy(update={"source": TransactionSource.BANK})
            bank_txns.append(txn)

        return {
            TransactionSource.GATEWAY: gateway_txns,
            TransactionSource.LEDGER: ledger_txns,
            TransactionSource.BANK: bank_txns,
        }
