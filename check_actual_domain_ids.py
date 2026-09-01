"""
Check actual domain_transaction_ids in ORM to understand ID structure
"""
import asyncio
from sqlalchemy import select
from app.database.session import get_db_session_context
from app.database.models import Transaction, ReconciliationRun

async def check_domain_ids():
    """Check actual domain_transaction_ids in ORM"""
    async with get_db_session_context() as session:
        # Get the most recent run
        run_stmt = select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(1)
        run_result = await session.execute(run_stmt)
        run = run_result.scalar_one_or_none()
        
        if not run:
            print("No run found")
            return
        
        print(f"Run ID: {run.run_id}, ORM ID: {run.id}")
        
        # Get transactions for this run
        from app.database.models import ReconciliationItem
        item_stmt = select(ReconciliationItem.transaction_id).where(
            ReconciliationItem.run_id == run.id
        )
        item_result = await session.execute(item_stmt)
        txn_ids = item_result.scalars().all()
        
        # Get transaction details
        txn_stmt = select(Transaction).where(Transaction.id.in_(txn_ids))
        txn_result = await session.execute(txn_stmt)
        transactions = txn_result.scalars().all()
        
        print(f"\nTotal transactions: {len(transactions)}")
        
        # Sample domain_transaction_ids
        print("\nSample domain_transaction_ids (first 20):")
        for i, txn in enumerate(transactions[:20]):
            print(f"  {i+1}. {txn.domain_transaction_id} (source: {txn.source})")
        
        # Count by source
        from collections import Counter
        source_counts = Counter(txn.source for txn in transactions)
        print(f"\nTransactions by source: {dict(source_counts)}")
        
        # Check for EVAL_TXN pattern
        eval_txns = [txn for txn in transactions if "EVAL_TXN" in txn.domain_transaction_id]
        print(f"\nTransactions containing 'EVAL_TXN': {len(eval_txns)}")
        
        if eval_txns:
            print("Sample EVAL_TXN domain IDs:")
            for i, txn in enumerate(eval_txns[:10]):
                print(f"  {i+1}. {txn.domain_transaction_id} (source: {txn.source})")

asyncio.run(check_domain_ids())
