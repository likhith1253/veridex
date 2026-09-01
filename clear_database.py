import asyncio
import asyncpg

async def clear_database():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
    
    # Delete in correct order to respect foreign keys
    await conn.execute("DELETE FROM audit_events")
    await conn.execute("DELETE FROM decisions")
    await conn.execute("DELETE FROM investigations")
    await conn.execute("DELETE FROM exception_transactions")
    await conn.execute("DELETE FROM match_transactions")
    await conn.execute("DELETE FROM matches")
    await conn.execute("DELETE FROM exceptions")
    await conn.execute("DELETE FROM reconciliation_items")
    await conn.execute("DELETE FROM reconciliation_runs")
    await conn.execute("DELETE FROM transactions")
    
    print("Database cleared successfully")
    
    await conn.close()

asyncio.run(clear_database())
