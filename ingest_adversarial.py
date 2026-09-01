import asyncio
import httpx
import random
from adversarial_evaluator import AdversarialDatasetGenerator

async def ingest_adversarial():
    # Generate fresh adversarial dataset
    generator = AdversarialDatasetGenerator(seed=random.randint(10000, 99999))
    gateway_records, ledger_records, bank_records, ground_truth = generator.generate_comprehensive_dataset(num_records=100)
    
    print(f"Generated {len(gateway_records)} gateway, {len(ledger_records)} ledger, {len(bank_records)} bank records")
    
    # Save ground truth
    import json
    with open('private_ground_truth.json', 'w') as f:
        json.dump(ground_truth, f, indent=2)
    print("Saved ground truth to private_ground_truth.json")
    
    # Ingest via API
    async with httpx.AsyncClient(timeout=300.0) as client:
        batch_id = f"adversarial_eval_{random.randint(1000, 9999)}"
        response = await client.post(
            "http://localhost:8000/api/v1/controller/ingest/batch",
            json={
                "gateway_records": gateway_records,
                "ledger_records": ledger_records,
                "bank_records": bank_records,
                "batch_id": batch_id,
            }
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nIngestion successful!")
            print(f"Batch ID: {batch_id}")
            print(f"Run ID: {result.get('run_id')}")
            print(f"Records received: {result.get('records_received', 0)}")
            print(f"Records normalized: {result.get('records_normalized', 0)}")
            print(f"Auto matched: {result.get('auto_matched_count', 0)}")
            print(f"ML recovered: {result.get('ml_recovered_count', 0)}")
            print(f"Manual review: {result.get('manual_review_count', 0)}")
            print(f"Unresolved: {result.get('unresolved_count', 0)}")
            return batch_id, result.get('run_id')
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None, None

if __name__ == "__main__":
    batch_id, run_id = asyncio.run(ingest_adversarial())
    print(f"\nUse run_id: {run_id} for testing")
