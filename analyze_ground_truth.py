import json
from collections import Counter

# Load ground truth
with open('private_ground_truth.json', 'r') as f:
    ground_truth = json.load(f)

# Analyze expected outcomes
outcomes = Counter()
scenarios = Counter()

for txn_id, data in ground_truth.items():
    outcomes[data['expected_outcome']] += 1
    scenarios[data['scenario']] += 1

print("Expected Outcomes:")
for outcome, count in outcomes.most_common():
    print(f"  {outcome}: {count}")

print("\nScenarios:")
for scenario, count in scenarios.most_common():
    print(f"  {scenario}: {count}")

# Count exceptions
exception_outcomes = [k for k, v in outcomes.items() if 'exception' in k.lower()]
total_exceptions = sum(outcomes[k] for k in exception_outcomes)
print(f"\nTotal expected exceptions: {total_exceptions}")
print(f"Exception types: {exception_outcomes}")
