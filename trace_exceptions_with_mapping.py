"""
Project Sentinel - Canonical Scenario-by-Scenario Trace Mapping Tool.
Traces active run exceptions against canonical ground truth and verifies scenario-level correctness.
"""

import asyncio
import httpx
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from eval.benchmark_registry import validate_ground_truth_namespace

# Load and validate canonical ground truth
with open(ROOT_DIR / 'private_ground_truth.json', 'r', encoding='utf-8') as f:
    ground_truth = validate_ground_truth_namespace(json.load(f))


async def resolve_run_id(client: httpx.AsyncClient) -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    response = await client.get("http://127.0.0.1:8000/runs")
    if response.status_code == 200:
        runs = response.json().get("runs", [])
        if runs:
            return runs[0].get("run_id") or runs[0].get("id")
    return "adversarial_eval_latest"


async def get_current_exceptions(client: httpx.AsyncClient, run_id: str):
    response = await client.get(
        "http://127.0.0.1:8000/api/v1/controller/exceptions",
        params={"run_id": run_id, "page_size": 200}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("exceptions", [])
    print(f"Exception API failed: {response.status_code} {response.text}")
    return []


async def get_transaction_mapping(client: httpx.AsyncClient, run_id: str):
    """Get mapping between domain transaction IDs and ORM UUIDs."""
    response = await client.get(
        "http://127.0.0.1:8000/api/v1/controller/transactions",
        params={"run_id": run_id, "limit": 500}
    )
    if response.status_code == 200:
        data = response.json()
        transactions = data.get("transactions", [])
        mapping = {}
        for txn in transactions:
            d_id = txn.get('domain_transaction_id') or txn.get('txn_id')
            o_id = txn.get('id')
            if d_id and o_id:
                mapping[d_id] = o_id
        return mapping
    print(f"Transaction API failed: {response.status_code} {response.text}")
    return {}


async def main():
    async with httpx.AsyncClient() as client:
        run_id = await resolve_run_id(client)
        exceptions = await get_current_exceptions(client, run_id)
        txn_mapping = await get_transaction_mapping(client, run_id)
    
    print(f"Run ID: {run_id}")
    print(f"Current exceptions: {len(exceptions)}")
    print(f"Transaction mapping: {len(txn_mapping)} physical entries")
    
    # Build inverted mapping: ORM UUID -> domain_transaction_id
    orm_to_domain = {v: k for k, v in txn_mapping.items()}
    
    # Group exceptions by domain transaction ID
    domain_to_excs = defaultdict(list)
    for exc in exceptions:
        t_id = exc.get("transaction_id")
        domain_id = orm_to_domain.get(t_id, "UNKNOWN")
        domain_to_excs[domain_id].append(exc)
        
    print("\n=== SCENARIO-BY-SCENARIO CANONICAL TRACE MAPPING ===")
    total_expected = 0
    detected_count = 0
    missing_count = 0
    unexpected_count = 0
    clean_matches_passed = 0
    
    scenario_results = []
    
    for scenario_id, gt in ground_truth.items():
        exp_exc = gt.get("expected_exception", False)
        exp_cat = gt.get("expected_category", gt.get("expected_outcome", "MATCHED"))
        
        if exp_exc:
            total_expected += 1
            
        src_ids = gt.get("gateway_ids", []) + gt.get("ledger_ids", []) + gt.get("bank_ids", [])
        if not src_ids:
            src_ids = [
                f"GW_{scenario_id}", f"LD_{scenario_id}", f"BK_{scenario_id}",
                f"GW_{scenario_id}_A", f"GW_{scenario_id}_B",
                f"LD_{scenario_id}_A", f"LD_{scenario_id}_B",
                f"BK_{scenario_id}_A", f"BK_{scenario_id}_B",
            ]
        
        attached_excs = []
        for d in src_ids:
            if d in domain_to_excs:
                for exc in domain_to_excs[d]:
                    attached_excs.append((d, exc))
                    
        detected_cats = [e.get("category") or e.get("exception_category") for _, e in attached_excs]
        detected_ids = [str(e.get("exception_id") or e.get("id"))[:8] for _, e in attached_excs]
        membership = [d for d, _ in attached_excs]
        
        if exp_exc:
            if attached_excs:
                status = "PASS"
                detected_count += 1
            else:
                status = "FAIL (MISSING)"
                missing_count += 1
        else:
            if not attached_excs:
                status = "PASS"
                clean_matches_passed += 1
            else:
                status = "FAIL (UNEXPECTED)"
                unexpected_count += 1
                
        res_str = f"[{status:<17}] {scenario_id:<20} | Exp: {str(exp_cat):<28} | Detected: {str(detected_cats or 'None')}"
        print(res_str)
        scenario_results.append((scenario_id, exp_exc, exp_cat, detected_ids, detected_cats, membership, status))
        
    print("\n=== SUMMARY ===")
    print(f"Total Logical Transactions: {len(ground_truth)}")
    print(f"Total Physical Records:     {len(txn_mapping)}")
    print(f"Clean Matches Passed:       {clean_matches_passed} / {len(ground_truth) - total_expected}")
    print(f"Expected Exception Scenarios: {total_expected}")
    print(f"Detected Exception Scenarios: {detected_count}")
    print(f"Missing Exception Scenarios:  {missing_count}")
    print(f"Unexpected Exception Scenarios: {unexpected_count}")
    print(f"Total Raw Exceptions in DB:   {len(exceptions)}")
    coverage = (detected_count / total_expected * 100.0) if total_expected > 0 else 0.0
    print(f"Coverage: {coverage:.1f}%")
    
    if detected_count == total_expected == 46 and missing_count == 0 and unexpected_count == 0:
        print("\n>>> TRACE VERIFICATION RESULT: PASS <<<")
    else:
        print("\n>>> TRACE VERIFICATION RESULT: FAIL <<<")


if __name__ == "__main__":
    asyncio.run(main())
