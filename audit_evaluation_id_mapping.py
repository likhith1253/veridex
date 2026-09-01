"""
Comprehensive Evaluation ID Mapping Audit
Verifies the complete identity chain from ground truth to exceptions
to distinguish evaluator defects from application defects
"""
import asyncio
import json
from collections import defaultdict, Counter
from typing import Dict, List, Set, Optional, Tuple
from sqlalchemy import select
from app.database.session import get_db_session_context
from app.database.models import Transaction, ReconciliationRun, Exception as ExceptionORM
import httpx

BASE_URL = "http://localhost:8000"

async def get_ground_truth() -> Dict:
    """Load ground truth from file"""
    with open('private_ground_truth.json', 'r') as f:
        return json.load(f)

async def get_current_run_id() -> Optional[str]:
    """Get the most recent run_id from database"""
    async with get_db_session_context() as session:
        stmt = select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        return run.run_id if run else None

async def get_api_exceptions(run_id: str) -> List[Dict]:
    """Get exceptions from API /exceptions endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/controller/exceptions",
            params={"run_id": run_id, "page_size": 200}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("exceptions", [])
        return []

async def get_orm_transactions(run_id: str) -> Dict[str, str]:
    """Get ORM transaction UUIDs directly from database"""
    async with get_db_session_context() as session:
        # Get the ORM run UUID
        run_stmt = select(ReconciliationRun).where(
            (ReconciliationRun.id == run_id) | (ReconciliationRun.run_id == run_id)
        )
        run_result = await session.execute(run_stmt)
        run_obj = run_result.scalar_one_or_none()
        
        if not run_obj:
            print(f"ERROR: Run {run_id} not found in database")
            return {}
        
        # Get all transactions for this run via reconciliation_items
        from app.database.models import ReconciliationItem
        item_stmt = select(ReconciliationItem.transaction_id).where(
            ReconciliationItem.run_id == run_obj.id
        )
        item_result = await session.execute(item_stmt)
        txn_ids = item_result.scalars().all()
        
        # Get transaction details
        txn_stmt = select(Transaction).where(Transaction.id.in_(txn_ids))
        txn_result = await session.execute(txn_stmt)
        transactions = txn_result.scalars().all()
        
        # Build mapping: domain_transaction_id -> ORM UUID
        mapping = {}
        for txn in transactions:
            if txn.domain_transaction_id:
                mapping[txn.domain_transaction_id] = str(txn.id)
        
        return mapping

async def get_orm_exceptions(run_id: str) -> List[Dict]:
    """Get exceptions directly from ORM"""
    async with get_db_session_context() as session:
        # Get the ORM run UUID
        run_stmt = select(ReconciliationRun).where(
            (ReconciliationRun.id == run_id) | (ReconciliationRun.run_id == run_id)
        )
        run_result = await session.execute(run_stmt)
        run_obj = run_result.scalar_one_or_none()
        
        if not run_obj:
            return []
        
        # Get exceptions for this run
        exc_stmt = select(ExceptionORM).where(ExceptionORM.run_id == run_obj.id)
        exc_result = await session.execute(exc_stmt)
        exceptions = exc_result.scalars().all()
        
        result = []
        for exc in exceptions:
            result.append({
                "id": str(exc.id),
                "transaction_id": str(exc.transaction_id) if exc.transaction_id else None,
                "exception_category": exc.exception_category,
                "status": exc.status,
                "financial_exposure": str(exc.financial_exposure) if exc.financial_exposure else None,
            })
        
        return result

async def get_api_exceptions(run_id: str) -> List[Dict]:
    """Get exceptions from API /exceptions endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/controller/exceptions",
            params={"run_id": run_id, "page_size": 200}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("exceptions", [])
        return []

def should_be_exception(ground_truth_record: Dict) -> bool:
    """
    Canonical function to determine if a ground truth record should produce an exception.
    This is the SINGLE source of truth for expected exception classification.
    """
    expected_outcome = ground_truth_record.get("expected_outcome", "")
    
    # Explicit exception outcomes
    exception_outcomes = {
        "amount_mismatch_exception",
        "settlement_variance_exception", 
        "missing_source_exception",
        "duplicate_exception",
        "fee_mismatch_exception",
        "tax_mismatch_exception",
        "delayed_settlement_exception",
        "partial_match_exception",
        "missing_fields_exception",
        "complex_mismatch_exception",
    }
    
    # Also check for keywords in expected_outcome
    exception_keywords = {"exception", "unresolved", "risk", "review"}
    
    if expected_outcome in exception_outcomes:
        return True
    
    if any(keyword in expected_outcome.lower() for keyword in exception_keywords):
        return True
    
    return False

