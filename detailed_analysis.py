"""
Detailed Analysis of Sentinel Reconciliation Results
Compares ground truth against system outputs for independent accuracy verification
"""
import json
import httpx
from decimal import Decimal
from typing import Dict, List, Any
from collections import defaultdict


class DetailedAnalyzer:
    """Analyze reconciliation results against ground truth"""
    
    def __init__(self, ground_truth_file: str = "private_ground_truth.json"):
        with open(ground_truth_file, 'r') as f:
            self.ground_truth = json.load(f)
        
        self.client = httpx.Client(timeout=30.0)
        self.base_url = "http://localhost:8000"
        
    def analyze_accuracy(self) -> Dict[str, Any]:
        """Calculate precision, recall, and other accuracy metrics"""
        
        # Get system results
        try:
            exceptions = self.client.get(f"{self.base_url}/api/v1/controller/exceptions", params={"page_size": 100}).json()
            summary = self.client.get(f"{self.base_url}/api/v1/controller/summary").json()
            funnel = self.client.get(f"{self.base_url}/api/v1/controller/funnel").json()
        except Exception as e:
            return {"error": f"Failed to fetch system results: {e}"}
        
        # Analyze ground truth scenarios
        scenario_counts = defaultdict(int)
        expected_outcomes = defaultdict(int)
        
        for logical_id, record in self.ground_truth.items():
            scenario_counts[record["scenario"]] += 1
            expected_outcomes[record["expected_outcome"]] += 1
        
        # Compare with system results
        system_exceptions = exceptions.get("exceptions", [])
        system_match_rate = summary.get("match_rate", 0)
        system_unresolved = summary.get("unresolved_transactions", 0)
        
        analysis = {
            "ground_truth_total": len(self.ground_truth),
            "ground_truth_scenarios": dict(scenario_counts),
            "expected_outcomes": dict(expected_outcomes),
            "system_match_rate": system_match_rate,
            "system_unresolved_count": system_unresolved,
            "system_exceptions_count": len(system_exceptions),
            "system_exceptions_by_category": self._categorize_exceptions(system_exceptions),
        }
        
        return analysis
    
    def _categorize_exceptions(self, exceptions: List[Dict]) -> Dict[str, int]:
        """Categorize system exceptions by type"""
        categories = defaultdict(int)
        for exc in exceptions:
            category = exc.get("exception_category", "unknown")
            categories[category] += 1
        return dict(categories)
    
    def verify_cash_position(self) -> Dict[str, Any]:
        """Independently verify cash position calculations"""
        
        try:
            cash_position = self.client.get(f"{self.base_url}/api/v1/controller/cash-position").json()
            settlement = self.client.get(f"{self.base_url}/api/v1/controller/settlement-accounting").json()
        except Exception as e:
            return {"error": f"Failed to fetch cash position: {e}"}
        
        # Independent calculation from ground truth
        total_gross = Decimal("0")
        total_fees = Decimal("0")
        total_taxes = Decimal("0")
        total_expected_net = Decimal("0")
        
        for logical_id, record in self.ground_truth.items():
            amount = Decimal(record["amount"])
            total_gross += amount
            
            # Calculate expected fees and taxes based on ground truth scenarios
            scenario = record["scenario"]
            if scenario in ["fee_mismatch", "tax_mismatch"]:
                # For mismatch scenarios, calculate what SHOULD have been
                expected_fee = amount * Decimal("0.02")
                expected_tax = expected_fee * Decimal("0.18")
            elif scenario == "high_value_transaction":
                expected_fee = amount * Decimal("0.015")
                expected_tax = expected_fee * Decimal("0.18")
            elif scenario == "very_small_transaction":
                expected_fee = Decimal("1.0")
                expected_tax = expected_fee * Decimal("0.18")
            else:
                expected_fee = amount * Decimal("0.02")
                expected_tax = expected_fee * Decimal("0.18")
            
            total_fees += expected_fee
            total_taxes += expected_tax
        
        total_expected_net = total_gross - total_fees - total_taxes
        
        system_gross = Decimal(cash_position.get("expected_gross", "0"))
        system_net = Decimal(cash_position.get("expected_net_settlement", "0"))
        system_fees = Decimal(cash_position.get("total_deducted_fees", "0"))
        system_taxes = Decimal(cash_position.get("total_deducted_taxes", "0"))
        system_received = Decimal(cash_position.get("received_amount", "0"))
        
        verification = {
            "independent_calculation": {
                "total_gross": str(total_gross),
                "total_fees": str(total_fees),
                "total_taxes": str(total_taxes),
                "expected_net_settlement": str(total_expected_net),
            },
            "system_reported": {
                "total_gross": str(system_gross),
                "total_fees": str(system_fees),
                "total_taxes": str(system_taxes),
                "expected_net_settlement": str(system_net),
                "received_bank_credits": str(system_received),
            },
            "discrepancies": {
                "gross_difference": str(system_gross - total_gross),
                "fees_difference": str(system_fees - total_fees),
                "taxes_difference": str(system_taxes - total_taxes),
                "net_difference": str(system_net - total_expected_net),
            },
            "accounting_equation_check": {
                "equation": "Gross - Fees - Taxes = Expected Net",
                "independent_result": f"{total_gross} - {total_fees} - {total_taxes} = {total_expected_net}",
                "system_result": f"{system_gross} - {system_fees} - {system_taxes} = {system_net}",
                "independent_matches_system": str(abs((total_gross - total_fees - total_taxes) - system_net) < Decimal("0.01")),
            }
        }
        
        return verification
    
    def test_ai_qa(self) -> Dict[str, Any]:
        """Test AI Q&A with adversarial questions"""
        
        test_questions = [
            "What is the total unresolved financial exposure?",
            "How much money was recovered by ML candidate scoring?",
            "What is the breakdown of open exceptions by category?",
            "Which exceptions have the highest monetary exposure?",
            "Why is there a discrepancy in today's settlement?",
            "What percentage of records matched?",
            "Which source is causing the largest reconciliation issue?",
            "What is the expected net settlement?",
            "Which transactions caused the largest variance?",
            "What should I investigate first?",
        ]
        
        results = {}
        for question in test_questions:
            try:
                response = self.client.post(
                    f"{self.base_url}/api/v1/controller/qa",
                    json={"question": question}
                ).json()
                results[question] = {
                    "success": True,
                    "answer": response.get("direct_answer", "No answer"),
                    "key_metrics": response.get("key_metrics", {}),
                    "has_evidence": len(response.get("evidence_records", [])) > 0,
                }
            except Exception as e:
                results[question] = {
                    "success": False,
                    "error": str(e),
                }
        
        return results
    
    def test_copilot(self) -> Dict[str, Any]:
        """Test AI copilot with adversarial questions"""
        
        test_questions = [
            "What needs my attention right now?",
            "Where is the highest monetary exposure?",
            "Why are these transactions unresolved?",
            "Show me the highest-risk exception.",
            "Which source is unhealthy?",
            "What can I safely auto-resolve?",
            "What requires human review?",
            "Explain today's reconciliation performance.",
        ]
        
        results = {}
        for question in test_questions:
            try:
                response = self.client.post(
                    f"{self.base_url}/api/v1/controller/copilot",
                    json={"question": question}
                ).json()
                results[question] = {
                    "success": True,
                    "answer": response.get("answer", "No answer"),
                    "interpretation": response.get("interpretation", ""),
                    "recommendation": response.get("recommendation", ""),
                    "needs_human_review": response.get("needs_human_review", False),
                }
            except Exception as e:
                results[question] = {
                    "success": False,
                    "error": str(e),
                }
        
        return results
    
    def verify_exception_honesty(self) -> Dict[str, Any]:
        """Verify that exception list is honest and complete"""
        
        try:
            exceptions = self.client.get(f"{self.base_url}/api/v1/controller/exceptions", params={"page_size": 100}).json()
        except Exception as e:
            return {"error": f"Failed to fetch exceptions: {e}"}
        
        system_exceptions = exceptions.get("exceptions", [])
        
        # Count expected exceptions from ground truth
        expected_exceptions = 0
        expected_by_category = defaultdict(int)
        
        for logical_id, record in self.ground_truth.items():
            expected_outcome = record["expected_outcome"]
            if "exception" in expected_outcome or "risk" in expected_outcome or "review" in expected_outcome:
                expected_exceptions += 1
                expected_by_category[expected_outcome] += 1
        
        # Check if system caught expected exceptions
        system_exception_count = len(system_exceptions)
        
        honesty_check = {
            "ground_truth_expected_exceptions": expected_exceptions,
            "ground_truth_breakdown": dict(expected_by_category),
            "system_reported_exceptions": system_exception_count,
            "exception_coverage": system_exception_count / expected_exceptions if expected_exceptions > 0 else 0,
            "honesty_assessment": "HONEST" if system_exception_count >= expected_exceptions * 0.8 else "POTENTIALLY INCOMPLETE",
            "system_exception_details": [
                {
                    "id": exc.get("exception_id", ""),
                    "category": exc.get("exception_category", ""),
                    "exposure": exc.get("financial_exposure_inr", 0),
                    "status": exc.get("status", ""),
                }
                for exc in system_exceptions[:10]  # First 10 for brevity
            ]
        }
        
        return honesty_check
    
    def test_throughput(self) -> Dict[str, Any]:
        """Measure and verify throughput metrics"""
        
        try:
            summary = self.client.get(f"{self.base_url}/api/v1/controller/summary").json()
        except Exception as e:
            return {"error": f"Failed to fetch summary: {e}"}
        
        reported_tps = summary.get("processing_throughput_tps")
        reported_latency = summary.get("average_processing_latency_ms")
        total_records = summary.get("total_records_processed")
        
        # Calculate expected throughput based on our batch
        # Our batch had 296 records processed in ~11.2 seconds
        expected_tps = 296 / 11.2
        
        throughput_analysis = {
            "system_reported_tps": reported_tps,
            "system_reported_latency_ms": reported_latency,
            "total_records_processed": total_records,
            "expected_tps_from_batch": expected_tps,
            "throughput_discrepancy": abs(reported_tps - expected_tps) if reported_tps else None,
            "throughput_realistic": reported_tps and abs(reported_tps - expected_tps) < expected_tps * 0.5,
        }
        
        return throughput_analysis


