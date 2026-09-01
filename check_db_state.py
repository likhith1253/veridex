import asyncio
from app.database.session import get_db_session_context
from sqlalchemy import select
from app.database.models import ReconciliationRun

async def check_runs():
    async with get_db_session_context() as session:
        stmt = select(ReconciliationRun)
        result = await session.execute(stmt)
        runs = result.scalars().all()
        print(f'Total runs in database: {len(runs)}')
        for run in runs:
            print(f'Run ID: {run.run_id}, Status: {run.status}, Gateway: {run.gateway_count}, Ledger: {run.ledger_count}, Bank: {run.bank_count}')

if __name__ == "__main__":
    asyncio.run(check_runs())