async def audit_id_mapping():
    """Main audit function"""
    print("=" * 80)
    print("EVALUATION ID MAPPING AUDIT")
    print("=" * 80)
    
    # Step 1: Get current run_id
    run_id = await get_current_run_id()
    print(f"\nCurrent run_id: {run_id}")
    
    if not run_id:
        print("ERROR: No run_id found")
        return
    
    # Step 2: Load ground truth
    ground_truth = await get_ground_truth()
    print(f"Ground truth transactions: {len(ground_truth)}")
    
    # Step 3: Get ORM transaction mapping (skip API since endpoint doesn't exist)
    orm_mapping = await get_orm_transactions(run_id)
    print(f"ORM transaction mapping: {len(orm_mapping)} entries")
    
    # Step 4: Get API exceptions
    api_exceptions = await get_api_exceptions(run_id)
    print(f"API exceptions: {len(api_exceptions)}")
    
    # Step 5: Get ORM exceptions
    orm_exceptions = await get_orm_exceptions(run_id)
    print(f"ORM exceptions: {len(orm_exceptions)}")
    
    # Step 5: Build exception transaction ID set (ORM UUIDs)
    exception_txn_ids = {exc.get("transaction_id") for exc in orm_exceptions if exc.get("transaction_id")}
    print(f"Exception transaction IDs (ORM UUIDs): {len(exception_txn_ids)}")
    
    # Step 6: Verify ID mapping chain for each ground truth transaction
    print("\n" + "=" * 80)
    print("ID MAPPING CHAIN VERIFICATION")
    print("=" * 80)
    
    mapping_results = []
    successfully_mapped_txns = 0
    successfully_mapped_exceptions = 0
    
    for logical_id, gt_record in ground_truth.items():
        # Get source IDs from ground truth
        gateway_id = gt_record.get("gateway_id")
        ledger_id = gt_record.get("ledger_id")
        bank_id = gt_record.get("bank_id")
        
        # The ORM has source-specific domain_transaction_ids (EVAL_GW_XXXX, EVAL_LD_XXXX, EVAL_BK_XXXX)
        source_ids = [gateway_id, ledger_id, bank_id]
        source_ids = [sid for sid in source_ids if sid]  # Filter out None
        
        # Check if any source ID maps to ORM UUID
        orm_uuids = [orm_mapping.get(source_id) for source_id in source_ids]
        orm_uuids = [uuid for uuid in orm_uuids if uuid]  # Filter out None
        
        # Use the first ORM UUID found (they should all map to the same logical transaction)
        orm_uuid = orm_uuids[0] if orm_uuids else None
        
        # Check if ANY ORM UUID has an exception
        has_exception = any(uuid in exception_txn_ids for uuid in orm_uuids) if orm_uuids else False
        
        # Determine if this should be an exception
        should_except = should_be_exception(gt_record)
        
        result = {
            "logical_id": logical_id,
            "source_ids": source_ids,
            "orm_uuids": orm_uuids,
            "orm_uuid": orm_uuid,
            "has_exception": has_exception,
            "should_except": should_except,
            "expected_outcome": gt_record.get("expected_outcome"),
            "scenario": gt_record.get("scenario"),
        }
        
        mapping_results.append(result)
        
        if orm_uuid:
            successfully_mapped_txns += 1
            if should_except and has_exception:
                successfully_mapped_exceptions += 1
    
    # Step 7: Print detailed mapping statistics
    print(f"\nSuccessfully mapped transactions (ground_truth -> ORM): {successfully_mapped_txns}/{len(ground_truth)}")
    print(f"Successfully mapped exceptions (ground_truth -> ORM -> exception): {successfully_mapped_exceptions}/{len(ground_truth)}")
    
    # Step 8: Calculate true expected exceptions
    expected_exceptions = sum(1 for r in mapping_results if r["should_except"])
    detected_exceptions = sum(1 for r in mapping_results if r["should_except"] and r["has_exception"])
    
    print(f"\nExpected exceptions (canonical): {expected_exceptions}")
    print(f"Detected exceptions: {detected_exceptions}")
    
    if expected_exceptions > 0:
        true_coverage = detected_exceptions / expected_exceptions * 100
        print(f"True coverage: {true_coverage:.1f}%")
    else:
        print("True coverage: N/A (no expected exceptions)")
    
    # Step 9: Identify mapping failures
    print("\n" + "=" * 80)
    print("MAPPING FAILURES")
    print("=" * 80)
    
    orm_mapping_failures = [r for r in mapping_results if not r["orm_uuid"]]
    
    print(f"\nORM mapping failures (ground_truth -> ORM): {len(orm_mapping_failures)}")
    for failure in orm_mapping_failures[:5]:
        print(f"  - {failure['logical_id']}: {failure['scenario']} (source_ids: {failure['source_ids']})")
    if len(orm_mapping_failures) > 5:
        print(f"  ... and {len(orm_mapping_failures) - 5} more")
    
    # Step 10: Print detailed chain for sample transactions
    print("\n" + "=" * 80)
    print("SAMPLE ID CHAINS (first 10)")
    print("=" * 80)
    
    for i, result in enumerate(mapping_results[:10]):
        print(f"\n{i+1}. {result['logical_id']} ({result['scenario']})")
        print(f"   Ground truth ID: {result['logical_id']}")
        print(f"   Source IDs: {result['source_ids']}")
        print(f"   ORM UUIDs: {result['orm_uuids']}")
        print(f"   Primary ORM UUID: {result['orm_uuid']}")
        print(f"   Has exception: {result['has_exception']}")
        print(f"   Should except: {result['should_except']}")
        print(f"   Expected outcome: {result['expected_outcome']}")
        
        # Print chain status
        chain_parts = []
        if result['orm_uuid']:
            chain_parts.append("ORM")
        if result['has_exception']:
            chain_parts.append("EXCEPTION")
        
        chain_status = " -> ".join(chain_parts) if chain_parts else "BROKEN"
        print(f"   Chain: {result['logical_id']} -> {chain_status}")
    
    # Step 11: Final assessment
    print("\n" + "=" * 80)
    print("FINAL ASSESSMENT")
    print("=" * 80)
    
    evaluator_defects = []
    application_defects = []
    
    if len(orm_mapping_failures) > 0:
        evaluator_defects.append(f"ORM mapping failure: {len(orm_mapping_failures)} ground truth IDs not mapped to ORM UUIDs")
    
    # Check for expected exceptions that weren't detected BUT have valid mapping
    missed_with_valid_mapping = [
        r for r in mapping_results 
        if r["should_except"] and not r["has_exception"] and r["orm_uuid"]
    ]
    
    if len(missed_with_valid_mapping) > 0:
        application_defects.append(f"Missed exceptions with valid mapping: {len(missed_with_valid_mapping)}")
    
    print(f"\nCurrent run ID: {run_id}")
    print(f"Ground truth count: {len(ground_truth)}")
    print(f"ORM transaction count: {len(orm_mapping)}")
    print(f"API exception count: {len(api_exceptions)}")
    print(f"ORM exception count: {len(orm_exceptions)}")
    print(f"Successfully mapped transaction count: {successfully_mapped_txns}")
    print(f"Successfully mapped exception count: {successfully_mapped_exceptions}")
    print(f"True expected exceptions: {expected_exceptions}")
    print(f"True detected exceptions: {detected_exceptions}")
    print(f"True coverage: {true_coverage:.1f}%" if expected_exceptions > 0 else "True coverage: N/A")
    
    print(f"\nEvaluator defects discovered: {len(evaluator_defects)}")
    for defect in evaluator_defects:
        print(f"  - {defect}")
    
    print(f"\nApplication defects discovered: {len(application_defects)}")
    for defect in application_defects:
        print(f"  - {defect}")
    
    # Save detailed results
    output = {
        "run_id": run_id,
        "ground_truth_count": len(ground_truth),
        "orm_transaction_count": len(orm_mapping),
        "api_exception_count": len(api_exceptions),
        "orm_exception_count": len(orm_exceptions),
        "successfully_mapped_transactions": successfully_mapped_txns,
        "successfully_mapped_exceptions": successfully_mapped_exceptions,
        "true_expected_exceptions": expected_exceptions,
        "true_detected_exceptions": detected_exceptions,
        "true_coverage": true_coverage if expected_exceptions > 0 else None,
        "evaluator_defects": evaluator_defects,
        "application_defects": application_defects,
        "orm_mapping_failures": len(orm_mapping_failures),
        "missed_exceptions_with_valid_mapping": len(missed_with_valid_mapping),
        "detailed_mapping_results": mapping_results,
    }
    
    with open("evaluation_id_mapping_audit.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nDetailed results saved to evaluation_id_mapping_audit.json")

if __name__ == "__main__":
    asyncio.run(audit_id_mapping())