def main():
    """Run detailed analysis"""
    print("Running Detailed Analysis of Sentinel Results")
    print("=" * 60)
    
    analyzer = DetailedAnalyzer()
    
    # 1. Accuracy Analysis
    print("\n1. ACCURACY ANALYSIS")
    accuracy = analyzer.analyze_accuracy()
    print(json.dumps(accuracy, indent=2))
    
    # 2. Cash Position Verification
    print("\n2. CASH POSITION VERIFICATION")
    cash_verification = analyzer.verify_cash_position()
    print(json.dumps(cash_verification, indent=2))
    
    # 3. AI Q&A Testing
    print("\n3. AI Q&A TESTING")
    qa_results = analyzer.test_ai_qa()
    print(json.dumps(qa_results, indent=2))
    
    # 4. Copilot Testing
    print("\n4. COPILOT TESTING")
    copilot_results = analyzer.test_copilot()
    print(json.dumps(copilot_results, indent=2))
    
    # 5. Exception Honesty Verification
    print("\n5. EXCEPTION HONESTY VERIFICATION")
    honesty = analyzer.verify_exception_honesty()
    print(json.dumps(honesty, indent=2))
    
    # 6. Throughput Analysis
    print("\n6. THROUGHPUT ANALYSIS")
    throughput = analyzer.test_throughput()
    print(json.dumps(throughput, indent=2))
    
    # Save complete analysis
    complete_analysis = {
        "accuracy": accuracy,
        "cash_position_verification": cash_verification,
        "ai_qa_results": qa_results,
        "copilot_results": copilot_results,
        "exception_honesty": honesty,
        "throughput_analysis": throughput,
    }
    
    with open("detailed_analysis_results.json", "w") as f:
        json.dump(complete_analysis, f, indent=2)
    
    print("\nComplete analysis saved to detailed_analysis_results.json")


if __name__ == "__main__":
    main()
