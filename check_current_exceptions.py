import asyncio
import httpx

async def check_exceptions():
    async with httpx.AsyncClient() as client:
        # Get exceptions for adversarial_eval_7333 run
        response = await client.get(
            "http://localhost:8000/api/v1/controller/exceptions",
            params={"run_id": "adversarial_eval_7333", "page_size": 100}
        )
        if response.status_code == 200:
            data = response.json()
            exceptions = data.get("exceptions", [])
            total = data.get("total_count", 0)
            print(f"Total exceptions for adversarial_eval_7333: {total}")
            print(f"\nException details:")
            for exc in exceptions:
                print(f"  - ID: {exc.get('exception_id')}")
                print(f"    Category: {exc.get('category')}")
                print(f"    Exposure: ₹{exc.get('financial_exposure_inr', 0):,.2f}")
                print(f"    Explanation: {exc.get('explanation', 'N/A')[:100]}...")
                print()
        else:
            print(f"Error: {response.status_code} - {response.text}")

        # Get summary KPIs for the run
        response = await client.get(
            "http://localhost:8000/api/v1/controller/summary",
            params={"run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            kpis = response.json()
            print(f"\nSummary KPIs for adversarial_eval_7333:")
            print(f"  Total records: {kpis.get('total_records_processed', 0)}")
            print(f"  Match rate: {kpis.get('match_rate', 0):.2f}%")
            print(f"  Deterministic matches: {kpis.get('deterministic_matches', 0)}")
            print(f"  ML recovered: {kpis.get('ml_recovered_matches', 0)}")
            print(f"  Manual reviews: {kpis.get('manual_reviews', 0)}")
            print(f"  Unresolved: {kpis.get('unresolved_transactions', 0)}")
            print(f"  Exception rate: {kpis.get('exception_rate', 0):.2f}%")
        else:
            print(f"Error getting KPIs: {response.status_code} - {response.text}")

asyncio.run(check_exceptions())
