import difflib
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.transaction import Transaction, TransactionSource


class FeatureExtractor:
    """Extracts deterministic features for ML candidate scoring."""

    def extract_features(self, txn1: Transaction, txn2: Transaction) -> dict[str, float]:
        """
        Extract numeric features from a transaction pair.
        
        Returns a dictionary of feature names to float values.
        All features are deterministic and use only standard library.
        """
        features = {}
        
        # Amount features
        features["abs_amount_diff"] = self._abs_amount_diff(txn1, txn2)
        features["rel_amount_diff"] = self._rel_amount_diff(txn1, txn2)
        
        # Date features
        features["date_diff_days"] = self._date_diff_days(txn1, txn2)
        features["settlement_window_7d"] = self._settlement_window_7d(txn1, txn2)
        
        # String similarity features
        features["ref_similarity"] = self._ref_similarity(txn1, txn2)
        features["narration_similarity"] = self._narration_similarity(txn1, txn2)
        
        # Binary equality features
        features["currency_equal"] = self._currency_equal(txn1, txn2)
        features["order_id_equal"] = self._order_id_equal(txn1, txn2)
        features["reference_equal"] = self._reference_equal(txn1, txn2)
        
        # Fee/tax consistency features
        features["fee_tax_consistent"] = self._fee_tax_consistent(txn1, txn2)
        features["fee_tax_amount_diff"] = self._fee_tax_amount_diff(txn1, txn2)
        
        # Source pair features
        features["source_pair_gw_ledger"] = self._source_pair_gw_ledger(txn1, txn2)
        features["source_pair_gw_bank"] = self._source_pair_gw_bank(txn1, txn2)
        features["source_pair_ledger_bank"] = self._source_pair_ledger_bank(txn1, txn2)
        
        return features

    def _abs_amount_diff(self, txn1: Transaction, txn2: Transaction) -> float:
        """Absolute difference in amounts."""
        diff = abs(txn1.amount - txn2.amount)
        return float(diff)

    def _rel_amount_diff(self, txn1: Transaction, txn2: Transaction) -> float:
        """Relative difference: |a-b|/max(a,b)."""
        max_amount = max(txn1.amount, txn2.amount)
        if max_amount == 0:
            return 0.0
        diff = abs(txn1.amount - txn2.amount)
        return float(diff / max_amount)

    def _date_diff_days(self, txn1: Transaction, txn2: Transaction) -> float:
        """Absolute date difference in days."""
        delta = txn1.timestamp - txn2.timestamp
        return float(abs(delta.total_seconds()) / 86400.0)

    def _settlement_window_7d(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if within ±7 calendar days."""
        delta = txn1.timestamp - txn2.timestamp
        days = abs(delta.total_seconds()) / 86400.0
        return 1.0 if days <= 7.0 else 0.0

    def _ref_similarity(self, txn1: Transaction, txn2: Transaction) -> float:
        """difflib.SequenceMatcher ratio for references (0 if None)."""
        ref1 = txn1.reference_number or ""
        ref2 = txn2.reference_number or ""
        if not ref1 or not ref2:
            return 0.0
        return difflib.SequenceMatcher(None, ref1, ref2).ratio()

    def _narration_similarity(self, txn1: Transaction, txn2: Transaction) -> float:
        """difflib.SequenceMatcher ratio for narrations (0 if None)."""
        nar1 = txn1.narration or ""
        nar2 = txn2.narration or ""
        if not nar1 or not nar2:
            return 0.0
        return difflib.SequenceMatcher(None, nar1, nar2).ratio()

    def _currency_equal(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if same currency."""
        return 1.0 if txn1.currency == txn2.currency else 0.0

    def _order_id_equal(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if same order_id."""
        if txn1.order_id is None or txn2.order_id is None:
            return 0.0
        return 1.0 if txn1.order_id == txn2.order_id else 0.0

    def _reference_equal(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if exact reference match."""
        if txn1.reference_number is None or txn2.reference_number is None:
            return 0.0
        return 1.0 if txn1.reference_number == txn2.reference_number else 0.0

    def _fee_tax_consistent(self, txn1: Transaction, txn2: Transaction) -> float:
        """
        Binary: 1 if gateway expected amount matches bank within tolerance.
        expected_bank_amount = gross - fee - tax - refund
        """
        # Only applicable for gateway-bank pairs
        if not self._is_gateway_bank_pair(txn1, txn2):
            return 0.0
        
        gateway_txn = self._get_gateway_txn(txn1, txn2)
        bank_txn = self._get_bank_txn(txn1, txn2)
        
        if gateway_txn is None or bank_txn is None:
            return 0.0
        
        # Calculate expected bank amount from gateway
        fee = gateway_txn.fee or Decimal("0")
        tax = gateway_txn.tax or Decimal("0")
        expected_bank = gateway_txn.amount - fee - tax
        
        # Check if within 1% tolerance
        tolerance = Decimal("0.01")
        diff = abs(expected_bank - bank_txn.amount)
        return 1.0 if diff <= expected_bank * tolerance else 0.0

    def _fee_tax_amount_diff(self, txn1: Transaction, txn2: Transaction) -> float:
        """
        Numeric difference between expected and actual bank amount.
        expected_bank_amount = gross - fee - tax - refund
        """
        if not self._is_gateway_bank_pair(txn1, txn2):
            return 0.0
        
        gateway_txn = self._get_gateway_txn(txn1, txn2)
        bank_txn = self._get_bank_txn(txn1, txn2)
        
        if gateway_txn is None or bank_txn is None:
            return 0.0
        
        fee = gateway_txn.fee or Decimal("0")
        tax = gateway_txn.tax or Decimal("0")
        expected_bank = gateway_txn.amount - fee - tax
        
        diff = abs(expected_bank - bank_txn.amount)
        return float(diff)

    def _source_pair_gw_ledger(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if gateway↔ledger."""
        sources = {txn1.source, txn2.source}
        return 1.0 if sources == {TransactionSource.GATEWAY, TransactionSource.LEDGER} else 0.0

    def _source_pair_gw_bank(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if gateway↔bank."""
        sources = {txn1.source, txn2.source}
        return 1.0 if sources == {TransactionSource.GATEWAY, TransactionSource.BANK} else 0.0

    def _source_pair_ledger_bank(self, txn1: Transaction, txn2: Transaction) -> float:
        """Binary: 1 if ledger↔bank."""
        sources = {txn1.source, txn2.source}
        return 1.0 if sources == {TransactionSource.LEDGER, TransactionSource.BANK} else 0.0

    def _is_gateway_bank_pair(self, txn1: Transaction, txn2: Transaction) -> bool:
        """Check if this is a gateway-bank pair."""
        sources = {txn1.source, txn2.source}
        return sources == {TransactionSource.GATEWAY, TransactionSource.BANK}

    def _get_gateway_txn(self, txn1: Transaction, txn2: Transaction) -> Optional[Transaction]:
        """Return the gateway transaction from the pair."""
        if txn1.source == TransactionSource.GATEWAY:
            return txn1
        if txn2.source == TransactionSource.GATEWAY:
            return txn2
        return None

    def _get_bank_txn(self, txn1: Transaction, txn2: Transaction) -> Optional[Transaction]:
        """Return the bank transaction from the pair."""
        if txn1.source == TransactionSource.BANK:
            return txn1
        if txn2.source == TransactionSource.BANK:
            return txn2
        return None
