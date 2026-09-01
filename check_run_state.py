import asyncio
import asyncpg

async def check_run_state():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
    
    # Check if the run exists
    run = await conn.fetchrow("SELECT * FROM reconciliation_runs WHERE run_id = 'adversarial_eval_7333'")
    if run:
        print(f"Run exists: {run['id']} | {run['run_id']} | {run['created_at']}")
        
        # Get reconciliation items for this run
        items = await conn.fetch("SELECT COUNT(*) as cnt FROM reconciliation_items WHERE run_id = $1", run['id'])
        print(f"Reconciliation items: {items[0]['cnt']}")
        
        # Get transactions in this run
        txns = await conn.fetch("""
            SELECT COUNT(*) as cnt 
            FROM transactions t 
            JOIN reconciliation_items ri ON t.id = ri.transaction_id 
            WHERE ri.run_id = $1
        """, run['id'])
        print(f"Transactions in run: {txns[0]['cnt']}")
        
        # Get all transactions
        all_txns = await conn.fetchrow("SELECT COUNT(*) as cnt FROM transactions")
        print(f"Total transactions in DB: {all_txns['cnt']}")
        
        # Get all runs
        all_runs = await conn.fetch("SELECT run_id, created_at FROM reconciliation_runs ORDER BY created_at DESC LIMIT 5")
        print(f"\nRecent runs:")
        for r in all_runs:
            print(f"  - {r['run_id']} | {r['created_at']}")
    else:
        print("Run 'adversarial_eval_7333' does NOT exist")
        
        # Show all runs
        all_runs = await conn.fetch("SELECT run_id, created_at FROM reconciliation_runs ORDER BY created_at DESC LIMIT 10")
        print(f"\nAll runs in DB:")
        for r in all_runs:
            print(f"  - {r['run_id']} | {r['created_at']}")
    
    await conn.close()

asyncio.run(check_run_state())
