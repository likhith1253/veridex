from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.transaction import Transaction, TransactionSource


class CandidateGenerator:
    """Generates deterministic candidate matches without ML or embeddings."""

    DATE_WINDOW_DAYS = 3

    def __init__(self, transactions_by_source: dict[TransactionSource, list[Transaction]]):
        """Initialize with transactions grouped by source."""
        self.transactions_by_source = transactions_by_source

    def filter_by_currency(
        self, transaction: Transaction, candidates: list[Transaction]
    ) -> list[Transaction]:
        """Filter candidates to same currency only."""
        return [c for c in candidates if c.currency == transaction.currency]

    def filter_by_date_window(
        self, transaction: Transaction, candidates: list[Transaction]
    ) -> list[Transaction]:
        """Filter candidates within ±3 calendar days."""
        delta = timedelta(days=self.DATE_WINDOW_DAYS)
        min_date = transaction.timestamp - delta
        max_date = transaction.timestamp + delta
        return [c for c in candidates if min_date <= c.timestamp <= max_date]

    def filter_by_amount_range(
        self, transaction: Transaction, candidates: list[Transaction]
    ) -> list[Transaction]:
        """Filter candidates with reasonable amount relationship."""
        # For now, use a simple tolerance: amounts within 20% of each other
        tolerance = Decimal("0.2")
        min_amount = transaction.amount * (Decimal("1") - tolerance)
        max_amount = transaction.amount * (Decimal("1") + tolerance)
        return [c for c in candidates if min_amount <= c.amount <= max_amount]

    def filter_by_source_compatibility(
        self, transaction: Transaction, candidates: list[Transaction]
    ) -> list[Transaction]:
        """Filter candidates by valid source pairings."""
        valid_pairs = {
            (TransactionSource.GATEWAY, TransactionSource.LEDGER),
            (TransactionSource.LEDGER, TransactionSource.GATEWAY),
            (TransactionSource.GATEWAY, TransactionSource.BANK),
            (TransactionSource.BANK, TransactionSource.GATEWAY),
            (TransactionSource.LEDGER, TransactionSource.BANK),
            (TransactionSource.BANK, TransactionSource.LEDGER),
        }
        return [
            c for c in candidates if (transaction.source, c.source) in valid_pairs
        ]

    def get_candidates(
        self,
        transaction: Transaction,
        target_source: Optional[TransactionSource] = None,
    ) -> list[Transaction]:
        """Get all candidate transactions for matching."""
        if target_source:
            source_transactions = self.transactions_by_source.get(target_source, [])
        else:
            # Get all transactions from other sources
            source_transactions = []
            for source, txns in self.transactions_by_source.items():
                if source != transaction.source:
                    source_transactions.extend(txns)

        candidates = self.filter_by_currency(transaction, source_transactions)
        candidates = self.filter_by_source_compatibility(transaction, candidates)
        candidates = self.filter_by_date_window(transaction, candidates)
        candidates = self.filter_by_amount_range(transaction, candidates)

        return candidates
