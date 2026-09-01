"""
Exception Classification Module
Separates matching from exception classification to properly categorize financial discrepancies
"""
from decimal import Decimal
from typing import Dict, List, Optional, Any
from app.models.transaction import Transaction
from app.matching.financial_utils import calculate_expected_bank_amount


class ExceptionClassifier:
    """Classifies financial discrepancies into specific exception categories"""
    
    def classify_transaction_group(
        self, 
        transactions: List[Transaction],
        match_evidence: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Classify a group of transactions that have been matched/associated but may have financial discrepancies.
        
        Returns exception classification if discrepancies exist, None if financially consistent.
        """
        if not transactions or len(transactions) < 2:
            return None
        
        # Separate by source
        gateway_txns = [t for t in transactions if t.source.value == "gateway"]
        ledger_txns = [t for t in transactions if t.source.value == "ledger"]
        bank_txns = [t for t in transactions if t.source.value == "bank"]
        
        classification = {
            "has_exception": False,
            "exception_type": None,
            "exception_category": None,
            "confidence": Decimal("0.0"),
            "financial_exposure": Decimal("0.0"),
            "explanation": "",
            "evidence": {},
        }
        
        # Check 1: Missing source records
        missing_sources = []
        if not gateway_txns:
            missing_sources.append("gateway")
        if not ledger_txns:
            missing_sources.append("ledger")
        if not bank_txns:
            missing_sources.append("bank")
        
        if missing_sources:
            classification["has_exception"] = True
            classification["exception_type"] = "missing_source"
            classification["exception_category"] = "missing_source_exception"
            classification["confidence"] = Decimal("0.95")
            classification["explanation"] = f"Missing source records: {', '.join(missing_sources)}"
            classification["evidence"]["missing_sources"] = missing_sources
            return classification
        
        # Check 2: Amount mismatches
        if gateway_txns and ledger_txns:
            gw_amount = gateway_txns[0].amount
            ld_amount = ledger_txns[0].amount
            if gw_amount != ld_amount:
                classification["has_exception"] = True
                classification["exception_type"] = "amount_mismatch"
                classification["exception_category"] = "amount_mismatch_exception"
                classification["confidence"] = Decimal("0.90")
                classification["financial_exposure"] = abs(gw_amount - ld_amount)
                classification["explanation"] = f"Gateway amount ({gw_amount}) differs from ledger amount ({ld_amount})"
                classification["evidence"]["gateway_amount"] = str(gw_amount)
                classification["evidence"]["ledger_amount"] = str(ld_amount)
                classification["evidence"]["amount_difference"] = str(abs(gw_amount - ld_amount))
                return classification
        
        # Check 3: Settlement variance (gateway vs bank)
        if gateway_txns and bank_txns:
            gw_txn = gateway_txns[0]
            bank_txn = bank_txns[0]
            expected_bank = calculate_expected_bank_amount(gw_txn)
            
            if expected_bank and bank_txn.amount != expected_bank:
                classification["has_exception"] = True
                classification["exception_type"] = "settlement_variance"
                classification["exception_category"] = "settlement_variance_exception"
                classification["confidence"] = Decimal("0.85")
                classification["financial_exposure"] = abs(bank_txn.amount - expected_bank)
                classification["explanation"] = f"Bank amount ({bank_txn.amount}) differs from expected ({expected_bank})"
                classification["evidence"]["gateway_amount"] = str(gw_txn.amount)
                classification["evidence"]["expected_bank"] = str(expected_bank)
                classification["evidence"]["actual_bank"] = str(bank_txn.amount)
                classification["evidence"]["variance"] = str(abs(bank_txn.amount - expected_bank))
                return classification
        
        # Check 4: Fee/tax discrepancies
        if gateway_txns and match_evidence:
            if "fee" in match_evidence or "tax" in match_evidence:
                # Check if fee/tax are unusually high or inconsistent
                gw_txn = gateway_txns[0]
                if gw_txn.fee and gw_txn.amount > 0:
                    fee_ratio = gw_txn.fee / gw_txn.amount
                    if fee_ratio > Decimal("0.03"):  # More than 3% fee
                        classification["has_exception"] = True
                        classification["exception_type"] = "fee_mismatch"
                        classification["exception_category"] = "fee_mismatch_exception"
                        classification["confidence"] = Decimal("0.80")
                        classification["financial_exposure"] = gw_txn.fee - (gw_txn.amount * Decimal("0.02"))
                        classification["explanation"] = f"Unusually high fee: {fee_ratio:.2%} of gross amount"
                        classification["evidence"]["fee"] = str(gw_txn.fee)
                        classification["evidence"]["fee_ratio"] = str(fee_ratio)
                        return classification
        
        # No financial discrepancies found
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
