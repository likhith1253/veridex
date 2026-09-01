import asyncio
import httpx
import json

async def check_exceptions():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/controller/exceptions",
            params={"run_id": "adversarial_eval_7138", "page_size": 100}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Total exceptions: {data.get('total_count', 0)}")
            print(f"Exceptions returned: {len(data.get('exceptions', []))}")
            print("\nFirst exception:")
            if data.get('exceptions'):
                print(json.dumps(data['exceptions'][0], indent=2))
            else:
                print("No exceptions found")
        else:
            print(f"Error: {response.status_code} - {response.text}")

asyncio.run(check_exceptions())
