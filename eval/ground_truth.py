from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from simulator.ground_truth import GroundTruth, GroundTruthRecord


class GroundTruthIndex:
    """Fast lookup index mapping source transaction IDs to ground truth records."""

    def __init__(self, ground_truth: GroundTruth):
        self.ground_truth = ground_truth
        self.txn_id_to_logical: dict[str, str] = {}
        self.logical_to_record: dict[str, GroundTruthRecord] = {}
        self._build_index()

    def _build_index(self) -> None:
        for logical_id, rec in self.ground_truth.records.items():
            self.logical_to_record[logical_id] = rec
            # Gateway normalized ID is logical_id (transaction_id in CSV)
            self.txn_id_to_logical[logical_id] = logical_id
            # Also map gateway_record_id if different
            if rec.gateway_record_id:
                self.txn_id_to_logical[rec.gateway_record_id] = logical_id
            # Ledger normalized ID is ledger_record_id (order_id in CSV)
            if rec.ledger_record_id:
                self.txn_id_to_logical[rec.ledger_record_id] = logical_id
            # Bank normalized ID is bank_record_id (bank_transaction_id in CSV)
            if rec.bank_record_id:
                self.txn_id_to_logical[rec.bank_record_id] = logical_id

    def get_logical_id(self, txn_id: str) -> Optional[str]:
        """Look up the logical transaction ID for any source transaction ID."""
        return self.txn_id_to_logical.get(txn_id)

    def get_record_by_txn_id(self, txn_id: str) -> Optional[GroundTruthRecord]:
        """Look up the GroundTruthRecord for a source transaction ID."""
        logical_id = self.get_logical_id(txn_id)
        if logical_id:
            return self.logical_to_record.get(logical_id)
        return None

    def get_record(self, logical_id: str) -> Optional[GroundTruthRecord]:
        """Look up by logical transaction ID."""
        return self.logical_to_record.get(logical_id)

    def is_valid_match_pair(self, txn_id_1: str, txn_id_2: str) -> tuple[bool, Optional[GroundTruthRecord]]:
        """Determine if a pair of transaction IDs represents a true match according to ground truth.

        Returns:
            (is_true_match, ground_truth_record)
        """
        log1 = self.get_logical_id(txn_id_1)
        log2 = self.get_logical_id(txn_id_2)

        if not log1 or not log2:
            return False, None

        if log1 != log2:
            return False, self.get_record(log1)

        rec = self.get_record(log1)
        if rec and rec.true_match:
            return True, rec

        return False, rec

    def is_valid_match_group(self, txn_ids: list[str]) -> tuple[bool, Optional[GroundTruthRecord]]:
        """Determine if all transaction IDs in a match group belong to the same true match.

        Returns:
            (is_true_match, ground_truth_record)
        """
        if len(txn_ids) < 2:
            return False, None

        logical_ids = [self.get_logical_id(tid) for tid in txn_ids]
        if any(lid is None for lid in logical_ids):
            return False, None

        first_lid = logical_ids[0]
        if not all(lid == first_lid for lid in logical_ids):
            return False, self.get_record(first_lid)

        rec = self.get_record(first_lid)
        if rec and rec.true_match:
            return True, rec

        return False, rec
