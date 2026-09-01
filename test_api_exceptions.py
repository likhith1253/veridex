import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        # Test the exceptions API endpoint
        response = await client.get(
            "http://localhost:8000/api/v1/controller/exceptions",
            params={"run_id": "adversarial_eval_7333"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total exceptions: {data['total_count']}")
            
            for exc in data['exceptions']:
                print(f"\nException ID: {exc['exception_id']}")
                print(f"Category: {exc['category']}")
                print(f"Status: {exc['status']}")
                print(f"Explanation: {exc['explanation']}")
                print(f"Financial exposure: {exc['financial_exposure_inr']}")
                print(f"Recommended action: {exc['recommended_action']}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test())
