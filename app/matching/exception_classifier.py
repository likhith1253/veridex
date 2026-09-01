"""
Exception Classification Module
Separates matching from exception classification to properly categorize financial discrepancies
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

from app.matching.financial_utils import calculate_expected_bank_amount
from app.models.exception_record import ExceptionCategory
from app.models.transaction import Transaction, TransactionSource


MONEY_TOLERANCE = Decimal("0.01")
STANDARD_FEE_RATE = Decimal("0.02")
HIGH_VALUE_FEE_RATE = Decimal("0.015")
STANDARD_TAX_RATE = Decimal("0.18")
SETTLEMENT_WINDOW_DAYS = 3


class ExceptionClassifier:
    """Classifies financial discrepancies into specific exception categories"""

    @staticmethod
    def _money_equal(left: Optional[Decimal], right: Optional[Decimal]) -> bool:
        if left is None or right is None:
            return False
        return abs(left - right) <= MONEY_TOLERANCE

    @staticmethod
    def _source_name(source: TransactionSource) -> str:
        return source.value if hasattr(source, "value") else str(source)

    @classmethod
    def _base(
        cls,
        category: ExceptionCategory,
        confidence: Decimal,
        exposure: Decimal,
        explanation: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "has_exception": True,
            "exception_type": category.value.removesuffix("_exception"),
            "exception_category": category.value,
            "category": category,
            "confidence": confidence,
            "financial_exposure": abs(exposure),
            "explanation": explanation,
            "evidence": evidence,
        }

    @staticmethod
    def _time_span_days(transactions: list[Transaction]) -> Decimal:
        timestamps = [t.timestamp.replace(tzinfo=None) if t.timestamp.tzinfo else t.timestamp for t in transactions if t.timestamp]
        if len(timestamps) < 2:
            return Decimal("0")
        return Decimal(str((max(timestamps) - min(timestamps)).total_seconds())) / Decimal("86400")

    @classmethod
    def _expected_fee(cls, gw: Transaction) -> Decimal:
        rate = HIGH_VALUE_FEE_RATE if gw.amount >= Decimal("100000") else STANDARD_FEE_RATE
        return gw.amount * rate

    @classmethod
    def _expected_tax(cls, fee: Decimal) -> Decimal:
        return fee * STANDARD_TAX_RATE
    
    def classify_transaction_group(
        self, 
        transactions: List[Transaction],
        match_evidence: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Classify a group of transactions that have been matched/associated but may have financial discrepancies.
        
        Returns exception classification if discrepancies exist, None if financially consistent.
        """
        if not transactions:
            return None
        
        # Separate by source
        gateway_txns = [t for t in transactions if t.source == TransactionSource.GATEWAY]
        ledger_txns = [t for t in transactions if t.source == TransactionSource.LEDGER]
        bank_txns = [t for t in transactions if t.source == TransactionSource.BANK]

        evidence = {
            "transaction_ids": [t.txn_id for t in transactions],
            "sources": [self._source_name(t.source) for t in transactions],
            "amounts": {t.txn_id: str(t.amount) for t in transactions},
            "order_ids": sorted({t.order_id for t in transactions if t.order_id}),
            "references": sorted({t.reference_number for t in transactions if t.reference_number}),
        }

        source_counts = {source: len(items) for source, items in (
            ("gateway", gateway_txns),
            ("ledger", ledger_txns),
            ("bank", bank_txns),
        )}
        if any(count > 1 for count in source_counts.values()):
            exposure = max((t.amount for t in transactions), default=Decimal("0"))
            evidence["source_counts"] = source_counts
            return self._base(
                ExceptionCategory.DUPLICATE_EXCEPTION,
                Decimal("0.98"),
                exposure,
                "Duplicate source records share the same transaction identity.",
                evidence,
            )
        
        missing_sources = []
        if not gateway_txns:
            missing_sources.append("gateway")
        if not ledger_txns:
            missing_sources.append("ledger")
        if not bank_txns:
            missing_sources.append("bank")
        
        if missing_sources and len(transactions) >= 2:
            evidence["missing_sources"] = missing_sources
            return self._base(
                ExceptionCategory.MISSING_SOURCE_EXCEPTION,
                Decimal("0.96"),
                max(t.amount for t in transactions),
                f"Identity match is missing source records: {', '.join(missing_sources)}.",
                evidence,
            )

        if not (gateway_txns and ledger_txns and bank_txns):
            return None

        gw = gateway_txns[0]
        ld = ledger_txns[0]
        bk = bank_txns[0]
        expected_bank = calculate_expected_bank_amount(gw)
        gw_ld_equal = self._money_equal(gw.amount, ld.amount)
        bank_equal_expected = self._money_equal(bk.amount, expected_bank)
        bank_equal_gross = self._money_equal(bk.amount, gw.amount)
        expected_fee = self._expected_fee(gw)
        observed_fee = gw.fee
        observed_tax = gw.tax
        expected_tax_from_observed_fee = self._expected_tax(observed_fee or Decimal("0"))
        expected_tax_from_expected_fee = self._expected_tax(expected_fee)
        order_conflict = bool(gw.order_id and ld.order_id and gw.order_id != ld.order_id)
        time_span_days = self._time_span_days(transactions)

        evidence.update({
            "gateway_amount": str(gw.amount),
            "ledger_amount": str(ld.amount),
            "bank_amount": str(bk.amount),
            "expected_bank_amount": str(expected_bank) if expected_bank is not None else None,
            "gateway_fee": str(observed_fee) if observed_fee is not None else None,
            "gateway_tax": str(observed_tax) if observed_tax is not None else None,
            "expected_fee": str(expected_fee),
            "expected_tax": str(expected_tax_from_expected_fee),
            "time_span_days": str(time_span_days),
        })

        if observed_fee is None or observed_tax is None:
            if bank_equal_gross:
                return self._base(
                    ExceptionCategory.MISSING_FIELDS_EXCEPTION,
                    Decimal("0.95"),
                    expected_fee + expected_tax_from_expected_fee,
                    "Gateway fee or tax fields are missing, so net settlement cannot be validated.",
                    evidence,
                )

        fee_valid = observed_fee is not None and self._money_equal(observed_fee, expected_fee)
        tax_valid_for_observed_fee = (
            observed_tax is not None
            and observed_fee is not None
            and self._money_equal(observed_tax, expected_tax_from_observed_fee)
        )

        if order_conflict and not gw_ld_equal and not bank_equal_expected:
            return self._base(
                ExceptionCategory.COMPLEX_MISMATCH_EXCEPTION,
                Decimal("0.94"),
                max(abs(gw.amount - ld.amount), abs((expected_bank or gw.amount) - bk.amount)),
                "Shared reference links the records, but order identity and multiple financial dimensions disagree.",
                evidence,
            )

        if observed_fee is not None and observed_tax is not None and not fee_valid and tax_valid_for_observed_fee and bank_equal_expected and gw_ld_equal:
            return self._base(
                ExceptionCategory.FEE_MISMATCH_EXCEPTION,
                Decimal("0.95"),
                abs(observed_fee - expected_fee),
                "Gateway fee differs from the configured fee rule while tax and settlement follow the recorded fee.",
                evidence,
            )

        if observed_fee is not None and observed_tax is not None and fee_valid and not tax_valid_for_observed_fee and bank_equal_expected and gw_ld_equal:
            return self._base(
                ExceptionCategory.TAX_MISMATCH_EXCEPTION,
                Decimal("0.95"),
                abs(observed_tax - expected_tax_from_observed_fee),
                "Gateway tax differs from the configured tax rule while settlement follows the recorded tax.",
                evidence,
            )

        if gw_ld_equal and bank_equal_expected and time_span_days > Decimal(str(SETTLEMENT_WINDOW_DAYS)):
            return self._base(
                ExceptionCategory.DELAYED_SETTLEMENT_EXCEPTION,
                Decimal("0.96"),
                bk.amount,
                "Financial amounts reconcile, but bank settlement is outside the configured settlement window.",
                evidence,
            )

        if not gw_ld_equal and bank_equal_expected:
            return self._base(
                ExceptionCategory.AMOUNT_MISMATCH_EXCEPTION,
                Decimal("0.96"),
                abs(gw.amount - ld.amount),
                "Gateway and ledger amounts disagree for the same transaction identity.",
                evidence,
            )

        if gw_ld_equal and not bank_equal_expected and expected_bank is not None:
            variance = bk.amount - expected_bank
            variance_ratio = abs(variance) / expected_bank if expected_bank > 0 else Decimal("0")
            if variance > 0:
                return self._base(
                    ExceptionCategory.PARTIAL_MATCH_EXCEPTION,
                    Decimal("0.90"),
                    variance,
                    "Gateway and ledger reconcile, but the bank settlement is only a partial financial match.",
                    evidence,
                )
            if variance_ratio >= Decimal("0.15"):
                return self._base(
                    ExceptionCategory.AMOUNT_MISMATCH_EXCEPTION,
                    Decimal("0.92"),
                    abs(variance),
                    "Shared reference has a material bank amount contradiction.",
                    evidence,
                )
            return self._base(
                ExceptionCategory.SETTLEMENT_VARIANCE_EXCEPTION,
                Decimal("0.94"),
                abs(variance),
                "Actual bank settlement differs from expected gateway net settlement.",
                evidence,
            )

        if not gw_ld_equal and not bank_equal_expected:
            return self._base(
                ExceptionCategory.COMPLEX_MISMATCH_EXCEPTION,
                Decimal("0.90"),
                max(abs(gw.amount - ld.amount), abs((expected_bank or gw.amount) - bk.amount)),
                "Multiple financial dimensions disagree for records with shared transaction identity.",
                evidence,
            )

        return None
    
    def classify_candidate_rejection(
        self,
        txn: Transaction,
        candidate: Transaction,
        rejection_reason: str
    ) -> Dict[str, Any]:
        """
        Classify why a candidate was rejected during matching.
        This converts silent "continue" statements into explicit exception classifications.
        """
        classification = {
            "has_exception": True,
            "exception_type": None,
            "exception_category": None,
            "confidence": Decimal("0.90"),
            "financial_exposure": Decimal("0.0"),
            "explanation": "",
            "evidence": {},
        }
        
        if rejection_reason == "same_order_id_different_amount":
            classification["exception_type"] = "amount_mismatch"
            classification["exception_category"] = "amount_mismatch_exception"
            classification["financial_exposure"] = abs(txn.amount - candidate.amount)
            classification["explanation"] = f"Same order_id ({txn.order_id}) but different amounts"
            classification["evidence"]["order_id"] = txn.order_id
            classification["evidence"]["amount_difference"] = str(abs(txn.amount - candidate.amount))
            classification["evidence"]["txn_amount"] = str(txn.amount)
            classification["evidence"]["candidate_amount"] = str(candidate.amount)
            
        elif rejection_reason == "same_reference_different_amount":
            classification["exception_type"] = "amount_mismatch"
            classification["exception_category"] = "amount_mismatch_exception"
            classification["financial_exposure"] = abs(txn.amount - candidate.amount)
            classification["explanation"] = f"Same reference ({txn.reference_number}) but different amounts"
            classification["evidence"]["reference"] = txn.reference_number
            classification["evidence"]["amount_difference"] = str(abs(txn.amount - candidate.amount))
            classification["evidence"]["txn_amount"] = str(txn.amount)
            classification["evidence"]["candidate_amount"] = str(candidate.amount)
            
        else:
            classification["exception_type"] = "unexplained"
            classification["exception_category"] = "unexplained"
            classification["confidence"] = Decimal("0.50")
            classification["explanation"] = f"Candidate rejected: {rejection_reason}"
            classification["evidence"]["rejection_reason"] = rejection_reason
        
        return classification
