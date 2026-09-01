"""
Prove what exception.transaction_id actually contains
Compare ORM UUID vs domain_transaction_id
"""
import asyncio
from sqlalchemy import select
from app.database.session import get_db_session_context
from app.database.models import Transaction, Exception as ExceptionORM, ReconciliationRun

async def prove_exception_id_namespace():
    """Check what exception.transaction_id actually contains"""
    async with get_db_session_context() as session:
        # Get the most recent run
        run_stmt = select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(1)
        run_result = await session.execute(run_stmt)
        run = run_result.scalar_one_or_none()
        
        if not run:
            print("No run found")
            return
        
        print(f"Run ID: {run.run_id}, ORM ID: {run.id}")
        
        # Get exceptions for this run
        exc_stmt = select(ExceptionORM).where(ExceptionORM.run_id == run.id).limit(5)
        exc_result = await session.execute(exc_stmt)
        exceptions = exc_result.scalars().all()
        
        print(f"\nAnalyzing {len(exceptions)} exceptions:")
        
        for i, exc in enumerate(exceptions, 1):
            print(f"\n{i}. Exception ID: {exc.id}")
            print(f"   Exception.transaction_id: {exc.transaction_id}")
            print(f"   Exception category: {exc.exception_category}")
            
            # Get the transaction if we have the ID
            if exc.transaction_id:
                try:
                    txn_stmt = select(Transaction).where(Transaction.id == exc.transaction_id)
                    txn_result = await session.execute(txn_stmt)
                    txn = txn_result.scalar_one_or_none()
                    
                    if txn:
                        print(f"   Transaction.id (ORM UUID): {txn.id}")
                        print(f"   Transaction.domain_transaction_id: {txn.domain_transaction_id}")
                        print(f"   Transaction.source: {txn.source}")
                        print(f"   Transaction.amount: {txn.amount}")
                    else:
                        print(f"   Transaction not found by ID")
                except Exception as e:
                    print(f"   Error fetching transaction: {e}")
            else:
                print(f"   Exception.transaction_id is None")

asyncio.run(prove_exception_id_namespace())
