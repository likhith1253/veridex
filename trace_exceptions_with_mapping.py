import asyncio
import httpx
import json
import sys
from collections import Counter, defaultdict

# Load ground truth
with open('private_ground_truth.json', 'r') as f:
    ground_truth = json.load(f)

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
    print(f"Coverage: {total_detected / total_expected * 100:.1f}%")

asyncio.run(main())
