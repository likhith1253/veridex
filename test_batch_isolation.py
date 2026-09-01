import asyncio
from sqlalchemy import select
from app.database.session import get_db_session_context
from app.database.models import ReconciliationRun as ReconciliationRunORM
from app.services.finance_controller import FinanceController

async def test():
    async with get_db_session_context() as session:
        # Get all runs directly
        result = await session.execute(select(ReconciliationRunORM))
        runs = result.scalars().all()
        print(f'Total runs: {len(runs)}')
        for r in runs:
            print(f'Run: {r.run_id}, Gateway: {r.gateway_count}, Ledger: {r.ledger_count}, Bank: {r.bank_count}')
        
        fc = FinanceController(session)
        
        # Test batch isolation for adversarial_eval_7333
        print(f'\n=== Testing batch isolation for adversarial_eval_7333 ===')
        kpis = await fc.get_summary_kpis('adversarial_eval_7333')
        print(f'Total records: {kpis.total_records_processed}')
        print(f'Match rate: {kpis.match_rate}%')
        print(f'Unresolved: {kpis.unresolved_transactions}')
        
        # Test batch isolation for all runs (no run_id filter)
        print(f'\n=== Testing all runs (no filter) ===')
        all_kpis = await fc.get_summary_kpis(None)
        print(f'Total records: {all_kpis.total_records_processed}')
        print(f'Match rate: {all_kpis.match_rate}%')
        print(f'Unresolved: {all_kpis.unresolved_transactions}')

if __name__ == "__main__":
    asyncio.run(test())
