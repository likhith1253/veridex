"""
Analyze which exceptions are being missed by the reconciliation engine
"""
import json
from collections import defaultdict, Counter

# Load the audit results
with open('evaluation_id_mapping_audit.json', 'r') as f:
    audit_results = json.load(f)

# Find missed exceptions with valid mapping
missed_exceptions = [
    r for r in audit_results['detailed_mapping_results']
    if r['should_except'] and not r['has_exception'] and r['orm_uuid']
]

print(f"Missed exceptions with valid mapping: {len(missed_exceptions)}")
print("\nBreakdown by scenario:")
scenario_counts = Counter(r['scenario'] for r in missed_exceptions)
for scenario, count in scenario_counts.most_common():
    print(f"  {scenario}: {count}")

print("\nBreakdown by expected outcome:")
outcome_counts = Counter(r['expected_outcome'] for r in missed_exceptions)
for outcome, count in outcome_counts.most_common():
    print(f"  {outcome}: {count}")

print("\nDetailed list of missed exceptions:")
for i, exc in enumerate(missed_exceptions[:15], 1):
    print(f"\n{i}. {exc['logical_id']} ({exc['scenario']})")
    print(f"   Expected outcome: {exc['expected_outcome']}")
    print(f"   Source IDs: {exc['source_ids']}")
    print(f"   ORM UUIDs: {exc['orm_uuids']}")

if len(missed_exceptions) > 15:
    print(f"\n... and {len(missed_exceptions) - 15} more")

# Load ground truth to get more details
with open('private_ground_truth.json', 'r') as f:
    ground_truth = json.load(f)

print("\n\nDetailed ground truth for missed exceptions:")
for i, exc in enumerate(missed_exceptions[:10], 1):
    logical_id = exc['logical_id']
    gt_data = ground_truth[logical_id]
    print(f"\n{i}. {logical_id}")
    print(f"   Scenario: {gt_data['scenario']}")
    print(f"   Expected outcome: {gt_data['expected_outcome']}")
    print(f"   Gateway ID: {gt_data.get('gateway_id')}")
    print(f"   Ledger ID: {gt_data.get('ledger_id')}")
    print(f"   Bank ID: {gt_data.get('bank_id')}")
    print(f"   Amount: {gt_data.get('amount')}")
