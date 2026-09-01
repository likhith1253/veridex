import json
import asyncio
import httpx

# Load ground truth
with open('private_ground_truth.json', 'r') as f:
    ground_truth = json.load(f)

# Get current exceptions from API
async def get_current_exceptions():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/controller/exceptions",
            params={"run_id": "adversarial_eval_7138", "page_size": 100}
        )
        if response.status_code == 200:
            data = response.json()
            exceptions = data.get("exceptions", [])
            # Extract transaction IDs from exceptions - some may have transaction_id field
            txn_ids = set()
            for e in exceptions:
                if e.get('transaction_id'):
                    txn_ids.add(e.get('transaction_id'))
            return txn_ids
        return set()

async def main():
    current_exceptions = await get_current_exceptions()
    print(f"Current exceptions: {len(current_exceptions)}")
    
    # Analyze by scenario
    from collections import Counter, defaultdict
    scenario_counts = Counter()
    missing_by_scenario = defaultdict(list)
    
    for logical_id, data in ground_truth.items():
        scenario = data['scenario']
        outcome = data['expected_outcome']
        scenario_counts[scenario] += 1
        
        if 'exception' in outcome.lower():
            # Check if any of the transaction IDs are in current exceptions
            gw_id = data.get('gateway_id')
            ld_id = data.get('ledger_id')
            bk_id = data.get('bank_id')
            
            found = False
            for txn_id in [gw_id, ld_id, bk_id]:
                if txn_id and txn_id in current_exceptions:
                    found = True
                    break
            
            if not found:
                missing_by_scenario[scenario].append({
                    'logical_id': logical_id,
                    'gateway_id': gw_id,
                    'ledger_id': ld_id,
                    'bank_id': bk_id,
                    'expected_outcome': outcome,
                    'amount': data['amount']
                })
    
    print("\n=== SCENARIO BREAKDOWN ===")
    for scenario, count in scenario_counts.most_common():
        missing = len(missing_by_scenario.get(scenario, []))
        print(f"{scenario}: {count} total, {missing} missing ({count-missing} detected)")
    
    print("\n=== MISSING EXCEPTIONS BY SCENARIO ===")
    for scenario, missing_list in sorted(missing_by_scenario.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{scenario} ({len(missing_list)} missing):")
        for item in missing_list[:3]:  # Show first 3
            print(f"  - {item['logical_id']}: amount={item['amount']}, expected={item['expected_outcome']}")
            print(f"    GW: {item['gateway_id']}, LD: {item['ledger_id']}, BK: {item['bank_id']}")
        if len(missing_list) > 3:
            print(f"  ... and {len(missing_list) - 3} more")

asyncio.run(main())
