import asyncio
import httpx
import json

async def verify_financials():
    async with httpx.AsyncClient() as client:
        # Get cash position for adversarial_eval_7333
        response = await client.get(
            "http://localhost:8000/api/v1/controller/cash-position",
            params={"run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            cash = response.json()
            print("Cash Position for adversarial_eval_7333:")
            print(f"  Expected Amount: ₹{float(cash.get('expected_amount', 0)):,.2f}")
            print(f"  Received Amount: ₹{float(cash.get('received_amount', 0)):,.2f}")
            print(f"  Pending Amount: ₹{float(cash.get('pending_amount', 0)):,.2f}")
            print(f"  Unreconciled Amount: ₹{float(cash.get('unreconciled_amount', 0)):,.2f}")
            print(f"  At Risk Amount: ₹{float(cash.get('at_risk_amount', 0)):,.2f}")
            print(f"  Expected Net Settlement: ₹{float(cash.get('expected_net_settlement', 0)):,.2f}")
        else:
            print(f"Error getting cash position: {response.status_code} - {response.text}")

        # Get exposure
        response = await client.get(
            "http://localhost:8000/api/v1/controller/exposure",
            params={"run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            exp = response.json()
            print("\nFinancial Exposure:")
            print(f"  Total Processed Value: ₹{float(exp.get('total_processed_value', 0)):,.2f}")
            print(f"  Matched Value: ₹{float(exp.get('matched_value', 0)):,.2f}")
            print(f"  ML Recovered Value: ₹{float(exp.get('ml_recovered_value', 0)):,.2f}")
            print(f"  Manual Review Value: ₹{float(exp.get('manual_review_value', 0)):,.2f}")
            print(f"  Unresolved Value: ₹{float(exp.get('unresolved_value', 0)):,.2f}")
            print(f"  High Risk Value: ₹{float(exp.get('high_risk_value', 0)):,.2f}")
            print(f"  Duplicate Exposure: ₹{float(exp.get('duplicate_exposure', 0)):,.2f}")
            print(f"  Unexplained Exposure: ₹{float(exp.get('unexplained_exposure', 0)):,.2f}")
            print(f"  Delayed Settlement Exposure: ₹{float(exp.get('delayed_settlement_exposure', 0)):,.2f}")
            print(f"  Fee Tax Mismatch Exposure: ₹{float(exp.get('fee_tax_mismatch_exposure', 0)):,.2f}")
        else:
            print(f"Error getting exposure: {response.status_code} - {response.text}")

        # Get settlement accounting
        response = await client.get(
            "http://localhost:8000/api/v1/controller/settlement/accounting",
            params={"run_id": "adversarial_eval_7333"}
        )
        if response.status_code == 200:
            settlement = response.json()
            print("\nSettlement Accounting:")
            print(f"  Gross Gateway Volume: ₹{float(settlement.get('gross_gateway_volume', 0)):,.2f}")
            print(f"  Total Deducted Fees: ₹{float(settlement.get('total_deducted_fees', 0)):,.2f}")
            print(f"  Total Deducted Taxes: ₹{float(settlement.get('total_deducted_taxes', 0)):,.2f}")
            print(f"  Total Refunded Amount: ₹{float(settlement.get('total_refunded_amount', 0)):,.2f}")
            print(f"  Expected Net Settlement: ₹{float(settlement.get('expected_net_settlement', 0)):,.2f}")
            print(f"  Actual Bank Settled Credits: ₹{float(settlement.get('actual_bank_settled_credits', 0)):,.2f}")
            print(f"  Net Settlement Variance: ₹{float(settlement.get('net_settlement_variance', 0)):,.2f}")
        else:
            print(f"Error getting settlement accounting: {response.status_code} - {response.text}")

asyncio.run(verify_financials())
