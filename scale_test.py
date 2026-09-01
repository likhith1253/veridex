"""
Scale Testing
Test system with larger batches to evaluate performance and degradation
"""
import json
import random
import httpx
from datetime import datetime, timezone, timedelta
from decimal import Decimal


class ScaleTester:
    """Test system with larger batches"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=60.0)
        self.base_url = "http://localhost:8000"
    
    def generate_large_batch(self, num_records: int) -> tuple:
        """Generate a large batch of records"""
        
        gateway_records = []
        ledger_records = []
        bank_records = []
        
        base_date = datetime.now(timezone.utc)
        
        for i in range(num_records):
            logical_id = f"SCALE_TXN_{i:04d}"
            gateway_id = f"SCALE_GW_{i:04d}"
            ledger_id = f"SCALE_LD_{i:04d}"
            bank_id = f"SCALE_BK_{i:04d}"
            
            amount = Decimal(str(random.randint(500, 50000)))
            timestamp = base_date - timedelta(days=random.randint(0, 3), hours=random.randint(0, 23))
            utr = f"UTR_{random.randint(100000, 999999)}"
            order_id = f"ORD_{random.randint(10000, 99999)}"
            
            # Mostly exact matches for scale testing
            fee = amount * Decimal("0.02")
            tax = fee * Decimal("0.18")
            net = amount - fee - tax
            
            gateway_records.append({
                "txn_id": gateway_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
                "fee": float(fee),
                "tax": float(tax),
            })
            
            ledger_records.append({
                "txn_id": ledger_id,
                "amount": float(amount),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "order_id": order_id,
                "reference_number": utr,
            })
            
            bank_records.append({
                "txn_id": bank_id,
                "amount": float(net),
                "currency": "INR",
                "timestamp": timestamp.isoformat(),
                "reference_number": utr,
                "narration": f"Settlement for {utr}",
            })
        
        return gateway_records, ledger_records, bank_records
    
    def test_scale(self, sizes: list[int]) -> dict:
        """Test system with different batch sizes"""
        
        results = {}
        
        for size in sizes:
            print(f"\nTesting scale with {size} records...")
            
            try:
                # Generate batch
                gateway, ledger, bank = self.generate_large_batch(size)
                
                # Ingest and measure time
                start_time = datetime.now()
                
                response = self.client.post(
                    f"{self.base_url}/api/v1/controller/ingest/batch",
                    json={
                        "gateway_records": gateway,
                        "ledger_records": ledger,
                        "bank_records": bank,
                        "batch_id": f"scale_test_{size}",
                    }
                )
                
                end_time = datetime.now()
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                result = response.json()
                
                results[size] = {
                    "success": response.status_code == 200,
                    "duration_ms": duration_ms,
                    "records_processed": result.get("records_received", 0),
                    "processing_status": result.get("processing_status"),
                    "reconciliation_status": result.get("reconciliation_status"),
                    "tps": size / (duration_ms / 1000) if duration_ms > 0 else 0,
                    "system_reported_tps": None,  # Would need to get from summary
                }
                
                print(f"  Duration: {duration_ms:.2f}ms")
                print(f"  TPS: {size / (duration_ms / 1000):.2f}")
                print(f"  Status: {result.get('processing_status')}")
                
            except Exception as e:
                results[size] = {
                    "success": False,
                    "error": str(e),
                }
                print(f"  Failed: {e}")
        
        return results


def main():
    """Run scale tests"""
    print("Scale Testing")
    print("=" * 60)
    
    tester = ScaleTester()
    
    # Test with progressively larger batches
    sizes = [50, 100, 250]
    results = tester.test_scale(sizes)
    
    print("\n" + "=" * 60)
    print("SCALE TEST RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    
    # Save results
    with open("scale_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nScale test results saved to scale_test_results.json")


if __name__ == "__main__":
    main()
