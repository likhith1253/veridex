"""
Test simple ingestion to debug API issues.
"""
import asyncio
import httpx

async def test():
    # Simple test data
    gateway_data = [
        {
            "txn_id": "GW_TEST_1",
            "source": "gateway",
            "reference_number": "REF_TEST_1",
            "order_id": "ORD_TEST_1",
            "amount": "1000.00",
            "currency": "INR",
            "timestamp": "2026-08-31T10:00:00",
            "narration": "Test payment",
            "fee": "20.00",
            "tax": "3.60"
        }
    ]
    
    ledger_data = [
        {
            "txn_id": "LD_TEST_1",
            "source": "ledger",
            "reference_number": "REF_TEST_1",
            "order_id": "ORD_TEST_1",
            "amount": "1000.00",
            "currency": "INR",
            "timestamp": "2026-08-31T10:00:00",
            "narration": "Test order",
            "fee": "20.00",
            "tax": "3.60"
        }
    ]
    
    bank_data = [
        {
            "txn_id": "BK_TEST_1",
            "source": "bank",
            "reference_number": "UTR_TEST_1",
            "order_id": "ORD_TEST_1",
            "amount": "976.40",
            "currency": "INR",
            "timestamp": "2026-09-01T10:00:00",
            "narration": "Test settlement",
            "fee": "0.00",
            "tax": "0.00"
        }
    ]
    
    # Ingest via API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/controller/ingest/batch",
            json={
                "batch_id": "simple_test",
                "gateway_records": gateway_data,
                "ledger_records": ledger_data,
                "bank_records": bank_data
            }
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test())
