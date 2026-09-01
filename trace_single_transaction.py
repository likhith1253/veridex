"""
Trace a single transaction through the entire reconciliation pipeline
to identify where expected exceptions are being lost
"""
import asyncio
import asyncpg
import json
from decimal import Decimal

async def trace_transaction():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/sentinel')
    
    # Get the latest run
    run = await conn.fetchrow("SELECT id, run_id FROM reconciliation_runs WHERE run_id = 'adversarial_eval_6233'")
    if not run:
        print("Run not found")
        return
    
    run_id = run['id']
    print(f"Tracing run: {run['run_id']} (ORM ID: {run_id})")
    
    # Load ground truth
    with open('private_ground_truth.json', 'r') as f:
        ground_truth = json.load(f)
    
    # Pick a representative transaction from each missed scenario
    scenarios_to_trace = [
        'amount_mismatch_gw_ledger',
        'amount_mismatch_gw_bank', 
        'missing_ledger',
        'missing_gateway',
        'missing_bank',
        'duplicate_gateway',
        'duplicate_bank',
        'fee_mismatch',
        'tax_mismatch',
        'same_order_diff_amount',
        'same_ref_diff_amount',
        'delayed_settlement',
        'partial_match',
        'complex_mismatch'
    ]
    
    for scenario in scenarios_to_trace:
        # Find first transaction with this scenario
        for logical_id, data in ground_truth.items():
            if data['scenario'] == scenario:
                print(f"\n{'='*60}")
                print(f"Tracing {logical_id} - Scenario: {scenario}")
                print(f"Expected outcome: {data['expected_outcome']}")
                print(f"Amount: {data['amount']}")
                print(f"{'='*60}")
                
                # Get the three source transactions
                gw_id = data['gateway_id']
                ld_id = data['ledger_id']
                bk_id = data['bank_id']
                
                # Query each transaction from DB
                gw_txn = await conn.fetchrow("SELECT id, domain_transaction_id, amount, source, order_id, reference_number FROM transactions WHERE domain_transaction_id = $1", gw_id)
                ld_txn = await conn.fetchrow("SELECT id, domain_transaction_id, amount, source, order_id, reference_number FROM transactions WHERE domain_transaction_id = $1", ld_id)
                bk_txn = await conn.fetchrow("SELECT id, domain_transaction_id, amount, source, order_id, reference_number FROM transactions WHERE domain_transaction_id = $1", bk_id)
                
                print(f"\nGateway transaction: {gw_txn}")
                print(f"Ledger transaction: {ld_txn}")
                print(f"Bank transaction: {bk_txn}")
                
                # Check if any of these are in matches
                if gw_txn:
                    gw_matches = await conn.fetch("""
                        SELECT m.id, m.confidence, m.match_type, m.reason, m.evidence
                        FROM matches m
                        JOIN match_transactions mt ON m.id = mt.match_id
                        WHERE mt.transaction_id = $1 AND m.run_id = $2
                    """, gw_txn['id'], run_id)
                    print(f"\nGateway in {len(gw_matches)} matches:")
                    for m in gw_matches:
                        print(f"  - Match ID: {m['id']}, Confidence: {m['confidence']}, Type: {m['match_type']}, Reason: {m['reason']}")
                        # Get all transactions in this match
                        match_txns = await conn.fetch("""
                            SELECT t.domain_transaction_id, t.amount, t.source
                            FROM transactions t
                            JOIN match_transactions mt ON t.id = mt.transaction_id
                            WHERE mt.match_id = $1
                        """, m['id'])
                        print(f"    Matched transactions:")
                        for mt in match_txns:
                            print(f"      - {mt['domain_transaction_id']}: {mt['amount']} ({mt['source']})")
                
                if ld_txn:
                    ld_matches = await conn.fetch("""
                        SELECT m.id, m.confidence, m.match_type, m.reason, m.evidence
                        FROM matches m
                        JOIN match_transactions mt ON m.id = mt.match_id
                        WHERE mt.transaction_id = $1 AND m.run_id = $2
                    """, ld_txn['id'], run_id)
                    print(f"\nLedger in {len(ld_matches)} matches:")
                    for m in ld_matches:
                        print(f"  - Match ID: {m['id']}, Confidence: {m['confidence']}, Type: {m['match_type']}, Reason: {m['reason']}")
                        match_txns = await conn.fetch("""
                            SELECT t.domain_transaction_id, t.amount, t.source
                            FROM transactions t
                            JOIN match_transactions mt ON t.id = mt.transaction_id
                            WHERE mt.match_id = $1
                        """, m['id'])
                        print(f"    Matched transactions:")
                        for mt in match_txns:
                            print(f"      - {mt['domain_transaction_id']}: {mt['amount']} ({mt['source']})")
                
                if bk_txn:
                    bk_matches = await conn.fetch("""
                        SELECT m.id, m.confidence, m.match_type, m.reason, m.evidence
                        FROM matches m
                        JOIN match_transactions mt ON m.id = mt.match_id
                        WHERE mt.transaction_id = $1 AND m.run_id = $2
                    """, bk_txn['id'], run_id)
                    print(f"\nBank in {len(bk_matches)} matches:")
                    for m in bk_matches:
                        print(f"  - Match ID: {m['id']}, Confidence: {m['confidence']}, Type: {m['match_type']}, Reason: {m['reason']}")
                        match_txns = await conn.fetch("""
                            SELECT t.domain_transaction_id, t.amount, t.source
                            FROM transactions t
                            JOIN match_transactions mt ON t.id = mt.transaction_id
                            WHERE mt.match_id = $1
                        """, m['id'])
                        print(f"    Matched transactions:")
                        for mt in match_txns:
                            print(f"      - {mt['domain_transaction_id']}: {mt['amount']} ({mt['source']})")
                
                # Check if any of these are in exceptions
                if gw_txn:
                    gw_exceptions = await conn.fetch("""
                        SELECT e.id, e.exception_category, e.financial_exposure, e.explanation
                        FROM exceptions e
                        JOIN exception_transactions et ON e.id = et.exception_id
                        WHERE et.transaction_id = $1 AND e.run_id = $2
                    """, gw_txn['id'], run_id)
                    print(f"\nGateway in {len(gw_exceptions)} exceptions:")
                    for e in gw_exceptions:
                        print(f"  - Exception ID: {e['id']}, Category: {e['exception_category']}, Exposure: {e['financial_exposure']}")
                        print(f"    Explanation: {e['explanation']}")
                
                if ld_txn:
                    ld_exceptions = await conn.fetch("""
                        SELECT e.id, e.exception_category, e.financial_exposure, e.explanation
                        FROM exceptions e
                        JOIN exception_transactions et ON e.id = et.exception_id
                        WHERE et.transaction_id = $1 AND e.run_id = $2
                    """, ld_txn['id'], run_id)
                    print(f"\nLedger in {len(ld_exceptions)} exceptions:")
                    for e in ld_exceptions:
                        print(f"  - Exception ID: {e['id']}, Category: {e['exception_category']}, Exposure: {e['financial_exposure']}")
                        print(f"    Explanation: {e['explanation']}")
                
                if bk_txn:
                    bk_exceptions = await conn.fetch("""
                        SELECT e.id, e.exception_category, e.financial_exposure, e.explanation
                        FROM exceptions e
                        JOIN exception_transactions et ON e.id = et.exception_id
                        WHERE et.transaction_id = $1 AND e.run_id = $2
                    """, bk_txn['id'], run_id)
                    print(f"\nBank in {len(bk_exceptions)} exceptions:")
                    for e in bk_exceptions:
                        print(f"  - Exception ID: {e['id']}, Category: {e['exception_category']}, Exposure: {e['financial_exposure']}")
                        print(f"    Explanation: {e['explanation']}")
                
                # Only trace one transaction per scenario
                break
    
    await conn.close()

asyncio.run(trace_transaction())
