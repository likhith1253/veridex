import asyncio
import asyncpg

async def trace_transaction():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
    
    # Get a specific amount_mismatch transaction
    gw_id = 'EVAL_GW_0009'
    
    # Find the transaction
    txn = await conn.fetchrow("SELECT * FROM transactions WHERE domain_transaction_id = $1", gw_id)
    if txn:
        print(f"Transaction found: {txn['id']} | {txn['domain_transaction_id']} | {txn['amount']} | {txn['source']}")
        
        # Check if it's in any match
        match_txn = await conn.fetchrow("SELECT * FROM match_transactions WHERE transaction_id = $1", txn['id'])
        if match_txn:
            print(f"  In match: {match_txn['match_id']}")
            
            # Get the match details
            match = await conn.fetchrow("SELECT * FROM matches WHERE id = $1", match_txn['match_id'])
            if match:
                print(f"  Match confidence: {match['confidence']}")
                print(f"  Match reason: {match['reason']}")
                print(f"  Match type: {match['match_type']}")
                
                # Get all transactions in this match
                all_match_txns = await conn.fetch("SELECT t.*, mt.* FROM match_transactions mt JOIN transactions t ON mt.transaction_id = t.id WHERE mt.match_id = $1", match['id'])
                print(f"  All transactions in match cluster:")
                for mt in all_match_txns:
                    print(f"    - {mt['domain_transaction_id']} | {mt['amount']} | {mt['source']}")
        else:
            print(f"  NOT in any match")
        
        # Check if it has an exception
        exc = await conn.fetchrow("SELECT * FROM exceptions WHERE transaction_id = $1", txn['id'])
        if exc:
            print(f"  Has exception: {exc['id']} | {exc['exception_category']} | {exc['explanation']}")
        else:
            print(f"  NO exception")
    
    # Check total exceptions in the run
    run_exc = await conn.fetchrow("""
        SELECT COUNT(*) as cnt 
        FROM exceptions e 
        JOIN reconciliation_runs r ON e.run_id = r.id 
        WHERE r.run_id = 'adversarial_eval_7333'
    """)
    print(f"\nTotal exceptions in adversarial_eval_7333: {run_exc['cnt']}")
    
    # Check total matches in the run
    run_matches = await conn.fetchrow("""
        SELECT COUNT(*) as cnt 
        FROM matches m 
        JOIN reconciliation_runs r ON m.run_id = r.id 
        WHERE r.run_id = 'adversarial_eval_7333'
    """)
    print(f"Total matches in adversarial_eval_7333: {run_matches['cnt']}")
    
    await conn.close()

asyncio.run(trace_transaction())
