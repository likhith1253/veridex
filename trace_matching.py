import asyncio
import httpx
import json

async def trace_matching():
    async with httpx.AsyncClient() as client:
        # Get all transactions for the run
        response = await client.get(
            "http://localhost:8000/api/v1/controller/transactions",
            params={"run_id": "adversarial_eval_2442", "limit": 500}
        )
        if response.status_code != 200:
            print(f"Error getting transactions: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        transactions = data.get("transactions", [])
        print(f"Total transactions: {len(transactions)}")
        
        # Get matches
        response = await client.get(
            "http://localhost:8000/api/v1/controller/matches",
            params={"run_id": "adversarial_eval_2442", "limit": 200}
        )
        if response.status_code != 200:
            print(f"Error getting matches: {response.status_code} - {response.text}")
            return
            
        match_data = response.json()
        matches = match_data.get("matches", [])
        print(f"Total matches: {len(matches)}")
        
        # Analyze a specific scenario - amount_mismatch_gw_ledger
        print("\n=== Checking amount_mismatch_gw_ledger scenario ===")
        # Find transactions with EVAL_TXN_0015 (from the missing list)
        target_txn = None
        for txn in transactions:
            if 'EVAL_TXN_0015' in str(txn.get('domain_transaction_id', '')):
                target_txn = txn
                break
        
        if target_txn:
            print(f"Found target transaction: {target_txn.get('domain_transaction_id')}, amount={target_txn.get('amount')}, source={target_txn.get('source')}")
            # Check if it's in any match
            found_match = False
            for match in matches:
                if target_txn.get('id') in match.get('transaction_ids', []):
                    print(f"Transaction is in match: {match}")
                    # Get the other transactions in the match
                    for tid in match.get('transaction_ids', []):
                        if tid != target_txn.get('id'):
                            other_txn = next((t for t in transactions if t.get('id') == tid), None)
                            if other_txn:
                                print(f"  Matched with: {other_txn.get('domain_transaction_id')}, amount={other_txn.get('amount')}, source={other_txn.get('source')}")
                    found_match = True
            if not found_match:
                print("Transaction is NOT in any match (should be exception)")
        else:
            print("Target transaction not found")
        
        # Check another scenario
        print("\n=== Checking amount_mismatch_gw_bank scenario ===")
        target_txn = None
        for txn in transactions:
            if 'EVAL_TXN_0002' in str(txn.get('domain_transaction_id', '')):
                target_txn = txn
                break
        
        if target_txn:
            print(f"Found target transaction: {target_txn.get('domain_transaction_id')}, amount={target_txn.get('amount')}, source={target_txn.get('source')}")
            found_match = False
            for match in matches:
                if target_txn.get('id') in match.get('transaction_ids', []):
                    print(f"Transaction is in match: {match}")
                    for tid in match.get('transaction_ids', []):
                        if tid != target_txn.get('id'):
                            other_txn = next((t for t in transactions if t.get('id') == tid), None)
                            if other_txn:
                                print(f"  Matched with: {other_txn.get('domain_transaction_id')}, amount={other_txn.get('amount')}, source={other_txn.get('source')}")
                    found_match = True
            if not found_match:
                print("Transaction is NOT in any match (should be exception)")
        else:
            print("Target transaction not found")

asyncio.run(trace_matching())
