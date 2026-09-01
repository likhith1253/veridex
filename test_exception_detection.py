import asyncio
from sqlalchemy import select
from app.database.session import get_db_session_context
from app.database.models import ReconciliationRun as ReconciliationRunORM, Decision as DecisionORM, Match as MatchORM, Exception as ExceptionORM

async def test():
    async with get_db_session_context() as session:
        # Get the run
        result = await session.execute(
            select(ReconciliationRunORM).where(ReconciliationRunORM.run_id == 'adversarial_eval_7333')
        )
        run = result.scalar_one_or_none()
        
        if run:
            print(f'Run found: {run.run_id}')
            print(f'Run ORM ID: {run.id}')
            print(f'Gateway count: {run.gateway_count}')
            print(f'Ledger count: {run.ledger_count}')
            print(f'Bank count: {run.bank_count}')
            print(f'Match count: {run.match_count}')
            print(f'Exception count: {run.exception_count}')
            
            # Get all decisions for this run
            dec_result = await session.execute(
                select(DecisionORM).where(DecisionORM.run_id == run.id)
            )
            decisions = dec_result.scalars().all()
            
            print(f'\nTotal decisions: {len(decisions)}')
            
            # Count by action
            from collections import Counter
            action_counts = Counter()
            for dec in decisions:
                action_counts[dec.decision_action] += 1
            
            print('\nDecision action breakdown:')
            for action, count in action_counts.items():
                print(f'  {action}: {count}')
            
            # Get all matches for this run
            match_result = await session.execute(
                select(MatchORM).where(MatchORM.run_id == run.id)
            )
            matches = match_result.scalars().all()
            
            print(f'\nTotal matches: {len(matches)}')
            
            # Count by match type
            match_type_counts = Counter()
            for match in matches:
                match_type_counts[match.match_type] += 1
            
            print('\nMatch type breakdown:')
            for match_type, count in match_type_counts.items():
                print(f'  {match_type}: {count}')
            
            # Get all exceptions for this run
            exc_result = await session.execute(
                select(ExceptionORM).where(ExceptionORM.run_id == run.id)
            )
            exceptions = exc_result.scalars().all()
            
            print(f'\nTotal exceptions: {len(exceptions)}')
            
            # Count by category
            category_counts = Counter()
            for exc in exceptions:
                category_counts[exc.exception_category] += 1
            
            print('\nException category breakdown:')
            for category, count in category_counts.items():
                print(f'  {category}: {count}')
        else:
            print('Run not found')

if __name__ == "__main__":
    asyncio.run(test())
