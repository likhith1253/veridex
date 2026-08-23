from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.matching.candidate import CandidateGenerator
from app.matching.financial_utils import calculate_expected_bank_amount
from app.models.match_result import MatchResult, MatchType
from app.models.transaction import Transaction, TransactionSource

# Confidence policy constants
EXACT_UTR_CONFIDENCE = Decimal("0.98")
EXACT_ORDER_ID_CONFIDENCE = Decimal("0.95")
EXACT_TXN_REF_CONFIDENCE = Decimal("0.97")
AMOUNT_DATE_UNIQUE_CONFIDENCE = Decimal("0.80")
AMBIGUOUS_CONFIDENCE = Decimal("0.30")
DATE_WINDOW_DAYS = 3


class DeterministicMatcher:
    """Deterministic matching engine using explicit rules."""

    def __init__(self, transactions_by_source: dict[TransactionSource, list[Transaction]]):
        """Initialize with normalized transactions grouped by source."""
        self.transactions_by_source = transactions_by_source
        self.candidate_generator = CandidateGenerator(transactions_by_source)
        self.matched_combinations = set()  # Track specific combinations to avoid duplicates
        self.ambiguous_txn_ids = set()  # Track transactions involved in ambiguous matches
        self.duplicates_detected = []

    def match_all(self) -> list[MatchResult]:
        """Orchestrate matching across all sources."""
        results = []

        # Detect duplicates first
        self._detect_duplicates()

        # Priority order: exact UTR, exact order ID, exact txn ref, amount+date
        results.extend(self._match_by_exact_utr())
        results.extend(self._match_by_order_id())
        results.extend(self._match_by_txn_reference())
        results.extend(self._match_by_amount_date())

        return results

    def _match_by_exact_utr(self) -> list[MatchResult]:
        """Match by exact UTR/reference with amount consistency."""
        results = []
        all_transactions = []
        for txns in self.transactions_by_source.values():
            all_transactions.extend(txns)

        # Group by reference number
        ref_groups = defaultdict(list)
        for txn in all_transactions:
            if txn.reference_number:
                ref_groups[txn.reference_number].append(txn)

        for ref, txns in ref_groups.items():
            # Only match if we have transactions from different sources
            sources = {t.source for t in txns}
            if len(sources) < 2:
                continue

            # Check for currency compatibility
            currencies = {t.currency for t in txns}
            if len(currencies) > 1:
                continue

            # Check for amount consistency
            amounts = {t.amount for t in txns}
            if len(amounts) == 1:
                # All same amount - high confidence match
                txn_ids = [t.txn_id for t in txns]
                # Track this specific combination to avoid duplicates
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            EXACT_UTR_CONFIDENCE,
                            f"Exact UTR match: {ref}",
                            {"reference": ref, "amount": str(list(amounts)[0])},
                        )
                    )
            elif len(amounts) > 1:
                # Different amounts - check for fee/refund relationship
                # Try to find a gateway transaction and calculate expected bank amount
                gateway_txns = [t for t in txns if t.source == TransactionSource.GATEWAY]
                bank_txns = [t for t in txns if t.source == TransactionSource.BANK]

                if gateway_txns and bank_txns:
                    for gateway_txn in gateway_txns:
                        expected_bank = calculate_expected_bank_amount(gateway_txn)
                        for bank_txn in bank_txns:
                            if expected_bank and bank_txn.amount == expected_bank:
                                txn_ids = [gateway_txn.txn_id, bank_txn.txn_id]
                                match_key = tuple(sorted(txn_ids))
                                if match_key not in self.matched_combinations:
                                    self.matched_combinations.add(match_key)
                                    results.append(
                                        self._build_match_result(
                                            txn_ids,
                                            EXACT_UTR_CONFIDENCE,
                                            f"Exact UTR match with fee adjustment: {ref}",
                                            {
                                                "reference": ref,
                                                "gateway_amount": str(gateway_txn.amount),
                                                "bank_amount": str(bank_txn.amount),
                                                "fee": str(gateway_txn.fee or 0),
                                                "tax": str(gateway_txn.tax or 0),
                                            },
                                        )
                                    )

        return results

    def _match_by_order_id(self) -> list[MatchResult]:
        """Match gateway↔ledger by exact order ID."""
        results = []
        gateway_txns = self.transactions_by_source.get(TransactionSource.GATEWAY, [])
        ledger_txns = self.transactions_by_source.get(TransactionSource.LEDGER, [])

        # Group gateway by order_id
        gateway_by_order = defaultdict(list)
        for txn in gateway_txns:
            if txn.order_id:
                gateway_by_order[txn.order_id].append(txn)

        # Group ledger by order_id
        ledger_by_order = defaultdict(list)
        for txn in ledger_txns:
            if txn.order_id:
                ledger_by_order[txn.order_id].append(txn)

        # Match by order ID
        for order_id, g_txns in gateway_by_order.items():
            if order_id in ledger_by_order:
                l_txns = ledger_by_order[order_id]

                # Check for ambiguity
                if len(g_txns) == 1 and len(l_txns) == 1:
                    g_txn = g_txns[0]
                    l_txn = l_txns[0]

                    # Verify currency match
                    if g_txn.currency == l_txn.currency:
                        txn_ids = [g_txn.txn_id, l_txn.txn_id]
                        match_key = tuple(sorted(txn_ids))
                        if match_key not in self.matched_combinations:
                            self.matched_combinations.add(match_key)
                            results.append(
                                self._build_match_result(
                                    txn_ids,
                                    EXACT_ORDER_ID_CONFIDENCE,
                                    f"Exact order ID match: {order_id}",
                                    {"order_id": order_id},
                                )
                            )

        return results

    def _match_by_txn_reference(self) -> list[MatchResult]:
        """Match by exact transaction/reference relationship."""
        results = []
        all_transactions = []
        for txns in self.transactions_by_source.values():
            all_transactions.extend(txns)

        # Group by reference number
        ref_groups = defaultdict(list)
        for txn in all_transactions:
            if txn.reference_number:
                ref_groups[txn.reference_number].append(txn)

        for ref, txns in ref_groups.items():
            # Only match if we have transactions from different sources
            sources = {t.source for t in txns}
            if len(sources) < 2:
                continue

            # Check for currency compatibility
            currencies = {t.currency for t in txns}
            if len(currencies) > 1:
                continue

            # Check for amount consistency
            amounts = {t.amount for t in txns}
            if len(amounts) > 1:
                # Different amounts - don't match via reference alone
                continue

            # Check for ambiguity
            if len(txns) == 2:
                txn_ids = [t.txn_id for t in txns]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            EXACT_TXN_REF_CONFIDENCE,
                            f"Exact transaction reference match: {ref}",
                            {"reference": ref},
                        )
                    )
            elif len(txns) > 2:
                # Multiple candidates - mark as ambiguous
                txn_ids = [t.txn_id for t in txns]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            AMBIGUOUS_CONFIDENCE,
                            f"Ambiguous reference match: {ref} ({len(txns)} candidates)",
                            {"reference": ref, "candidate_count": len(txns)},
                        )
                    )

        return results

    def _match_by_amount_date(self) -> list[MatchResult]:
        """Match by amount + date window with uniqueness check."""
        results = []
        all_transactions = []
        for txns in self.transactions_by_source.values():
            all_transactions.extend(txns)

        for txn in all_transactions:
            # Skip if already involved in ambiguous match or already matched
            if txn.txn_id in self.ambiguous_txn_ids:
                continue

            # Check if this transaction is already part of a high-confidence match
            already_matched = False
            for combo in self.matched_combinations:
                if txn.txn_id in combo:
                    already_matched = True
                    break
            if already_matched:
                continue

            candidates = self.candidate_generator.get_candidates(txn)

            # Filter out candidates already involved in ambiguous matches or already matched
            candidates = [
                c for c in candidates
                if c.txn_id not in self.ambiguous_txn_ids and not any(
                    c.txn_id in combo for combo in self.matched_combinations
                )
            ]

            if not candidates:
                continue

            # Check for uniqueness
            if len(candidates) == 1:
                candidate = candidates[0]
                txn_ids = [txn.txn_id, candidate.txn_id]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            AMOUNT_DATE_UNIQUE_CONFIDENCE,
                            f"Amount + date match (±{DATE_WINDOW_DAYS} days)",
                            {
                                "amount": str(txn.amount),
                                "date_diff": str(abs((txn.timestamp - candidate.timestamp).days)),
                            },
                        )
                    )
            elif len(candidates) > 1:
                # Multiple candidates - mark as ambiguous and mark all as matched to prevent further matching
                txn_ids = [txn.txn_id] + [c.txn_id for c in candidates]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
                    # Mark all involved transactions as ambiguous
                    for tid in txn_ids:
                        self.ambiguous_txn_ids.add(tid)
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            AMBIGUOUS_CONFIDENCE,
                            f"Ambiguous amount/date match ({len(candidates)} candidates)",
                            {"candidate_count": len(candidates)},
                        )
                    )

        return results

    def _detect_ambiguity(self, candidates: list[Transaction]) -> bool:
        """Check for multiple plausible candidates."""
        return len(candidates) > 1

    def _detect_duplicates(self) -> None:
        """Detect duplicate records (same source + same reference + same amount)."""
        for source, txns in self.transactions_by_source.items():
            ref_amount_groups = defaultdict(list)
            for txn in txns:
                if txn.reference_number:
                    key = (txn.source, txn.reference_number, txn.amount)
                    ref_amount_groups[key].append(txn)

            for key, group in ref_amount_groups.items():
                if len(group) > 1:
                    self.duplicates_detected.append(
                        {
                            "source": key[0],
                            "reference": key[1],
                            "amount": key[2],
                            "count": len(group),
                            "txn_ids": [t.txn_id for t in group],
                        }
                    )

    def _build_match_result(
        self,
        transaction_ids: list[str],
        confidence: Decimal,
        reason: str,
        evidence: dict,
    ) -> MatchResult:
        """Create a MatchResult with documented confidence."""
        match_type = MatchType.EXACT if confidence >= Decimal("0.90") else MatchType.PROBABLE

        return MatchResult(
            transaction_ids=transaction_ids,
            confidence=confidence,
            reason=reason,
            match_type=match_type,
            evidence=evidence,
            recommended_action=None,
        )
