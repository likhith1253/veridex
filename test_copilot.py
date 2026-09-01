import asyncio
import httpx

async def test_copilot():
    async with httpx.AsyncClient() as client:
        # Test copilot brief
        print("Testing copilot brief...")
        response = await client.get(
            "http://localhost:8000/api/v1/controller/copilot/brief",
            params={"run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Copilot Brief Status: {data.get('status')}")
            print(f"Money at risk: ₹{data.get('money_at_risk_inr', 0):,.2f}")
            print(f"Match rate: {data.get('reconciliation_match_rate_percent', 0):.2f}%")
            print(f"Answer: {data.get('why', 'N/A')[:200]}...")
        else:
            print(f"Error: {response.status_code} - {response.text}")

        # Test copilot query
        print("\nTesting copilot query...")
        response = await client.post(
            "http://localhost:8000/api/v1/controller/copilot/query",
            json={"question": "What needs my attention right now?", "run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Answer: {data.get('answer', 'N/A')[:200]}...")
            print(f"Source: {data.get('source', 'N/A')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

        # Test another query
        print("\nTesting another copilot query...")
        response = await client.post(
            "http://localhost:8000/api/v1/controller/copilot/query",
            json={"question": "Which source is unhealthy?", "run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Answer: {data.get('answer', 'N/A')[:200]}...")
            print(f"Source: {data.get('source', 'N/A')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

asyncio.run(test_copilot())
