import asyncio
from sqlalchemy import select, text
from app.database.session import get_db_session_context
from app.database.models import ReconciliationRun

async def get_latest_run():
    async with get_db_session_context() as session:
        # Get the most recent run
        stmt = select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(5)
        result = await session.execute(stmt)
        runs = result.scalars().all()
        
        print("Recent reconciliation runs:")
        for run in runs:
            print(f"  ID: {run.id}, run_id: {run.run_id}, status: {run.status}, created: {run.created_at}")
        
        if runs:
            return runs[0].run_id
        return None

latest_run = asyncio.run(get_latest_run())
print(f"\nLatest run_id: {latest_run}")
