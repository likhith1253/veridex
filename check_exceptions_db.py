import asyncio
import asyncpg

async def check_exceptions():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
    
    # Check if run exists
    run = await conn.fetchrow("SELECT id, run_id, status FROM reconciliation_runs WHERE run_id = 'adversarial_eval_7138'")
    print(f"Run: {run}")
    
    if run:
        run_id = run['id']
        # Count exceptions for this run
        count = await conn.fetchval("SELECT COUNT(*) FROM exceptions WHERE run_id = $1", run_id)
        print(f"Exception count: {count}")
        
        # Show first few exceptions
        exceptions = await conn.fetch("SELECT id, exception_category, financial_exposure, created_at FROM exceptions WHERE run_id = $1 LIMIT 5", run_id)
        print("\nFirst 5 exceptions:")
        for exc in exceptions:
            print(f"  - {exc['id']}: {exc['exception_category']}, exposure={exc['financial_exposure']}")
    
    await conn.close()

asyncio.run(check_exceptions())
