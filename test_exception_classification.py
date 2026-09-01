import asyncio
from sqlalchemy import select
from app.database.session import get_db_session_context
from app.database.models import ReconciliationRun as ReconciliationRunORM, Exception as ExceptionORM

async def test():
    async with get_db_session_context() as session:
        # Get the run ORM directly
        result = await session.execute(
            select(ReconciliationRunORM).where(ReconciliationRunORM.run_id == 'adversarial_eval_7333')
        )
        run = result.scalar_one_or_none()
        
        if run:
            print(f'Run found: {run.run_id}')
            print(f'Run ORM ID: {run.id}')
            
            # Get exceptions for this run
            exc_result = await session.execute(
                select(ExceptionORM).where(ExceptionORM.run_id == run.id)
            )
            exceptions = exc_result.scalars().all()
            
            print(f'\nTotal exceptions for run: {len(exceptions)}')
            
            for exc in exceptions:
                print(f'\nException ID: {exc.id}')
                print(f'Category: {exc.exception_category}')
                print(f'Category type: {type(exc.exception_category)}')
                print(f'Status: {exc.status}')
                print(f'Explanation: {exc.explanation}')
                print(f'Financial exposure: {exc.financial_exposure}')
                print(f'Recommended action: {exc.recommended_action}')
        else:
            print('Run not found')

if __name__ == "__main__":
    asyncio.run(test())
