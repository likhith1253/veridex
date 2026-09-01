"""
Debug the reconciliation pipeline to understand why exceptions aren't being created.
"""
import asyncio
from generate_independent_adversarial import generate_adversarial_dataset
from app.database.session import get_db_session_context
from app.services.reconciliation import ReconciliationService
from app.database.repositories import (
    TransactionRepository,
    ReconciliationRepository,
    MatchRepository,
    DecisionRepository,
    ExceptionRepository,
    AuditRepository,
)
from app.matching.ml_scorer import MLScorer
from app.models.transaction import Transaction, TransactionSource

async def test():
    # Generate the adversarial dataset
    raw_transactions = generate_adversarial_dataset()
    
    # Convert to Transaction domain objects
    transactions = {
        TransactionSource.GATEWAY: [],
        TransactionSource.LEDGER: [],
        TransactionSource.BANK: []
    }
    
    for t in raw_transactions["gateway"]:
        transactions[TransactionSource.GATEWAY].append(Transaction(
            txn_id=t["txn_id"],
            source=TransactionSource.GATEWAY,
            reference_number=t["reference_number"],
            order_id=t["order_id"],
            amount=t["amount"],
            currency=t["currency"],
            timestamp=t["timestamp"],
            narration=t["narration"],
            fee=t["fee"],
            tax=t["tax"],
            status="completed"
        ))
    
    for t in raw_transactions["ledger"]:
        transactions[TransactionSource.LEDGER].append(Transaction(
            txn_id=t["txn_id"],
            source=TransactionSource.LEDGER,
            reference_number=t["reference_number"],
            order_id=t["order_id"],
            amount=t["amount"],
            currency=t["currency"],
            timestamp=t["timestamp"],
            narration=t["narration"],
            fee=t["fee"],
            tax=t["tax"],
            status="completed"
        ))
    
    for t in raw_transactions["bank"]:
        transactions[TransactionSource.BANK].append(Transaction(
            txn_id=t["txn_id"],
            source=TransactionSource.BANK,
            reference_number=t["reference_number"],
            order_id=t["order_id"],
            amount=t["amount"],
            currency=t["currency"],
            timestamp=t["timestamp"],
            narration=t["narration"],
            fee=t["fee"],
            tax=t["tax"],
            status="completed"
        ))
    
    print(f"Total transactions: {len(transactions[TransactionSource.GATEWAY]) + len(transactions[TransactionSource.LEDGER]) + len(transactions[TransactionSource.BANK])}")
    print(f"Gateway: {len(transactions[TransactionSource.GATEWAY])}")
    print(f"Ledger: {len(transactions[TransactionSource.LEDGER])}")
    print(f"Bank: {len(transactions[TransactionSource.BANK])}")
    
    # Run reconciliation
    async with get_db_session_context() as session:
        ml_scorer = MLScorer(model_type="xgboost")
        
        transaction_repo = TransactionRepository(session)
        reconciliation_repo = ReconciliationRepository(session)
        match_repo = MatchRepository(session)
        decision_repo = DecisionRepository(session)
        exception_repo = ExceptionRepository(session)
        audit_repo = AuditRepository(session)
        
        reconciliation_service = ReconciliationService(
            session=session,
            transaction_repo=transaction_repo,
            reconciliation_repo=reconciliation_repo,
            match_repo=match_repo,
            decision_repo=decision_repo,
            exception_repo=exception_repo,
            audit_repo=audit_repo,
            ml_scorer=ml_scorer,
            investigation_service=None,
        )
        
        summary = await reconciliation_service.run_reconciliation(
            transactions_by_source=transactions,
            run_id="debug_pipeline_test"
        )
        
        print(f"\nReconciliation Summary:")
        print(f"Run ID: {summary.run_id}")
        print(f"Total transactions: {summary.total_transactions}")
        print(f"Deterministic matches: {summary.deterministic_matches}")
        print(f"ML proposals: {summary.ml_proposals}")
        print(f"Manual reviews: {summary.manual_reviews}")
        print(f"Ambiguous: {summary.ambiguous}")
        print(f"Unresolved: {summary.unresolved}")
        print(f"Exceptions created: {summary.exceptions_created}")
        print(f"Completed successfully: {summary.completed_successfully}")

if __name__ == "__main__":
    asyncio.run(test())
