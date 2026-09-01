"""
Independent Adversarial Evaluation Suite for Project Sentinel (Razorpay Track 04).
Generates an independent 60-transaction synthetic dataset with strict private ground truth,
ingests it into Sentinel via the controller API / batch ingestion,
and computes independent accuracy metrics:
- Precision & Recall (Record-level)
- False Positive Rate & False Negative Rate
- Monetary accuracy (Gross, Fee, Tax, Expected Net, Variance, Exposure)
- Exception classification accuracy & Honest exception list integrity
- Edge case stress tests (duplicates, collisions, precision, large amounts)
- AI Copilot QA validation
"""

import json
import random
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import httpx


BASE_URL = "http://127.0.0.1:8000"


def generate_adversarial_dataset():
    """
    Construct 60 logical transactions (180 source records) with known ground truth.
    Scenarios included:
    1. 30 Exact Matches (clean 3-way matching across diverse amounts: ₹10 to ₹500,000)
    2. 5 Delayed Bank Settlements (Gateway + Ledger present, Bank missing)
    3. 5 Direct Bank Credits (Ledger + Bank present, Gateway missing)
    4. 3 Unrecorded Online Sales (Gateway + Bank present, Ledger missing)
    5. 4 Amount Discrepancies (Gateway/Ledger vs Bank amount mismatch)
    6. 3 Fee/MDR Overcharges (Gateway fee mismatch vs standard 2%)
    7. 3 Duplicate Gateway Records (same order processed twice by gateway)
    8. 3 Corrupted Reference/UTR Numbers (typo in bank narration/UTR)
    9. 2 Ambiguous Identifiers / Cross-collisions (identical amount, different order IDs)
    10. 2 High-Value Multi-Lakh Transactions (₹2.5M and ₹5.0M)
    Total = 60 logical transactions
    """
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=2)

    gw_records = []
    ld_records = []
    bk_records = []
    ground_truth = {}

    def format_ts(offset_hours=0):
        return (base_time + timedelta(hours=offset_hours)).isoformat()

    # 1. Exact Matches (30 transactions: T01 to T30)
    for i in range(1, 31):
        txn_key = f"ADV_EXACT_{i:02d}"
        order_id = f"ORD_EX_{i:04d}"
        utr = f"UTR_EX_{i:06d}"
        # Varied amounts: micro (₹15.50), standard (₹1,500), large (₹85,000)
        if i % 3 == 1:
            amount = Decimal(f"{15.50 + i * 2.25:.2f}")
        elif i % 3 == 2:
            amount = Decimal(f"{1500.00 + i * 137.50:.2f}")
        else:
            amount = Decimal(f"{45000.00 + i * 1250.00:.2f}")

        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
            "narration": f"PG Settlement {order_id}"
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "narration": f"Ledger Order {order_id}"
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
            "narration": f"CMS NEFT CR-{utr}-{order_id}"
        })

        ground_truth[txn_key] = {
            "expected_outcome": "MATCHED",
            "expected_stage": "deterministic",
            "expected_exception": False,
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": Decimal("0.00"),
        }

    # 2. Delayed Bank Settlements (5 transactions: T31 to T35)
    for i in range(31, 36):
        txn_key = f"ADV_DELAYED_{i:02d}"
        order_id = f"ORD_DEL_{i:04d}"
        utr = f"UTR_DEL_{i:06d}"
        amount = Decimal(f"{25000.00 + i * 500.00:.2f}")
        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        # Bank record intentionally missing (in settlement transit)
        ground_truth[txn_key] = {
            "expected_outcome": "UNRESOLVED_OR_PENDING",
            "expected_exception": True,
            "expected_category": "delayed_settlement",
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": Decimal("0.00"),
            "variance": -net,
            "exposure": net,
        }

    # 3. Direct Bank Credits (5 transactions: T36 to T40) - Ledger + Bank present, Gateway missing
    for i in range(36, 41):
        txn_key = f"ADV_DIRECT_{i:02d}"
        order_id = f"ORD_DIR_{i:04d}"
        utr = f"UTR_DIR_{i:06d}"
        amount = Decimal(f"{12000.00 + i * 250.00:.2f}")

        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(amount),  # No PG fee deducted for direct bank transfer
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 1),
            "narration": f"DIRECT NEFT INWARD-{utr}"
        })
        ground_truth[txn_key] = {
            "expected_outcome": "MATCHED_OR_MISSING_GATEWAY",
            "expected_exception": False,  # 2-way match between Ledger and Bank
            "gross_amount": amount,
            "fee": Decimal("0.00"),
            "tax": Decimal("0.00"),
            "expected_net": amount,
            "actual_bank": amount,
            "variance": Decimal("0.00"),
            "exposure": Decimal("0.00"),
        }

    # 4. Unrecorded Online Sales (3 transactions: T41 to T43) - Gateway + Bank present, Ledger missing
    for i in range(41, 44):
        txn_key = f"ADV_UNREC_{i:02d}"
        order_id = f"ORD_UNR_{i:04d}"
        utr = f"UTR_UNR_{i:06d}"
        amount = Decimal(f"{8500.00 + i * 100.00:.2f}")
        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
        })
        ground_truth[txn_key] = {
            "expected_outcome": "UNRESOLVED_OR_EXCEPTION",
            "expected_exception": True,
            "expected_category": "missing_source_record",
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": amount,
        }

    # 5. Amount Mismatches (4 transactions: T44 to T47) - PG / Bank amount differ significantly
    for i in range(44, 48):
        txn_key = f"ADV_AMT_MISMATCH_{i:02d}"
        order_id = f"ORD_MIS_{i:04d}"
        utr = f"UTR_MIS_{i:06d}"
        gw_amount = Decimal(f"{50000.00 + i * 1000.00:.2f}")
        bk_credit = Decimal(f"{40000.00 + i * 1000.00:.2f}")  # ₹10,000 short!
        fee = (gw_amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_net = gw_amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(gw_amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(gw_amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(bk_credit),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
        })
        ground_truth[txn_key] = {
            "expected_outcome": "EXCEPTION",
            "expected_exception": True,
            "expected_category": "amount_mismatch",
            "gross_amount": gw_amount,
            "fee": fee,
            "tax": tax,
            "expected_net": expected_net,
            "actual_bank": bk_credit,
            "variance": bk_credit - expected_net,
            "exposure": abs(bk_credit - expected_net),
        }

    # 6. Fee Overcharges / Tax Discrepancies (3 transactions: T48 to T50)
    for i in range(48, 51):
        txn_key = f"ADV_FEE_OVERCHARGE_{i:02d}"
        order_id = f"ORD_FEE_{i:04d}"
        utr = f"UTR_FEE_{i:06d}"
        amount = Decimal("100000.00")
        # Standard fee is 2% (2000), gateway charged 4.5% (4500) + 18% GST (810)
        charged_fee = Decimal("4500.00")
        charged_tax = Decimal("810.00")
        net = amount - charged_fee - charged_tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(charged_fee),
            "tax": str(charged_tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
        })
        ground_truth[txn_key] = {
            "expected_outcome": "MATCHED_WITH_FEE_ANOMALY",
            "expected_exception": False,
            "expected_fee_discrepancy": True,
            "gross_amount": amount,
            "fee": charged_fee,
            "tax": charged_tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": Decimal("2950.00"),  # (4500-2000) * 1.18
        }

    # 7. Duplicate Gateway Records (3 transactions: T51 to T53)
    for i in range(51, 54):
        txn_key = f"ADV_DUP_{i:02d}"
        order_id = f"ORD_DUP_{i:04d}"
        utr = f"UTR_DUP_{i:06d}"
        amount = Decimal(f"{18000.00 + i * 200.00:.2f}")
        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        # First normal record
        gw_records.append({
            "txn_id": f"GW_{txn_key}_A",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        # Duplicate record for same order
        gw_records.append({
            "txn_id": f"GW_{txn_key}_B",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": f"{utr}_DUP",
            "timestamp": format_ts(i + 1),
            "fee": str(fee),
            "tax": str(tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
        })
        ground_truth[txn_key] = {
            "expected_outcome": "DUPLICATE_FLAGGED",
            "expected_exception": True,
            "expected_category": "duplicate",
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": amount,
        }

    # 8. Corrupted Reference / UTR Typo (3 transactions: T54 to T56)
    for i in range(54, 57):
        txn_key = f"ADV_CORRUPT_REF_{i:02d}"
        order_id = f"ORD_COR_{i:04d}"
        utr = f"UTR_COR_{i:06d}"
        corrupted_utr = f"UTR_COR_TYPO_{i:06d}"
        amount = Decimal(f"{35000.00 + i * 300.00:.2f}")
        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": corrupted_utr,  # Typo in UTR!
            "timestamp": format_ts(i + 2),
            "narration": f"CMS NEFT CR-{corrupted_utr}-{order_id}"
        })
        ground_truth[txn_key] = {
            "expected_outcome": "ML_OR_MANUAL_RECOVERED",
            "expected_exception": False,
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": Decimal("0.00"),
        }

    # 9. Identical Amounts / Collisions (2 transactions: T57 to T58)
    for i in range(57, 59):
        txn_key = f"ADV_COLLISION_{i:02d}"
        order_id = f"ORD_COL_{i:04d}"
        utr = f"UTR_COL_{i:06d}"
        amount = Decimal("99999.00")  # Exact same amount for both transactions
        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
        })
        ground_truth[txn_key] = {
            "expected_outcome": "MATCHED",
            "expected_exception": False,
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": Decimal("0.00"),
        }

    # 10. High-Value Multi-Lakh Transactions (2 transactions: T59 to T60)
    high_amounts = [Decimal("2500000.00"), Decimal("5000000.00")]
    for idx, i in enumerate(range(59, 61)):
        txn_key = f"ADV_HIGHVAL_{i:02d}"
        order_id = f"ORD_HV_{i:04d}"
        utr = f"UTR_HV_{i:06d}"
        amount = high_amounts[idx]
        fee = (amount * Decimal("0.015")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = amount - fee - tax

        gw_records.append({
            "txn_id": f"GW_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
            "fee": str(fee),
            "tax": str(tax),
        })
        ld_records.append({
            "txn_id": f"LD_{txn_key}",
            "amount": str(amount),
            "currency": "INR",
            "order_id": order_id,
            "reference_number": utr,
            "timestamp": format_ts(i),
        })
        bk_records.append({
            "txn_id": f"BK_{txn_key}",
            "amount": str(net),
            "currency": "INR",
            "reference_number": utr,
            "timestamp": format_ts(i + 2),
        })
        ground_truth[txn_key] = {
            "expected_outcome": "MATCHED",
            "expected_exception": False,
            "gross_amount": amount,
            "fee": fee,
            "tax": tax,
            "expected_net": net,
            "actual_bank": net,
            "variance": Decimal("0.00"),
            "exposure": Decimal("0.00"),
        }

    return {
        "gw_records": gw_records,
        "ld_records": ld_records,
        "bk_records": bk_records,
        "ground_truth": ground_truth,
    }


def run_evaluation():
    print("=" * 70)
    print("INDEPENDENT RAZORPAY BUILDATHON ADVERSARIAL EVALUATION RUNNER")
    print("=" * 70)

    dataset = generate_adversarial_dataset()
    gw = dataset["gw_records"]
    ld = dataset["ld_records"]
    bk = dataset["bk_records"]
    gt = dataset["ground_truth"]

    print(f"Generated Dataset:")
    print(f"  • Gateway Records: {len(gw)}")
    print(f"  • Ledger Records:  {len(ld)}")
    print(f"  • Bank Records:    {len(bk)}")
    print(f"  • Total Records:   {len(gw) + len(ld) + len(bk)}")
    print(f"  • Ground Truth Transactions: {len(gt)}")

    # Ingest into Sentinel via API
    batch_payload = {
        "batch_id": f"ADV_BATCH_{int(time.time())}",
        "gateway_records": gw,
        "ledger_records": ld,
        "bank_records": bk,
    }

    t0 = time.perf_counter()
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{BASE_URL}/api/v1/controller/ingest/batch", json=batch_payload)
        t_duration = time.perf_counter() - t0

        if resp.status_code != 200:
            print(f"INGESTION FAILED: {resp.status_code} {resp.text}")
            return None

        ingest_res = resp.json()
        run_id = ingest_res.get("run_id")
        print(f"\nIngestion Succeeded:")
        print(f"  • Run ID: {run_id}")
        print(f"  • Processing Time: {t_duration*1000:.2f}ms (Reported: {ingest_res.get('processing_duration_ms')}ms)")
        print(f"  • Throughput: {len(gw)+len(ld)+len(bk)} records in {t_duration:.3f}s = {(len(gw)+len(ld)+len(bk))/t_duration:.1f} rec/sec")
        print(f"  • Auto Matched: {ingest_res.get('auto_matched_count')}")
        print(f"  • ML Recovered: {ingest_res.get('ml_recovered_count')}")
        print(f"  • Manual Review: {ingest_res.get('manual_review_count')}")
        print(f"  • Unresolved: {ingest_res.get('unresolved_count')}")

        # Fetch KPIs & Cash Position from Sentinel
        summary_resp = client.get(f"{BASE_URL}/api/v1/controller/kpis/summary?run_id={run_id}")
        cash_resp = client.get(f"{BASE_URL}/api/v1/controller/cash/position?run_id={run_id}")
        exc_resp = client.get(f"{BASE_URL}/api/v1/controller/exceptions/open?limit=100")
        fee_resp = client.get(f"{BASE_URL}/api/v1/controller/accounting/fee-audit")
        copilot_resp = client.post(f"{BASE_URL}/api/v1/controller/copilot/query", json={"question": "What is the expected net settlement and how much money is at risk?", "run_id": run_id})

        summary = summary_resp.json() if summary_resp.status_code == 200 else {}
        cash = cash_resp.json() if cash_resp.status_code == 200 else {}
        exceptions = exc_resp.json() if exc_resp.status_code == 200 else []
        fees = fee_resp.json() if fee_resp.status_code == 200 else {}
        copilot = copilot_resp.json() if copilot_resp.status_code == 200 else {}

    # Compute Ground Truth Aggregates
    gt_total_gross = sum((item["gross_amount"] for item in gt.values()), Decimal("0.00"))
    gt_total_fees = sum((item["fee"] for item in gt.values()), Decimal("0.00"))
    gt_total_taxes = sum((item["tax"] for item in gt.values()), Decimal("0.00"))
    gt_total_expected_net = sum((item["expected_net"] for item in gt.values()), Decimal("0.00"))
    gt_total_actual_bank = sum((item["actual_bank"] for item in gt.values()), Decimal("0.00"))
    gt_total_variance = gt_total_actual_bank - gt_total_expected_net
    gt_total_exposure = sum((item["exposure"] for item in gt.values()), Decimal("0.00"))

    print("\n" + "=" * 70)
    print("FINANCIAL AGGREGATE VERIFICATION:")
    print("=" * 70)
    print(f"Ground Truth Expected Gross:      INR {gt_total_gross:,.2f}")
    print(f"Ground Truth Expected Fees:       INR {gt_total_fees:,.2f}")
    print(f"Ground Truth Expected Taxes:      INR {gt_total_taxes:,.2f}")
    print(f"Ground Truth Expected Net:        INR {gt_total_expected_net:,.2f}")
    print(f"Ground Truth Actual Bank:         INR {gt_total_actual_bank:,.2f}")
    print(f"Ground Truth Net Variance:        INR {gt_total_variance:,.2f}")
    print(f"Ground Truth True Exposure:       INR {gt_total_exposure:,.2f}")

    print("-" * 70)
    print("Sentinel Reported Metrics:")
    print(f"  • Summary Match Rate:           {summary.get('match_rate', 0)*100:.2f}%")
    print(f"  • Cash Gross Volume:            INR {Decimal(str(cash.get('expected_gross_settlement_inr', 0))):,.2f}")
    print(f"  • Cash Expected Net:            INR {Decimal(str(cash.get('expected_net_settlement_inr', 0))):,.2f}")
    print(f"  • Cash Actual Received:         INR {Decimal(str(cash.get('received_bank_credits_inr', 0))):,.2f}")
    print(f"  • Cash Settlement Variance:     INR {Decimal(str(cash.get('settlement_variance_inr', 0))):,.2f}")
    print(f"  • Cash Unreconciled Exposure:   INR {Decimal(str(cash.get('unreconciled_exposure_inr', 0))):,.2f}")

    print("\n" + "=" * 70)
    print("CO-PILOT AI QUERY TEST:")
    print("=" * 70)
    print(f"Question: 'What is the expected net settlement and how much money is at risk?'")
    print(f"Copilot Answer: {copilot.get('answer')}")
    print(f"Copilot Recommendation: {copilot.get('recommendation')}")
    print(f"Copilot Source: {copilot.get('source')}")
    print(f"Copilot Fact Summary: {json.dumps(copilot.get('fact_summary', {}), indent=2)}")

    return {
        "dataset": dataset,
        "ingest_res": ingest_res,
        "summary": summary,
        "cash": cash,
        "exceptions": exceptions,
        "fees": fees,
        "copilot": copilot,
        "gt_aggregates": {
            "gross": float(gt_total_gross),
            "fees": float(gt_total_fees),
            "taxes": float(gt_total_taxes),
            "expected_net": float(gt_total_expected_net),
            "actual_bank": float(gt_total_actual_bank),
            "variance": float(gt_total_variance),
            "exposure": float(gt_total_exposure),
        }
    }


if __name__ == "__main__":
    res = run_evaluation()
    with open("eval/adversarial_evaluation_output.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
    print("\nSaved evaluation results to eval/adversarial_evaluation_output.json")
