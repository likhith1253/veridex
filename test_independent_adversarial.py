"""
Test independent adversarial dataset ingestion and exception detection.
"""
import asyncio
import httpx
from generate_independent_adversarial import generate_adversarial_dataset

async def test():
    # Generate the adversarial dataset
    transactions = generate_adversarial_dataset()
    
    # Convert to API format
    gateway_data = [
        {
            "txn_id": t["txn_id"],
            "source": t["source"],
            "reference_number": t["reference_number"],
            "order_id": t["order_id"],
            "amount": str(t["amount"]),
            "currency": t["currency"],
            "timestamp": t["timestamp"].isoformat(),
            "narration": t["narration"],
            "fee": str(t["fee"]),
            "tax": str(t["tax"])
        }
        for t in transactions["gateway"]
    ]
    
    ledger_data = [
        {
            "txn_id": t["txn_id"],
            "source": t["source"],
            "reference_number": t["reference_number"],
            "order_id": t["order_id"],
            "amount": str(t["amount"]),
            "currency": t["currency"],
            "timestamp": t["timestamp"].isoformat(),
            "narration": t["narration"],
            "fee": str(t["fee"]),
            "tax": str(t["tax"])
        }
        for t in transactions["ledger"]
    ]
    
    bank_data = [
        {
            "txn_id": t["txn_id"],
            "source": t["source"],
            "reference_number": t["reference_number"],
            "order_id": t["order_id"],
            "amount": str(t["amount"]),
            "currency": t["currency"],
            "timestamp": t["timestamp"].isoformat(),
            "narration": t["narration"],
            "fee": str(t["fee"]),
            "tax": str(t["tax"])
        }
        for t in transactions["bank"]
    ]
    
    # Ingest via API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/controller/ingest/batch",
            json={
                "batch_id": "independent_adversarial_v2",
                "gateway_records": gateway_data,
                "ledger_records": ledger_data,
                "bank_records": bank_data
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Ingestion successful:")
            print(f"  Batch ID: {result['batch_id']}")
            print(f"  Records received: {result['records_received']}")
            print(f"  Records normalized: {result['records_normalized']}")
            print(f"  Auto matched: {result['auto_matched_count']}")
            print(f"  ML recovered: {result['ml_recovered_count']}")
            print(f"  Manual review: {result['manual_review_count']}")
            print(f"  Unresolved: {result['unresolved_count']}")
            
            # Get exceptions for this run
            exc_response = await client.get(
                "http://localhost:8000/api/v1/controller/exceptions",
                params={"run_id": "independent_adversarial_v2"}
            )
            
            if exc_response.status_code == 200:
                exc_data = exc_response.json()
                print(f"\nExceptions detected: {exc_data['total_count']}")
                
                for exc in exc_data['exceptions']:
                    print(f"\n  Category: {exc['category']}")
                    print(f"  Explanation: {exc['explanation']}")
                    print(f"  Exposure: {exc['financial_exposure_inr']}")
            else:
                print(f"Error getting exceptions: {exc_response.status_code}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test())
