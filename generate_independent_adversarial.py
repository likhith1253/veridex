"""
Generate independent adversarial dataset for Razorpay evaluation.
This creates a fresh dataset with known ground truth to test exception detection.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

def generate_adversarial_dataset():
    """Generate 50 transaction pairs with specific exception types."""
    
    base_date = datetime.now()
    
    transactions = {
        "gateway": [],
        "ledger": [],
        "bank": []
    }
    
    # 1. Exact matches (should reconcile)
    for i in range(10):
        amount = Decimal(str(random.randint(1000, 50000)))
        order_id = f"EXACT_ORD_{i}"
        ref_id = f"EXACT_REF_{i}"
        fee = amount * Decimal("0.02")
        tax = amount * Decimal("0.18") * Decimal("0.02")
        
        gateway = {
            "txn_id": f"GW_EXACT_{i}",
            "source": "gateway",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=i),
            "narration": f"Payment {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        ledger = {
            "txn_id": f"LD_EXACT_{i}",
            "source": "ledger",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=i),
            "narration": f"Order {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        bank = {
            "txn_id": f"BK_EXACT_{i}",
            "source": "bank",
            "reference_number": f"UTR_{i}",
            "order_id": order_id,
            "amount": amount - fee - tax,
            "currency": "INR",
            "timestamp": base_date + timedelta(days=1, hours=i),
            "narration": f"Settlement {i}",
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "status": "completed"
        }
        
        transactions["gateway"].append(gateway)
        transactions["ledger"].append(ledger)
        transactions["bank"].append(bank)
    
    # 2. Missing bank records (should detect missing source)
    for i in range(5):
        amount = Decimal(str(random.randint(1000, 50000)))
        order_id = f"MISS_BANK_ORD_{i}"
        ref_id = f"MISS_BANK_REF_{i}"
        fee = amount * Decimal("0.02")
        tax = amount * Decimal("0.18") * Decimal("0.02")
        
        gateway = {
            "txn_id": f"GW_MISS_BANK_{i}",
            "source": "gateway",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=10+i),
            "narration": f"Payment {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        ledger = {
            "txn_id": f"LD_MISS_BANK_{i}",
            "source": "ledger",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=10+i),
            "narration": f"Order {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        transactions["gateway"].append(gateway)
        transactions["ledger"].append(ledger)
        # No bank record
    
    # 3. Amount mismatches (should detect amount mismatch)
    for i in range(5):
        amount = Decimal(str(random.randint(1000, 50000)))
        order_id = f"AMT_MISMATCH_ORD_{i}"
        ref_id = f"AMT_MISMATCH_REF_{i}"
        fee = amount * Decimal("0.02")
        tax = amount * Decimal("0.18") * Decimal("0.02")
        
        gateway = {
            "txn_id": f"GW_AMT_MISMATCH_{i}",
            "source": "gateway",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=15+i),
            "narration": f"Payment {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        ledger = {
            "txn_id": f"LD_AMT_MISMATCH_{i}",
            "source": "ledger",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount + Decimal("1000"),  # Different amount
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=15+i),
            "narration": f"Order {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        bank = {
            "txn_id": f"BK_AMT_MISMATCH_{i}",
            "source": "bank",
            "reference_number": f"UTR_{100+i}",
            "order_id": order_id,
            "amount": amount - fee - tax,
            "currency": "INR",
            "timestamp": base_date + timedelta(days=1, hours=15+i),
            "narration": f"Settlement {i}",
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "status": "completed"
        }
        
        transactions["gateway"].append(gateway)
        transactions["ledger"].append(ledger)
        transactions["bank"].append(bank)
    
    # 4. Duplicate gateway records (should detect duplicate)
    for i in range(3):
        amount = Decimal(str(random.randint(1000, 50000)))
        order_id = f"DUP_ORD_{i}"
        ref_id = f"DUP_REF_{i}"
        fee = amount * Decimal("0.02")
        tax = amount * Decimal("0.18") * Decimal("0.02")
        
        gateway1 = {
            "txn_id": f"GW_DUP_{i}_1",
            "source": "gateway",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=20+i),
            "narration": f"Payment {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        gateway2 = {
            "txn_id": f"GW_DUP_{i}_2",
            "source": "gateway",
            "reference_number": ref_id,  # Same reference
            "order_id": order_id,  # Same order
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=20+i, minutes=5),
            "narration": f"Payment {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        ledger = {
            "txn_id": f"LD_DUP_{i}",
            "source": "ledger",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=20+i),
            "narration": f"Order {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        bank = {
            "txn_id": f"BK_DUP_{i}",
            "source": "bank",
            "reference_number": f"UTR_{200+i}",
            "order_id": order_id,
            "amount": amount - fee - tax,
            "currency": "INR",
            "timestamp": base_date + timedelta(days=1, hours=20+i),
            "narration": f"Settlement {i}",
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "status": "completed"
        }
        
        transactions["gateway"].append(gateway1)
        transactions["gateway"].append(gateway2)
        transactions["ledger"].append(ledger)
        transactions["bank"].append(bank)
    
    # 5. Fee mismatches (should detect fee mismatch)
    for i in range(3):
        amount = Decimal(str(random.randint(1000, 50000)))
        order_id = f"FEE_MISMATCH_ORD_{i}"
        ref_id = f"FEE_MISMATCH_REF_{i}"
        gateway_fee = amount * Decimal("0.03")
        gateway_tax = amount * Decimal("0.18") * Decimal("0.03")
        ledger_fee = amount * Decimal("0.02")
        ledger_tax = amount * Decimal("0.18") * Decimal("0.02")
        
        gateway = {
            "txn_id": f"GW_FEE_MISMATCH_{i}",
            "source": "gateway",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=25+i),
            "narration": f"Payment {i}",
            "fee": gateway_fee,
            "tax": gateway_tax,
            "status": "completed"
        }
        
        ledger = {
            "txn_id": f"LD_FEE_MISMATCH_{i}",
            "source": "ledger",
            "reference_number": ref_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=25+i),
            "narration": f"Order {i}",
            "fee": ledger_fee,  # Different fee
            "tax": ledger_tax,
            "status": "completed"
        }
        
        bank = {
            "txn_id": f"BK_FEE_MISMATCH_{i}",
            "source": "bank",
            "reference_number": f"UTR_{300+i}",
            "order_id": order_id,
            "amount": amount - gateway_fee - gateway_tax,
            "currency": "INR",
            "timestamp": base_date + timedelta(days=1, hours=25+i),
            "narration": f"Settlement {i}",
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "status": "completed"
        }
        
        transactions["gateway"].append(gateway)
        transactions["ledger"].append(ledger)
        transactions["bank"].append(bank)
    
    # 6. Identifier conflicts (should detect identifier conflict)
    for i in range(3):
        amount = Decimal(str(random.randint(1000, 50000)))
        order_id = f"ID_CONFLICT_ORD_{i}"
        fee = amount * Decimal("0.02")
        tax = amount * Decimal("0.18") * Decimal("0.02")
        
        gateway = {
            "txn_id": f"GW_ID_CONFLICT_{i}",
            "source": "gateway",
            "reference_number": f"REF_A_{i}",
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=30+i),
            "narration": f"Payment {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        ledger = {
            "txn_id": f"LD_ID_CONFLICT_{i}",
            "source": "ledger",
            "reference_number": f"REF_B_{i}",  # Different reference
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "timestamp": base_date + timedelta(hours=30+i),
            "narration": f"Order {i}",
            "fee": fee,
            "tax": tax,
            "status": "completed"
        }
        
        bank = {
            "txn_id": f"BK_ID_CONFLICT_{i}",
            "source": "bank",
            "reference_number": f"UTR_{400+i}",
            "order_id": order_id,
            "amount": amount - fee - tax,
            "currency": "INR",
            "timestamp": base_date + timedelta(days=1, hours=30+i),
            "narration": f"Settlement {i}",
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "status": "completed"
        }
        
        transactions["gateway"].append(gateway)
        transactions["ledger"].append(ledger)
        transactions["bank"].append(bank)
    
    return transactions

if __name__ == "__main__":
    transactions = generate_adversarial_dataset()
    print(f"Generated adversarial dataset:")
    print(f"Gateway: {len(transactions['gateway'])}")
    print(f"Ledger: {len(transactions['ledger'])}")
    print(f"Bank: {len(transactions['bank'])}")
    print(f"Total: {len(transactions['gateway']) + len(transactions['ledger']) + len(transactions['bank'])}")
