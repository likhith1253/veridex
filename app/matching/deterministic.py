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
EXACT_3WAY_CONFIDENCE = Decimal("0.98")
EXACT_ORDER_ID_CONFIDENCE = Decimal("0.95")
EXACT_TXN_REF_CONFIDENCE = Decimal("0.97")
AMOUNT_DATE_UNIQUE_CONFIDENCE = Decimal("0.80")
AMBIGUOUS_CONFIDENCE = Decimal("0.30")
DATE_WINDOW_DAYS = 3
MONEY_TOLERANCE = Decimal("0.01")


class DeterministicMatcher:
    """Deterministic matching engine using explicit rules."""

    def __init__(self, transactions_by_source: dict[TransactionSource, list[Transaction]]):
        """Initialize with normalized transactions grouped by source."""
        self.transactions_by_source = transactions_by_source
        self.candidate_generator = CandidateGenerator(transactions_by_source)
        self.matched_combinations = set()  # Track specific combinations to avoid duplicates
        self.matched_txn_ids = set()  # Track transactions already assigned to matches
        self.ambiguous_txn_ids = set()  # Track transactions involved in ambiguous matches
        self.duplicates_detected = []

    def match_all(self) -> list[MatchResult]:
        """Orchestrate matching across all sources."""
        raw_results = []

        # Detect duplicates first
        self._detect_duplicates()

        # Priority 1: Direct 3-way exact matches across Gateway, Ledger, and Bank
        raw_results.extend(self._match_3way_exact())

        # Priority 2: Exact UTR / Reference matches
        raw_results.extend(self._match_by_exact_utr())

        # Priority 3: Exact Order ID matches
        raw_results.extend(self._match_by_order_id())

        # Priority 4: Exact Txn Reference matches
        raw_results.extend(self._match_by_txn_reference())

        # Priority 5: Amount + Date window matches
        raw_results.extend(self._match_by_amount_date())

        # Merge overlapping matches (e.g. GW-LD and GW-BK for the same transaction) into true 3-way matches
        # and enforce the invariant that every transaction belongs to at most one match.
        return self._merge_and_deduplicate_matches(raw_results)

    def _match_3way_exact(self) -> list[MatchResult]:
        """Find true 3-way matches where Gateway, Ledger, and Bank all correspond."""
        results = []
        gateway_txns = self.transactions_by_source.get(TransactionSource.GATEWAY, [])
        ledger_txns = self.transactions_by_source.get(TransactionSource.LEDGER, [])
        bank_txns = self.transactions_by_source.get(TransactionSource.BANK, [])

        if not gateway_txns or not ledger_txns or not bank_txns:
            return results

        # Index ledger by order_id and reference_number
        ledger_by_order = defaultdict(list)
        ledger_by_ref = defaultdict(list)
        for t in ledger_txns:
            if t.order_id:
                ledger_by_order[t.order_id].append(t)
            if t.reference_number:
                ledger_by_ref[t.reference_number].append(t)

        # Index bank by reference_number and order_id
        bank_by_ref = defaultdict(list)
        bank_by_order = defaultdict(list)
        for t in bank_txns:
            if t.reference_number:
                bank_by_ref[t.reference_number].append(t)
            if t.order_id:
                bank_by_order[t.order_id].append(t)

        for g in gateway_txns:
            if g.txn_id in self.matched_txn_ids:
                continue

            # 1. Find Ledger by exact order_id
            matching_ledgers = []
            if g.order_id and g.order_id in ledger_by_order:
                matching_ledgers = [l for l in ledger_by_order[g.order_id] if l.txn_id not in self.matched_txn_ids]
            elif g.reference_number and g.reference_number in ledger_by_ref:
                matching_ledgers = [l for l in ledger_by_ref[g.reference_number] if l.txn_id not in self.matched_txn_ids]

            if len(matching_ledgers) != 1:
                continue
            l = matching_ledgers[0]
            if l.currency != g.currency:
                continue

            # 2. Find Bank counterpart (prefer reference_number / UTR, then order_id)
            matching_banks = []
            if g.reference_number and g.reference_number in bank_by_ref:
                matching_banks = [b for b in bank_by_ref[g.reference_number] if b.txn_id not in self.matched_txn_ids]
            elif g.order_id and g.order_id in bank_by_order:
                matching_banks = [b for b in bank_by_order[g.order_id] if b.txn_id not in self.matched_txn_ids]

            if len(matching_banks) != 1:
                continue
            b = matching_banks[0]
            if b.currency != g.currency:
                continue

            # Check financial consistency - identifiers establish identity, not reconciliation.
            gw_ld_match = self._money_equal(l.amount, g.amount)
            expected_bank = calculate_expected_bank_amount(g)
            gw_bk_match = (expected_bank is not None and self._money_equal(b.amount, expected_bank))
            expected_fee_rate = Decimal("0.015") if g.amount >= Decimal("100000") else Decimal("0.02")
            expected_fee = g.amount * expected_fee_rate
            expected_tax = expected_fee * Decimal("0.18")
            fee_tax_valid = (
                g.fee is not None
                and g.tax is not None
                and self._money_equal(g.fee, expected_fee)
                and self._money_equal(g.tax, expected_tax)
            )
            g_ts = g.timestamp.replace(tzinfo=None) if g.timestamp.tzinfo else g.timestamp
            b_ts = b.timestamp.replace(tzinfo=None) if b.timestamp.tzinfo else b.timestamp
            settlement_days = abs((b_ts - g_ts).total_seconds()) / 86400
            settlement_timing_valid = settlement_days <= DATE_WINDOW_DAYS
            
            # If amounts don't match at all, still match but with lower confidence
            # This allows detection of amount_mismatch exceptions
            if not gw_ld_match and not gw_bk_match:
                # All amounts differ - match with low confidence for exception detection
                confidence = Decimal("0.75")
                reason = f"3-way identifier match with amount differences: {g.order_id or g.reference_number}"
            elif not gw_ld_match or not gw_bk_match or not fee_tax_valid or not settlement_timing_valid:
                # Partial amount mismatch - match with medium confidence
                confidence = Decimal("0.85")
                reason = f"3-way identifier match with financial validation difference: {g.order_id or g.reference_number}"
            else:
                # All amounts match - high confidence
                confidence = EXACT_3WAY_CONFIDENCE
                reason = f"Exact 3-way match (Order ID + UTR): {g.order_id or g.reference_number}"

            # Valid 3-way match found!
            txn_ids = [g.txn_id, l.txn_id, b.txn_id]
            match_key = tuple(sorted(txn_ids))
            self.matched_combinations.add(match_key)
            self.matched_txn_ids.update(txn_ids)

            evidence = {
                "order_id": g.order_id or l.order_id,
                "reference": g.reference_number or b.reference_number,
                "gateway_amount": str(g.amount),
                "ledger_amount": str(l.amount),
                "bank_amount": str(b.amount),
                "expected_bank": str(expected_bank) if expected_bank is not None else None,
                "fee_tax_valid": fee_tax_valid,
                "settlement_timing_valid": settlement_timing_valid,
                "settlement_days": settlement_days,
                "sources": ["gateway", "ledger", "bank"],
                "three_way_match": True,
            }
            if g.fee:
                evidence["fee"] = str(g.fee)
            if g.tax:
                evidence["tax"] = str(g.tax)

            results.append(
                self._build_match_result(
                    txn_ids,
                    confidence,
                    reason,
                    evidence,
                )
            )

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
            if txn.reference_number and txn.txn_id not in self.matched_txn_ids:
                ref_groups[txn.reference_number].append(txn)

        for ref, txns in ref_groups.items():
            sources = {t.source for t in txns}
            if len(sources) < 2:
                continue

            currencies = {t.currency for t in txns}
            if len(currencies) > 1:
                continue

            amounts = {t.amount for t in txns}
            if len(amounts) == 1:
                txn_ids = [t.txn_id for t in txns]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations and not any(t in self.matched_txn_ids for t in txn_ids):
                    self.matched_combinations.add(match_key)
                    self.matched_txn_ids.update(txn_ids)
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            EXACT_UTR_CONFIDENCE,
                            f"Exact UTR match: {ref}",
                            {"reference": ref, "amount": str(list(amounts)[0])},
                        )
                    )
            elif len(amounts) > 1:
                # Different amounts with same reference - this is an amount mismatch exception
                # Only match if it's a legitimate fee adjustment (gateway-bank pair)
                gateway_txns = [t for t in txns if t.source == TransactionSource.GATEWAY]
                bank_txns = [t for t in txns if t.source == TransactionSource.BANK]
                ledger_txns = [t for t in txns if t.source == TransactionSource.LEDGER]

                # Only allow fee adjustment for gateway-bank pairs
                if gateway_txns and bank_txns and not ledger_txns:
                    for gateway_txn in gateway_txns:
                        if gateway_txn.txn_id in self.matched_txn_ids:
                            continue
                        expected_bank = calculate_expected_bank_amount(gateway_txn)
                        for bank_txn in bank_txns:
                            if bank_txn.txn_id in self.matched_txn_ids:
                                continue
                            if expected_bank and bank_txn.amount == expected_bank:
                                txn_ids = [gateway_txn.txn_id, bank_txn.txn_id]
                                match_key = tuple(sorted(txn_ids))
                                if match_key not in self.matched_combinations:
                                    self.matched_combinations.add(match_key)
                                    self.matched_txn_ids.update(txn_ids)
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
                # If amounts don't match even with fee adjustment, or if ledger is involved, don't match - let it become an exception

        return results

    def _match_by_order_id(self) -> list[MatchResult]:
        """Match gateway↔ledger by exact order ID.
        
        Match even when amounts differ - the decision engine will flag amount mismatches as exceptions.
        This allows the system to detect amount_mismatch scenarios instead of treating them as missing records.
        """
        results = []
        gateway_txns = self.transactions_by_source.get(TransactionSource.GATEWAY, [])
        ledger_txns = self.transactions_by_source.get(TransactionSource.LEDGER, [])

        gateway_by_order = defaultdict(list)
        for txn in gateway_txns:
            if txn.order_id and txn.txn_id not in self.matched_txn_ids:
                gateway_by_order[txn.order_id].append(txn)

        ledger_by_order = defaultdict(list)
        for txn in ledger_txns:
            if txn.order_id and txn.txn_id not in self.matched_txn_ids:
                ledger_by_order[txn.order_id].append(txn)

        for order_id, g_txns in gateway_by_order.items():
            if order_id in ledger_by_order:
                l_txns = ledger_by_order[order_id]

                if len(g_txns) == 1 and len(l_txns) == 1:
                    g_txn = g_txns[0]
                    l_txn = l_txns[0]

                    if g_txn.currency == l_txn.currency:
                        txn_ids = [g_txn.txn_id, l_txn.txn_id]
                        match_key = tuple(sorted(txn_ids))
                        if match_key not in self.matched_combinations and not any(t in self.matched_txn_ids for t in txn_ids):
                            self.matched_combinations.add(match_key)
                            self.matched_txn_ids.update(txn_ids)
                            
                            # Use high confidence if amounts match, lower confidence if they differ
                            if g_txn.amount == l_txn.amount:
                                confidence = EXACT_ORDER_ID_CONFIDENCE
                                reason = f"Exact order ID match: {order_id}"
                                evidence = {"order_id": order_id}
                            else:
                                confidence = Decimal("0.85")  # Lower confidence for amount mismatch
                                reason = f"Order ID match with amount difference: {order_id}"
                                evidence = {
                                    "order_id": order_id,
                                    "gateway_amount": str(g_txn.amount),
                                    "ledger_amount": str(l_txn.amount),
                                    "amount_difference": str(abs(g_txn.amount - l_txn.amount))
                                }
                            
                            results.append(
                                self._build_match_result(
                                    txn_ids,
                                    confidence,
                                    reason,
                                    evidence,
                                )
                            )

        return results

    def _match_by_txn_reference(self) -> list[MatchResult]:
        """Match by exact transaction/reference relationship.
        
        Match even when amounts differ - the decision engine will flag amount mismatches as exceptions.
        This allows the system to detect amount_mismatch scenarios instead of treating them as missing records.
        """
        results = []
        all_transactions = []
        for txns in self.transactions_by_source.values():
            all_transactions.extend(txns)

        ref_groups = defaultdict(list)
        for txn in all_transactions:
            if txn.reference_number and txn.txn_id not in self.matched_txn_ids:
                ref_groups[txn.reference_number].append(txn)

        for ref, txns in ref_groups.items():
            sources = {t.source for t in txns}
            if len(sources) < 2:
                continue

            currencies = {t.currency for t in txns}
            if len(currencies) > 1:
                continue

            # Remove the amount check - match even when amounts differ
            amounts = {t.amount for t in txns}
            has_amount_mismatch = len(amounts) > 1

            if len(txns) == 2:
                gateway_txns = [t for t in txns if t.source == TransactionSource.GATEWAY]
                bank_txns = [t for t in txns if t.source == TransactionSource.BANK]
                if has_amount_mismatch and gateway_txns and bank_txns:
                    expected_bank = calculate_expected_bank_amount(gateway_txns[0])
                    if expected_bank is None or not self._money_equal(bank_txns[0].amount, expected_bank):
                        continue

                txn_ids = [t.txn_id for t in txns]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations and not any(t in self.matched_txn_ids for t in txn_ids):
                    self.matched_combinations.add(match_key)
                    self.matched_txn_ids.update(txn_ids)
                    
                    # Use high confidence if amounts match, lower confidence if they differ
                    if has_amount_mismatch:
                        confidence = Decimal("0.85")
                        reason = f"Reference match with amount difference: {ref}"
                        evidence = {
                            "reference": ref,
                            "amounts": [str(t.amount) for t in txns]
                        }
                    else:
                        confidence = EXACT_TXN_REF_CONFIDENCE
                        reason = f"Exact transaction reference match: {ref}"
                        evidence = {"reference": ref}
                    
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            confidence,
                            reason,
                            evidence,
                        )
                    )
            elif len(txns) > 2:
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
            if txn.txn_id in self.ambiguous_txn_ids or txn.txn_id in self.matched_txn_ids:
                continue

            already_matched = False
            for combo in self.matched_combinations:
                if txn.txn_id in combo:
                    already_matched = True
                    break
            if already_matched:
                continue

            candidates = self.candidate_generator.get_candidates(txn)

            candidates = [
                c for c in candidates
                if c.txn_id not in self.ambiguous_txn_ids
                and c.txn_id not in self.matched_txn_ids
                and not any(c.txn_id in combo for combo in self.matched_combinations)
            ]

            if not candidates:
                continue

            # Filter out candidates that share order_id or reference_number but have different amounts
            # These should be exceptions, not matches - record them for exception classification
            filtered_candidates = []
            potential_exceptions = []
            for candidate in candidates:
                # Check if they share order_id
                if txn.order_id and candidate.order_id and txn.order_id == candidate.order_id:
                    if txn.amount != candidate.amount:
                        # Same order_id, different amount - record as potential exception
                        potential_exceptions.append({
                            "type": "amount_mismatch",
                            "reason": "same_order_id_different_amount",
                            "txn_id": txn.txn_id,
                            "candidate_id": candidate.txn_id,
                            "order_id": txn.order_id,
                            "amount_difference": str(abs(txn.amount - candidate.amount))
                        })
                        continue
                # Check if they share reference_number
                if txn.reference_number and candidate.reference_number and txn.reference_number == candidate.reference_number:
                    if txn.amount != candidate.amount:
                        # Same reference, different amount - record as potential exception
                        potential_exceptions.append({
                            "type": "amount_mismatch",
                            "reason": "same_reference_different_amount",
                            "txn_id": txn.txn_id,
                            "candidate_id": candidate.txn_id,
                            "reference": txn.reference_number,
                            "amount_difference": str(abs(txn.amount - candidate.amount))
                        })
                        continue
                filtered_candidates.append(candidate)
            
            candidates = filtered_candidates

            # Store potential exceptions for later classification
            if potential_exceptions:
                self.duplicates_detected.extend(potential_exceptions)

            if not candidates:
                continue

            if len(candidates) == 1:
                candidate = candidates[0]
                txn_ids = [txn.txn_id, candidate.txn_id]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
                    ts1 = txn.timestamp.replace(tzinfo=None) if hasattr(txn.timestamp, "replace") else txn.timestamp
                    ts2 = candidate.timestamp.replace(tzinfo=None) if hasattr(candidate.timestamp, "replace") else candidate.timestamp
                    results.append(
                        self._build_match_result(
                            txn_ids,
                            AMOUNT_DATE_UNIQUE_CONFIDENCE,
                            f"Amount + date match (±{DATE_WINDOW_DAYS} days)",
                            {
                                "amount": str(txn.amount),
                                "date_diff": str(abs((ts1 - ts2).days)),
                            },
                        )
                    )
            elif len(candidates) > 1:
                txn_ids = [txn.txn_id] + [c.txn_id for c in candidates]
                match_key = tuple(sorted(txn_ids))
                if match_key not in self.matched_combinations:
                    self.matched_combinations.add(match_key)
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

    def _merge_and_deduplicate_matches(self, raw_matches: list[MatchResult]) -> list[MatchResult]:
        """Merge overlapping matches (e.g. GW-LD and GW-BK for the same transaction) into true 3-way matches
        and enforce the invariant that every transaction belongs to at most one final match.
        """
        if not raw_matches:
            return []

        txn_to_group = {}
        groups: list[set[str]] = []
        group_matches: list[list[MatchResult]] = []

        for match in raw_matches:
            matched_group_indices = set()
            for tid in match.transaction_ids:
                if tid in txn_to_group:
                    matched_group_indices.add(txn_to_group[tid])

            if not matched_group_indices:
                new_idx = len(groups)
                groups.append(set(match.transaction_ids))
                group_matches.append([match])
                for tid in match.transaction_ids:
                    txn_to_group[tid] = new_idx
            else:
                main_idx = min(matched_group_indices)
                for other_idx in sorted(matched_group_indices, reverse=True):
                    if other_idx != main_idx:
                        groups[main_idx].update(groups[other_idx])
                        group_matches[main_idx].extend(group_matches[other_idx])
                        for tid in groups[other_idx]:
                            txn_to_group[tid] = main_idx
                        groups[other_idx] = set()
                        group_matches[other_idx] = []

                groups[main_idx].update(match.transaction_ids)
                group_matches[main_idx].append(match)
                for tid in match.transaction_ids:
                    txn_to_group[tid] = main_idx

        final_results = []
        all_txns_by_id = {t.txn_id: t for txns in self.transactions_by_source.values() for t in txns}

        for group, m_list in zip(groups, group_matches):
            if not group or not m_list:
                continue

            merged_txn_ids = sorted(list(group))
            sources_list = [all_txns_by_id[tid].source.value for tid in merged_txn_ids if tid in all_txns_by_id]
            unique_sources = set(sources_list)

            max_conf = max(m.confidence for m in m_list)
            combined_evidence = {}
            for m in m_list:
                if m.evidence:
                    combined_evidence.update(m.evidence)

            # Check if there are multiple transactions from the same source (ambiguity)
            has_duplicates_per_source = len(merged_txn_ids) > len(unique_sources)
            is_explicitly_ambiguous = any(m.confidence == AMBIGUOUS_CONFIDENCE for m in m_list)

            if has_duplicates_per_source or is_explicitly_ambiguous:
                # Ambiguous candidate cluster
                combined_evidence["sources"] = sorted(list(unique_sources))
                combined_evidence["candidate_count"] = len(merged_txn_ids)
                final_results.append(
                    self._build_match_result(
                        merged_txn_ids,
                        AMBIGUOUS_CONFIDENCE,
                        f"Ambiguous match ({len(merged_txn_ids)} candidates across {len(unique_sources)} sources)",
                        combined_evidence,
                    )
                )
            elif unique_sources == {"gateway", "ledger", "bank"} and all(m.confidence >= Decimal("0.90") for m in m_list):
                # True exact 3-way match
                combined_evidence["sources"] = ["gateway", "ledger", "bank"]
                combined_evidence["three_way_match"] = True
                order_ref = combined_evidence.get("order_id") or combined_evidence.get("reference") or merged_txn_ids[0]
                final_results.append(
                    self._build_match_result(
                        merged_txn_ids,
                        max(max_conf, EXACT_UTR_CONFIDENCE),
                        f"Exact 3-way match (Order ID + UTR): {order_ref}",
                        combined_evidence,
                    )
                )
            else:
                # Clean exact or amount+date match
                combined_evidence["sources"] = sorted(list(unique_sources))
                primary_reason = m_list[0].reason
                final_results.append(
                    self._build_match_result(
                        merged_txn_ids,
                        max_conf,
                        primary_reason,
                        combined_evidence,
                    )
                )

        return final_results

    @staticmethod
    def _money_equal(left: Optional[Decimal], right: Optional[Decimal]) -> bool:
        if left is None or right is None:
            return False
        return abs(left - right) <= MONEY_TOLERANCE

    def _detect_ambiguity(self, candidates: list[Transaction]) -> bool:
        """Check for multiple plausible candidates."""
        return len(candidates) > 1

    def _detect_duplicates(self) -> None:
        """Detect duplicate records with multiple patterns."""
        for source, txns in self.transactions_by_source.items():
            # Pattern 1: Same source + same reference + same amount (original)
            ref_amount_groups = defaultdict(list)
            for txn in txns:
                if txn.reference_number:
                    key = (txn.source, txn.reference_number, txn.amount)
                    ref_amount_groups[key].append(txn)

            for key, group in ref_amount_groups.items():
                if len(group) > 1:
                    self.duplicates_detected.append(
                        {
                            "type": "duplicate_exact",
                            "source": key[0],
                            "reference": key[1],
                            "amount": key[2],
                            "count": len(group),
                            "txn_ids": [t.txn_id for t in group],
                        }
                    )
            
            # Pattern 2: Same source + same reference + different amount
            ref_groups = defaultdict(list)
            for txn in txns:
                if txn.reference_number:
                    key = (txn.source, txn.reference_number)
                    ref_groups[key].append(txn)
            
            for key, group in ref_groups.items():
                if len(group) > 1:
                    amounts = {t.amount for t in group}
                    if len(amounts) > 1:
                        self.duplicates_detected.append(
                            {
                                "type": "duplicate_amount_mismatch",
                                "source": key[0],
                                "reference": key[1],
                                "amounts": [str(a) for a in amounts],
                                "count": len(group),
                                "txn_ids": [t.txn_id for t in group],
                            }
                        )
            
            # Pattern 3: Same source + same order_id + different amount
            order_groups = defaultdict(list)
            for txn in txns:
                if txn.order_id:
                    key = (txn.source, txn.order_id)
                    order_groups[key].append(txn)
            
            for key, group in order_groups.items():
                if len(group) > 1:
                    amounts = {t.amount for t in group}
                    if len(amounts) > 1:
                        self.duplicates_detected.append(
                            {
                                "type": "duplicate_order_amount_mismatch",
                                "source": key[0],
                                "order_id": key[1],
                                "amounts": [str(a) for a in amounts],
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
