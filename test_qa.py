import asyncio
import httpx

async def test_qa():
    async with httpx.AsyncClient() as client:
        # Test QA endpoint
        print("Testing QA endpoint...")
        response = await client.post(
            "http://localhost:8000/api/v1/controller/qa",
            json={"question": "What is the total amount reconciled?", "run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Direct Answer: {data.get('direct_answer', 'N/A')[:200]}...")
            print(f"Confidence: {data.get('confidence', 0)}")
            print(f"Key Metrics: {data.get('key_metrics', {})}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

        # Test another QA question
        print("\nTesting another QA question...")
        response = await client.post(
            "http://localhost:8000/api/v1/controller/qa",
            json={"question": "How many exceptions are there?", "run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Direct Answer: {data.get('direct_answer', 'N/A')[:200]}...")
            print(f"Confidence: {data.get('confidence', 0)}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

asyncio.run(test_qa())
