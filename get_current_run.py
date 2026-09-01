import asyncio
import httpx

async def get_runs():
    async with httpx.AsyncClient() as client:
        resp = await client.get('http://localhost:8000/api/v1/controller/runs')
        if resp.status_code == 200:
            print(resp.json())
        else:
            print(f"Error: {resp.status_code}")

asyncio.run(get_runs())
