import asyncio
import asyncpg

async def check_schema():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
    columns = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'transactions' ORDER BY ordinal_position")
    for c in columns:
        print(f"{c['column_name']}: {c['data_type']}")
    await conn.close()

asyncio.run(check_schema())
