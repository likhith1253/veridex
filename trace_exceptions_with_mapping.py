import asyncio
import httpx
import json
import sys
from collections import Counter, defaultdict

from eval.benchmark_registry import validate_ground_truth_namespace

# Load ground truth
with open('private_ground_truth.json', 'r') as f:
    ground_truth = validate_ground_truth_namespace(json.load(f))

async def resolve_run_id(client: httpx.AsyncClient) -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    response = await client.get("http://localhost:8000/api/v1/runs")
    if response.status_code == 200:
        runs = response.json().get("runs", [])
        if runs:
            return runs[0].get("run_id") or runs[0].get("id")
    return "adversarial_eval_1595"

async def get_current_exceptions(client: httpx.AsyncClient, run_id: str):
    response = await client.get(
        "http://localhost:8000/api/v1/controller/exceptions",
        params={"run_id": run_id, "page_size": 200}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("exceptions", [])
    print(f"Exception API failed: {response.status_code} {response.text}")
    return []

async def get_transaction_mapping(client: httpx.AsyncClient, run_id: str):
    """Get mapping between domain transaction IDs and ORM UUIDs"""
    response = await client.get(
        "http://localhost:8000/api/v1/controller/transactions",
        params={"run_id": run_id, "limit": 500}
    )
    if response.status_code == 200:
        data = response.json()
        transactions = data.get("transactions", [])
        mapping = {}
        for txn in transactions:
            if txn.get('domain_transaction_id') and txn.get('id'):
                mapping[txn['domain_transaction_id']] = txn['id']
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
    print(f"Transaction mapping: {len(txn_mapping)} entries")
    
    # Build set of exception transaction IDs (ORM UUIDs)
    exception_txn_ids = {e.get('transaction_id') for e in exceptions if e.get('transaction_id')}
    
    # Check ground truth format to determine schema
    sample_key = list(ground_truth.keys())[0] if ground_truth else None
    sample_data = ground_truth[sample_key] if sample_key else {}
    
    # Determine if this is the new format (from independent_adversarial_eval.py) or old format
    is_new_format = 'expected_exception' in sample_data and 'gross_amount' in sample_data
    
    if is_new_format:
        print("Using canonical ADV_* ground truth format (independent_adversarial_eval.py)")
        
        # Build inverted mapping: ORM UUID -> domain_transaction_id
        orm_to_domain = {v: k for k, v in txn_mapping.items()}
        
        # Group exceptions by domain transaction ID
        domain_to_excs = defaultdict(list)
        for exc in exceptions:
            t_id = exc.get("transaction_id")
            domain_id = orm_to_domain.get(t_id, "UNKNOWN")
            domain_to_excs[domain_id].append(exc)
            
        print("\n=== SCENARIO-BY-SCENARIO TRACE MAPPING ===")
        total_expected = 0
        detected_count = 0
        missing_count = 0
        unexpected_count = 0
        
        scenario_results = []
        
        for scenario_id, gt in ground_truth.items():
            exp_exc = gt.get("expected_exception", False)
            exp_cat = gt.get("expected_category", gt.get("expected_outcome", "MATCHED"))
            
            if exp_exc:
                total_expected += 1
                
            possible_domains = [
                f"GW_{scenario_id}",
                f"LD_{scenario_id}",
                f"BK_{scenario_id}",
                f"GW_{scenario_id}_A",
                f"GW_{scenario_id}_B",
            ]
            
            attached_excs = []
            for d in possible_domains:
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
                else:
                    status = "FAIL (UNEXPECTED)"
                    unexpected_count += 1
                    
            res_str = f"{scenario_id} -> exp_cat: {exp_cat} | det_ids: {detected_ids or 'None'} | det_cats: {detected_cats or 'None'} | txn_members: {membership or 'None'} | {status}"
            print(res_str)
            scenario_results.append((scenario_id, exp_exc, exp_cat, detected_ids, detected_cats, membership, status))
            
        print("\n=== SUMMARY ===")
        print(f"Total Logical Transactions: {len(ground_truth)}")
        print(f"Total Physical Records:     {len(txn_mapping)}")
        print(f"Expected Exception Scenarios: {total_expected}")
        print(f"Detected Exception Scenarios: {detected_count}")
        print(f"Missing Exception Scenarios:  {missing_count}")
        print(f"Unexpected Exception Scenarios: {unexpected_count}")
        print(f"Total Raw Exceptions in DB:   {len(exceptions)}")
        coverage = (detected_count / total_expected * 100.0) if total_expected > 0 else 0.0
        print(f"Coverage: {coverage:.1f}%")
        return
    
    # Old format handling (from adversarial_evaluator.py)
    print("Using old ground truth format (adversarial_evaluator.py)")
    
    # Analyze by scenario
    scenario_counts = Counter()
    missing_by_scenario = defaultdict(list)
    
    for txn_id, scenario_data in ground_truth.items():
        scenario = scenario_data.get('scenario', 'unknown')
        expected_outcome = scenario_data.get('expected_outcome', 'unknown')
        
        scenario_counts[scenario] += 1
        
        # Check if this transaction should have an exception
        should_have_exception = 'exception' in expected_outcome or expected_outcome in [
            'amount_mismatch_exception', 'settlement_variance_exception', 
            'missing_source_exception', 'duplicate_exception', 
            'fee_mismatch_exception', 'tax_mismatch_exception',
            'delayed_settlement_exception', 'partial_match_exception',
            'missing_fields_exception', 'complex_mismatch_exception'
        ]
        
        if should_have_exception:
            source_ids = [
                scenario_data.get("gateway_id"),
                scenario_data.get("ledger_id"),
                scenario_data.get("bank_id"),
                f"{scenario_data.get('gateway_id')}_DUP" if scenario_data.get("gateway_id") else None,
                f"{scenario_data.get('ledger_id')}_DUP" if scenario_data.get("ledger_id") else None,
                f"{scenario_data.get('bank_id')}_DUP" if scenario_data.get("bank_id") else None,
            ]
            orm_ids = {txn_mapping[source_id] for source_id in source_ids if source_id in txn_mapping}
            matching_exceptions = [e for e in exceptions if e.get("transaction_id") in orm_ids]
            expected_category = expected_outcome
            detected = any(e.get("category") == expected_category for e in matching_exceptions)
            if not detected:
                missing_by_scenario[scenario].append(txn_id)
    
    print("\n=== SCENARIO BREAKDOWN ===")
    for scenario, count in scenario_counts.most_common():
        missing = len(missing_by_scenario.get(scenario, []))
        detected = count - missing
        print(f"{scenario}: {count} total, {missing} missing ({detected} detected)")
    
    print("\n=== MISSING EXCEPTIONS BY SCENARIO ===")
    for scenario, txn_ids in sorted(missing_by_scenario.items(), key=lambda x: len(x[1]), reverse=True):
        if txn_ids:
            print(f"\n{scenario} ({len(txn_ids)} missing):")
            for tid in txn_ids[:3]:
                data = ground_truth[tid]
                print(f"  - {tid}: amount={data.get('amount')}, expected={data.get('expected_outcome')}")
                print(f"    GW: {data.get('gateway_id')}, LD: {data.get('ledger_id')}, BK: {data.get('bank_id')}")
            if len(txn_ids) > 3:
                print(f"  ... and {len(txn_ids) - 3} more")
    
    total_expected = sum(1 for s in ground_truth.values() if 'exception' in s.get('expected_outcome', ''))
    total_detected = total_expected - sum(len(v) for v in missing_by_scenario.values())
    print(f"\n=== SUMMARY ===")
    print(f"Expected exceptions: {total_expected}")
    print(f"Detected exceptions: {total_detected}")
    print(f"Missing exceptions: {total_expected - total_detected}")
    if total_expected > 0:
        print(f"Coverage: {total_detected / total_expected * 100:.1f}%")

asyncio.run(main())
