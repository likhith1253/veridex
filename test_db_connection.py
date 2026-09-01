import asyncpg
import asyncio

async def test_connection():
    try:
        conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
        print('Connected successfully')
        await conn.close()
    except Exception as e:
        print(f'Connection failed: {e}')

asyncio.run(test_connection())
