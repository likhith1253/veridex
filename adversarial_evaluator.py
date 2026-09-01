"""
Independent Adversarial Razorpay Evaluator
Creates comprehensive test datasets with private ground truth for evaluation
"""
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import httpx
import asyncio


class AdversarialDatasetGenerator:
    """Generate adversarial test datasets with private ground truth"""
    
    def __init__(self, seed: int = 99999):
        random.seed(seed)
        self.seed = seed
        self.ground_truth = {}  # Private ground truth for evaluation
        self.gateway_records = []
        self.ledger_records = []
        self.bank_records = []
        
    def generate_comprehensive_dataset(self, num_records: int = 100) -> Tuple[List, List, List, Dict]:
        """Generate 100+ record dataset with comprehensive edge cases"""
        
        # Scenario distribution for adversarial testing
        scenarios = [
            # 40% normal exact matches
            *["exact_match"] * 40,
            # 10% amount mismatches (gateway vs ledger vs bank)
            *["amount_mismatch_gw_ledger"] * 5,
            *["amount_mismatch_gw_bank"] * 5,
            # 10% missing source records
            *["missing_ledger"] * 4,
            *["missing_gateway"] * 3,
            *["missing_bank"] * 3,
            # 8% duplicate records
            *["duplicate_gateway"] * 3,
            *["duplicate_bank"] * 3,
            *["duplicate_ledger"] * 2,
            # 7% identifier conflicts
            *["same_order_diff_amount"] * 3,
            *["same_ref_diff_amount"] * 2,
            *["repeated_identifiers"] * 2,
            # 5% fee/tax discrepancies
            *["fee_mismatch"] * 3,
            *["tax_mismatch"] * 2,
            # 5% timing issues
            *["delayed_settlement"] * 3,
            *["cross_date_boundary"] * 2,
            # 5% edge cases
            *["high_value_transaction"] * 2,
            *["very_small_transaction"] * 2,
            *["rounding_edge_case"] * 1,
            # 5% partial/complex scenarios
            *["partial_match"] * 3,
            *["complex_mismatch"] * 2,
            # 5% adversarial scenarios
            *["false_positive_risk"] * 2,
            *["missing_optional_fields"] * 2,
            *["near_duplicate_amounts"] * 1,
        ]
        
        # Ensure we have exactly num_records
        scenarios = scenarios[:num_records]
        while len(scenarios) < num_records:
            scenarios.append("exact_match")
            
        random.shuffle(scenarios)
        
        base_date = datetime.now(timezone.utc)
        
        for i, scenario in enumerate(scenarios):
            logical_id = f"EVAL_TXN_{i:04d}"
            gateway_id = f"EVAL_GW_{i:04d}"
            ledger_id = f"EVAL_LD_{i:04d}"
            bank_id = f"EVAL_BK_{i:04d}"
            
            # Generate amount with adversarial distribution
            if scenario == "high_value_transaction":
                amount = Decimal(str(random.randint(100000, 500000)))
            elif scenario == "very_small_transaction":
                amount = Decimal(str(random.randint(1, 100)))
            else:
                amount = Decimal(str(random.randint(500, 50000)))
            
            # Generate timestamp with variations
            if scenario == "delayed_settlement":
                days_offset = random.randint(5, 15)
            elif scenario == "cross_date_boundary":
                days_offset = random.randint(-1, 1)
            else:
                days_offset = random.randint(0, 3)
                
            timestamp = base_date - timedelta(days=days_offset, hours=random.randint(0, 23))
            
            gateway, ledger, bank, expected_outcome = self._generate_scenario(
                scenario, logical_id, gateway_id, ledger_id, bank_id, amount, timestamp
            )
            
            # Store private ground truth
            self.ground_truth[logical_id] = {
                "logical_id": logical_id,
                "scenario": scenario,
                "gateway_id": gateway_id,
                "ledger_id": ledger_id,
                "bank_id": bank_id,
                "expected_outcome": expected_outcome,
                "amount": str(amount),
                "timestamp": timestamp.isoformat(),
            }
            
            if gateway:
                self.gateway_records.append(gateway)
            if ledger:
                self.ledger_records.append(ledger)
            if bank:
                self.bank_records.append(bank)
        
        return self.gateway_records, self.ledger_records, self.bank_records, self.ground_truth
    
    def _generate_scenario(self, scenario: str, logical_id: str, gateway_id: str, 
                           ledger_id: str, bank_id: str, amount: Decimal, 
                           timestamp: datetime) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict], str]:
        """Generate specific adversarial scenario"""
        
        utr = f"UTR_{random.randint(100000, 999999)}"
        order_id = f"ORD_{random.randint(10000, 99999)}"
        
        gateway = None
        ledger = None  
        bank = None
        expected_outcome = "exact_match"
        
        if scenario == "exact_match":
            # Perfect three-way match
            fee = amount * Decimal("0.02")  # 2% fee
            tax = fee * Decimal("0.18")  # 18% GST on fee
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "exact_match"
            
        elif scenario == "amount_mismatch_gw_ledger":
            # Gateway and ledger have different amounts
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            ledger_amount = amount * Decimal("1.01")  # 1% higher in ledger
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(ledger_amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "amount_mismatch_exception"
            
        elif scenario == "amount_mismatch_gw_bank":
            # Gateway and bank have different amounts
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            expected_net = amount - fee - tax
            actual_net = max(expected_net * Decimal("0.95"), Decimal("1.00"))  # Bank received 5% less, ensure positive
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(actual_net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "settlement_variance_exception"
            
        elif scenario == "missing_ledger":
            # No ledger record
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "missing_source_exception"
            
        elif scenario == "missing_gateway":
            # No gateway record
            bank = {
                "txn_id": bank_id,
                "amount": float(max(amount, Decimal("1.00"))),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(max(amount, Decimal("1.00"))),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            expected_outcome = "missing_source_exception"
            
        elif scenario == "missing_bank":
            # No bank record
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            expected_outcome = "missing_source_exception"
            
        elif scenario == "duplicate_gateway":
            # Two gateway records for same logical transaction
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            # First gateway record
            gateway1 = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            # Duplicate gateway record (same order_id, different settlement_id)
            gateway2 = {
                "txn_id": f"{gateway_id}_DUP",
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,  # Same order_id
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            
            self.gateway_records.append(gateway1)
            self.gateway_records.append(gateway2)
            
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "duplicate_exception"
            gateway = None  # Already added
            
        elif scenario == "duplicate_bank":
            # Two bank records for same UTR
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            # Duplicate bank records
            bank1 = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            bank2 = {
                "txn_id": f"{bank_id}_DUP",
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,  # Same UTR
                "narration": f"Settlement for {utr}",
            }
            
            self.bank_records.append(bank1)
            self.bank_records.append(bank2)
            expected_outcome = "duplicate_exception"
            bank = None  # Already added
            
        elif scenario == "same_order_diff_amount":
            # Same order_id but different amounts (gateway vs ledger)
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            ledger_amount = amount * Decimal("1.5")  # 50% higher in ledger
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(ledger_amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,  # Same order_id
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "amount_mismatch_exception"
            
        elif scenario == "same_ref_diff_amount":
            # Same reference number but different amounts
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            bank_amount = net * Decimal("0.8")  # Bank shows 20% less
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(bank_amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,  # Same UTR but different amount
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "amount_mismatch_exception"
            
        elif scenario == "fee_mismatch":
            # Fee calculation discrepancy
            correct_fee = amount * Decimal("0.02")
            wrong_fee = amount * Decimal("0.025")  # 2.5% instead of 2%
            tax = wrong_fee * Decimal("0.18")
            net = amount - wrong_fee - tax
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(wrong_fee),  # Wrong fee
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "fee_mismatch_exception"
            
        elif scenario == "tax_mismatch":
            # Tax calculation discrepancy
            fee = amount * Decimal("0.02")
            correct_tax = fee * Decimal("0.18")
            wrong_tax = fee * Decimal("0.20")  # 20% instead of 18%
            net = amount - fee - wrong_tax
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(wrong_tax),  # Wrong tax
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "tax_mismatch_exception"
            
        elif scenario == "delayed_settlement":
            # Settlement delayed beyond normal window
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            delayed_timestamp = timestamp + timedelta(days=7)
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": delayed_timestamp.isoformat(),  # Delayed
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "delayed_settlement_exception"
            
        elif scenario == "high_value_transaction":
            # Large transaction that should not be auto-matched
            fee = amount * Decimal("0.015")  # Lower fee for high value
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "high_value_review_required"
            
        elif scenario == "very_small_transaction":
            # Very small amount to test rounding
            fee = Decimal("1.0")  # Fixed minimum fee
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "rounding_edge_case"
            
        elif scenario == "rounding_edge_case":
            # Amount that creates rounding issues
            amount = Decimal("1000.01")
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "exact_match"
            
        elif scenario == "partial_match":
            # Only two sources match, third differs
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            bank_amount = net * Decimal("1.1")  # Bank shows 10% more
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(bank_amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "partial_match_exception"
            
        elif scenario == "complex_mismatch":
            # Multiple fields mismatch
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount * Decimal("1.02")),  # 2% higher
                "currency": "INR",
                "timestamp": (timestamp + timedelta(hours=1)).isoformat(),  # Different time
                "order_id": f"{order_id}X",  # Different order_id
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net * Decimal("0.98")),  # 2% lower
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "complex_mismatch_exception"
            
        elif scenario == "false_positive_risk":
            # Two different transactions with very similar amounts that could be falsely matched
            amount1 = amount
            amount2 = amount * Decimal("1.001")  # 0.1% difference
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount1),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(amount1 * Decimal("0.02")),
                "tax": float(amount1 * Decimal("0.02") * Decimal("0.18")),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount2),  # Slightly different
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(amount1 - (amount1 * Decimal("0.02") * Decimal("1.18"))),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "false_positive_risk"
            
        elif scenario == "missing_optional_fields":
            # Valid transaction but missing optional fields
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                # Missing fee and tax
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(amount),  # Bank shows gross instead of net
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "missing_fields_exception"
            
        elif scenario == "near_duplicate_amounts":
            # Multiple transactions with similar amounts to test collision detection
            base_amount = amount
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(base_amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(base_amount * Decimal("0.02")),
                "tax": float(base_amount * Decimal("0.02") * Decimal("0.18")),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(base_amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(base_amount - (base_amount * Decimal("0.02") * Decimal("1.18"))),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "exact_match"
            
        else:
            # Default to exact match for unknown scenarios
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = max(amount - fee - tax, Decimal("1.00"))
            
            gateway = {
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            }
            ledger = {
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            }
            bank = {
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            }
            expected_outcome = "exact_match"
        
        return gateway, ledger, bank, expected_outcome


class RazorpayAPIEvaluator:
    """Evaluate the Sentinel system through its API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)
        
    def ingest_batch(self, gateway_records: List[Dict], ledger_records: List[Dict], 
                     bank_records: List[Dict], batch_id: str) -> Dict:
        """Ingest a batch of records through the API"""
        response = self.client.post(
            f"{self.base_url}/api/v1/controller/ingest/batch",
            json={
                "gateway_records": gateway_records,
                "ledger_records": ledger_records,
                "bank_records": bank_records,
                "batch_id": batch_id,
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_summary(self) -> Dict:
        """Get executive summary"""
        response = self.client.get(f"{self.base_url}/api/v1/controller/summary")
        response.raise_for_status()
        return response.json()
    
    def get_funnel(self) -> Dict:
        """Get reconciliation funnel"""
        response = self.client.get(f"{self.base_url}/api/v1/controller/funnel")
        response.raise_for_status()
        return response.json()
    
    def get_exceptions(self, status: str = None, category: str = None, 
                       min_exposure: float = None, page: int = 1, page_size: int = 100) -> Dict:
        """Get exceptions with filters"""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if category:
            params["category"] = category
        if min_exposure:
            params["min_exposure"] = min_exposure
            
        response = self.client.get(f"{self.base_url}/api/v1/controller/exceptions", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_cash_position(self) -> Dict:
        """Get cash position"""
        response = self.client.get(f"{self.base_url}/api/v1/controller/cash-position")
        response.raise_for_status()
        return response.json()
    
    def get_settlement_accounting(self) -> Dict:
        """Get settlement accounting"""
        response = self.client.get(f"{self.base_url}/api/v1/controller/settlement-accounting")
        response.raise_for_status()
        return response.json()
    
    def ask_qa(self, question: str) -> Dict:
        """Ask finance QA question"""
        response = self.client.post(
            f"{self.base_url}/api/v1/controller/qa",
            json={"question": question}
        )
        response.raise_for_status()
        return response.json()
    
    def ask_copilot(self, question: str) -> Dict:
        """Ask copilot question"""
        response = self.client.post(
            f"{self.base_url}/api/v1/controller/copilot",
            json={"question": question}
        )
        response.raise_for_status()
        return response.json()


def main():
    """Main evaluation workflow"""
    print("Starting Independent Razorpay Adversarial Evaluation")
    print("=" * 60)
    
    # Step 1: Generate comprehensive adversarial dataset
    print("\nStep 1: Generating 100+ record adversarial dataset...")
    generator = AdversarialDatasetGenerator(seed=88888)
    gateway_records, ledger_records, bank_records, ground_truth = generator.generate_comprehensive_dataset(num_records=100)
    
    print(f"   Generated {len(gateway_records)} gateway records")
    print(f"   Generated {len(ledger_records)} ledger records")
    print(f"   Generated {len(bank_records)} bank records")
    print(f"   Ground truth scenarios: {len(ground_truth)}")
    
    # Save ground truth privately
    with open("private_ground_truth.json", "w") as f:
        json.dump(ground_truth, f, indent=2)
    print("   Private ground truth saved")
    
    # Step 2: Ingest through API
    print("\nStep 2: Ingesting dataset through API...")
    evaluator = RazorpayAPIEvaluator()
    
    try:
        batch_id = f"adversarial_eval_{random.randint(1000, 9999)}"
        result = evaluator.ingest_batch(gateway_records, ledger_records, bank_records, batch_id)
        print(f"   Batch ingested successfully: {batch_id}")
        print(f"   Response: {result}")
    except Exception as e:
        print(f"   Ingestion failed: {e}")
        return
    
    # Step 3: Query results
    print("\nStep 3: Querying reconciliation results...")
    
    try:
        summary = evaluator.get_summary()
        print(f"   Summary: {summary}")
    except Exception as e:
        print(f"   Failed to get summary: {e}")
    
    try:
        funnel = evaluator.get_funnel()
        print(f"   Funnel: {funnel}")
    except Exception as e:
        print(f"   Failed to get funnel: {e}")
    
    try:
        exceptions = evaluator.get_exceptions(page_size=100)
        print(f"   Exceptions: {len(exceptions.get('exceptions', []))} found")
    except Exception as e:
        print(f"   Failed to get exceptions: {e}")
    
    try:
        cash_position = evaluator.get_cash_position()
        print(f"   Cash Position: {cash_position}")
    except Exception as e:
        print(f"   Failed to get cash position: {e}")
    
    print("\nInitial data collection complete. Proceeding to detailed analysis...")


if __name__ == "__main__":
    main()
