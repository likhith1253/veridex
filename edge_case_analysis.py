"""
Detailed Edge Case Analysis
Test specific adversarial scenarios to understand failure modes
"""
import json
import httpx
from decimal import Decimal
from typing import Dict, List, Any


class EdgeCaseAnalyzer:
    """Analyze specific edge cases in detail"""
    
    def __init__(self, ground_truth_file: str = "private_ground_truth.json"):
        with open(ground_truth_file, 'r') as f:
            self.ground_truth = json.load(f)
        
        self.client = httpx.Client(timeout=30.0)
        self.base_url = "http://localhost:8000"
    
    def test_specific_scenarios(self) -> Dict[str, Any]:
        """Test specific adversarial scenarios"""
        
        # Select representative scenarios for detailed analysis
        test_cases = {
            "EVAL_TXN_0000": "exact_match",  # Should match perfectly
            "EVAL_TXN_0003": "missing_optional_fields",  # Should detect missing fields
            "EVAL_TXN_0005": "missing_ledger",  # Should detect missing source
            "EVAL_TXN_0009": "amount_mismatch_gw_bank",  # Should detect settlement variance
            "EVAL_TXN_0012": "duplicate_gateway",  # Should detect duplicate
            "EVAL_TXN_0013": "same_order_diff_amount",  # Should detect amount mismatch
            "EVAL_TXN_0016": "fee_mismatch",  # Should detect fee discrepancy
            "EVAL_TXN_0018": "missing_gateway",  # Should detect missing source
            "EVAL_TXN_0022": "complex_mismatch",  # Should detect complex issues
            "EVAL_TXN_0028": "tax_mismatch",  # Should detect tax discrepancy
            "EVAL_TXN_0032": "partial_match",  # Should detect partial match
            "EVAL_TXN_0036": "duplicate_bank",  # Should detect duplicate
            "EVAL_TXN_0040": "same_ref_diff_amount",  # Should detect ref conflict
            "EVAL_TXN_0049": "false_positive_risk",  # Should avoid false positive
            "EVAL_TXN_0052": "high_value_transaction",  # Should require review
            "EVAL_TXN_0056": "delayed_settlement",  # Should detect delay
        }
        
        results = {}
        
        for logical_id, expected_scenario in test_cases.items():
            ground_truth_record = self.ground_truth[logical_id]
            
            # Try to find this transaction in system results
            try:
                # Search for transactions by identifiers
                gateway_id = ground_truth_record["gateway_id"]
                ledger_id = ground_truth_record["ledger_id"]
                bank_id = ground_truth_record["bank_id"]
                
                # Check if any exceptions reference our IDs
                exceptions = self.client.get(f"{self.base_url}/api/v1/controller/exceptions", params={"page_size": 100}).json()
                system_exceptions = exceptions.get("exceptions", [])
                
                # Look for our transaction in exceptions
                found_in_exceptions = False
                exception_details = None
                for exc in system_exceptions:
                    # Check if exception mentions any of our IDs
                    exc_str = json.dumps(exc)
                    if any(id in exc_str for id in [gateway_id, ledger_id, bank_id, logical_id]):
                        found_in_exceptions = True
                        exception_details = exc
                        break
                
                results[logical_id] = {
                    "expected_scenario": expected_scenario,
                    "expected_outcome": ground_truth_record["expected_outcome"],
                    "gateway_id": gateway_id,
                    "ledger_id": ledger_id,
                    "bank_id": bank_id,
                    "found_in_exceptions": found_in_exceptions,
                    "exception_details": exception_details,
                    "assessment": "CORRECT" if found_in_exceptions and "exception" in ground_truth_record["expected_outcome"] else "INCORRECT" if not found_in_exceptions and "exception" in ground_truth_record["expected_outcome"] else "UNKNOWN",
                }
                
            except Exception as e:
                results[logical_id] = {
                    "error": str(e),
                    "assessment": "ERROR"
                }
        
        return results
    
    def test_data_isolation(self) -> Dict[str, Any]:
        """Test if system isolates batch results properly"""
        
        try:
            # Get current summary
            summary = self.client.get(f"{self.base_url}/api/v1/controller/summary").json()
            
            # Get batch-specific info if available
            runs = self.client.get(f"{self.base_url}/api/v1/runs").json()
            
            isolation_test = {
                "total_records_in_system": summary.get("total_records_processed"),
                "total_logical_transactions": summary.get("total_logical_transactions"),
                "our_batch_size": 296,  # Our adversarial batch had 296 records
                "isolation_issue": summary.get("total_records_processed") > 400,  # Should be close to our batch size
                "available_runs": len(runs.get("runs", [])),
                "assessment": "SYSTEM AGGREGATES ALL DATA - CANNOT ISOLATE BATCH RESULTS" if summary.get("total_records_processed") > 400 else "PROPER ISOLATION"
            }
            
            return isolation_test
            
        except Exception as e:
            return {"error": str(e)}
    
    def test_metrics_consistency(self) -> Dict[str, Any]:
        """Test if metrics are consistent across endpoints"""
        
        try:
            summary = self.client.get(f"{self.base_url}/api/v1/controller/summary").json()
            funnel = self.client.get(f"{self.base_url}/api/v1/controller/funnel").json()
            cash = self.client.get(f"{self.base_url}/api/v1/controller/cash-position").json()
            exceptions = self.client.get(f"{self.base_url}/api/v1/controller/exceptions", params={"page_size": 100}).json()
            
            # Cross-check key metrics
            consistency_checks = {
                "funnel_vs_summary_match_rate": {
                    "funnel_final_match_rate": funnel.get("final_match_rate"),
                    "summary_match_rate": summary.get("match_rate"),
                    "consistent": abs(funnel.get("final_match_rate", 0) - summary.get("match_rate", 0)) < 0.1
                },
                "funnel_vs_summary_unresolved": {
                    "funnel_unresolved": funnel.get("unresolved"),
                    "summary_unresolved": summary.get("unresolved_transactions"),
                    "consistent": funnel.get("unresolved") == summary.get("unresolved_transactions")
                },
                "exception_count_consistency": {
                    "exceptions_from_endpoint": len(exceptions.get("exceptions", [])),
                    "unresolved_from_summary": summary.get("unresolved_transactions"),
                    "consistent": len(exceptions.get("exceptions", [])) <= summary.get("unresolved_transactions", 0)
                },
                "cash_position_match": {
                    "cash_unreconciled": cash.get("unreconciled_amount"),
                    "summary_unresolved_exposure": summary.get("unresolved_monetary_exposure_inr"),
                    "consistent": abs(Decimal(str(cash.get("unreconciled_amount", 0))) - Decimal(str(summary.get("unresolved_monetary_exposure_inr", 0)))) < Decimal("1.0")
                }
            }
            
            overall_consistency = all(check.get("consistent", False) for check in consistency_checks.values())
            
            return {
                "overall_consistent": overall_consistency,
                "consistency_checks": consistency_checks,
                "assessment": "METRICS CONSISTENT" if overall_consistency else "METRICS INCONSISTENT"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def test_malformed_input(self) -> Dict[str, Any]:
        """Test system handling of malformed inputs"""
        
        test_cases = [
            {
                "name": "empty_records",
                "gateway_records": [],
                "ledger_records": [],
                "bank_records": [],
                "should_fail": False  # Empty should be handled gracefully
            },
            {
                "name": "missing_required_fields",
                "gateway_records": [{"txn_id": "test"}],  # Missing amount, currency, etc.
                "ledger_records": [],
                "bank_records": [],
                "should_fail": True  # Should reject or handle gracefully
            },
            {
                "name": "invalid_amount",
                "gateway_records": [{"txn_id": "test", "amount": "invalid", "currency": "INR"}],
                "ledger_records": [],
                "bank_records": [],
                "should_fail": True
            },
            {
                "name": "negative_amount",
                "gateway_records": [{"txn_id": "test", "amount": -100, "currency": "INR"}],
                "ledger_records": [],
                "bank_records": [],
                "should_fail": True
            },
        ]
        
        results = {}
        
        for test_case in test_cases:
            try:
                response = self.client.post(
                    f"{self.base_url}/api/v1/controller/ingest/batch",
                    json={
                        "gateway_records": test_case["gateway_records"],
                        "ledger_records": test_case["ledger_records"],
                        "bank_records": test_case["bank_records"],
                        "batch_id": f"test_{test_case['name']}",
                    }
                )
                
                results[test_case["name"]] = {
                    "status_code": response.status_code,
                    "response": response.json(),
                    "expected_failure": test_case["should_fail"],
                    "actually_failed": response.status_code >= 400,
                    "handled_correctly": (response.status_code >= 400) == test_case["should_fail"]
                }
                
            except Exception as e:
                results[test_case["name"]] = {
                    "error": str(e),
                    "expected_failure": test_case["should_fail"],
                    "handled_correctly": True  # Exception is OK for expected failures
                }
        
        return results


def main():
    """Run edge case analysis"""
    print("Running Edge Case Analysis")
    print("=" * 60)
    
    analyzer = EdgeCaseAnalyzer()
    
    # 1. Test specific scenarios
    print("\n1. SPECIFIC SCENARIO TESTING")
    scenario_results = analyzer.test_specific_scenarios()
    print(json.dumps(scenario_results, indent=2))
    
    # 2. Test data isolation
    print("\n2. DATA ISOLATION TESTING")
    isolation = analyzer.test_data_isolation()
    print(json.dumps(isolation, indent=2))
    
    # 3. Test metrics consistency
    print("\n3. METRICS CONSISTENCY TESTING")
    consistency = analyzer.test_metrics_consistency()
    print(json.dumps(consistency, indent=2))
    
    # 4. Test malformed input handling
    print("\n4. MALFORMED INPUT TESTING")
    malformed = analyzer.test_malformed_input()
    print(json.dumps(malformed, indent=2))
    
    # Save complete analysis
    complete_analysis = {
        "scenario_testing": scenario_results,
        "data_isolation": isolation,
        "metrics_consistency": consistency,
        "malformed_input_handling": malformed,
    }
    
    with open("edge_case_analysis_results.json", "w") as f:
        json.dump(complete_analysis, f, indent=2)
    
    print("\nEdge case analysis saved to edge_case_analysis_results.json")


if __name__ == "__main__":
    main()
