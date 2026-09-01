# Sentinel End-to-End Audit

Status: IN PROGRESS

## 2026-09-01 21:41 IST
- Severity: CRITICAL
- Subsystem: Financial aggregate mismatch / Multiple adversarial generators
- Symptom: Independent evaluator financial aggregates do not match Sentinel's reported values. Ground truth gross: INR 9,667,841.75, Sentinel gross: INR 9,645,541.75 (difference: -22,300.00). Expected net differs by -24,310.72. Unreconciled exposure differs by -156,460.72.
- Reproduction: `python eval\independent_adversarial_eval.py`
- Expected behavior: Financial aggregates should match between ground truth and Sentinel reports
- Actual behavior: Significant discrepancies in gross volume, expected net, settlement variance, and unreconciled exposure
- Root cause: THREE completely separate adversarial data generators exist:
  1. `eval/independent_adversarial_eval.py` has its own `generate_adversarial_dataset()` creating 60 fixed transactions with ADV_* IDs (ADV_EXACT_01, ADV_DELAYED_31, etc.)
  2. `adversarial_evaluator.py` class generates 100+ records with different scenario distribution with EVAL_TXN_* IDs (EVAL_TXN_0000, EVAL_TXN_0001, etc.)
  3. `generate_independent_adversarial.py` has a third `generate_adversarial_dataset()` function creating transactions with GW_EXACT_*/LD_EXACT_*/BK_EXACT_* IDs
  The evaluator generates ground truth from its internal dataset but the trace script uses `private_ground_truth.json` from a different generator. These are completely different datasets with different financial totals.
- File/location: `eval/independent_adversarial_eval.py`, `adversarial_evaluator.py`, `generate_independent_adversarial.py`, `ingest_adversarial.py`, `trace_exceptions_with_mapping.py`
- Fix status: Pending

## 2026-09-01 21:42 IST
- Severity: CRITICAL
- Subsystem: Exception coverage reporting / Ground truth mismatch
- Symptom: Trace script reports 0% exception coverage (Expected: 46, Detected: 0, Missing: 46) despite the independent evaluator showing 46 exceptions expected and only 3 manual review
- Reproduction: `python trace_exceptions_with_mapping.py ADV_BATCH_1788274298`
- Expected behavior: Exception coverage should reflect the actual dataset that was ingested
- Actual behavior: The trace script loads `private_ground_truth.json` which contains 100 transaction scenarios from `adversarial_evaluator.py` (EVAL_TXN_* IDs), but the database contains 60 transactions from `eval/independent_adversarial_eval.py` (ADV_* IDs). The ground truth and actual data are completely mismatched.
- Root cause: `trace_exceptions_with_mapping.py` uses ground truth from a different generator than the one that created the actual database data. Database has ADV_* transactions, ground truth has EVAL_TXN_* transactions.
- File/location: `trace_exceptions_with_mapping.py`, `private_ground_truth.json`
- Fix status: Fixed - Modified evaluator to save ground truth and updated trace script to handle both formats

## 2026-09-01 21:43 IST
- Severity: CRITICAL
- Subsystem: Database / Ground truth namespace collision
- Symptom: Database contains transactions with ADV_* IDs (from independent evaluator) but ground truth file contains EVAL_TXN_* IDs (from adversarial_evaluator.py)
- Reproduction: `python -c "from eval.independent_adversarial_eval import generate_adversarial_dataset; dataset = generate_adversarial_dataset(); print('Sample ground truth keys:', list(dataset['ground_truth'].keys())[:5])"`
- Expected behavior: Ground truth should match the actual transaction IDs in the database
- Actual behavior: Database has "BK_ADV_HIGHVAL_60", "BK_ADV_COLLISION_58", etc. but ground truth has "EVAL_TXN_0000", "EVAL_TXN_0001", etc.
- Root cause: Three independent adversarial generators with different ID namespaces are being used interchangeably without coordination
- File/location: Database content vs `private_ground_truth.json`
- Fix status: Fixed - Evaluator now saves correct ground truth to private_ground_truth.json

## 2026-09-01 21:44 IST
- Severity: CRITICAL
- Subsystem: Independent evaluator design
- Symptom: `eval/independent_adversarial_eval.py` generates its own dataset internally but does not save ground truth to `private_ground_truth.json` for use by tracing scripts
- Reproduction: Inspect `eval/independent_adversarial_eval.py` - it calls `generate_adversarial_dataset()` and ingests the data, but never saves the ground truth to a file
- Expected behavior: The independent evaluator should save its ground truth so tracing scripts can use the correct ground truth for the actual ingested data
- Actual behavior: Ground truth is computed internally for aggregate comparison but not persisted. Tracing scripts use stale ground truth from a different generator.
- Root cause: The independent evaluator was designed as a self-contained evaluation tool without considering that other tools need access to its ground truth
- File/location: `eval/independent_adversarial_eval.py`
- Fix status: Fixed - Added ground truth persistence to evaluator

## 2026-09-01 21:45 IST
- Severity: CRITICAL
- Subsystem: Multiple parallel data generation pathways
- Symptom: THREE separate adversarial data generators exist in the repository with different ID namespaces and scenario distributions
- Reproduction: `grep -l "generate_adversarial_dataset" *.py` returns three files: `eval/independent_adversarial_eval.py`, `adversarial_evaluator.py`, `generate_independent_adversarial.py`
- Expected behavior: There should be ONE canonical adversarial data generator used by all evaluation and tracing tools
- Actual behavior: Three independent generators exist:
  1. `eval/independent_adversarial_eval.py::generate_adversarial_dataset()` - 60 transactions, ADV_* IDs
  2. `adversarial_evaluator.py::AdversarialDatasetGenerator.generate_comprehensive_dataset()` - 100+ transactions, EVAL_TXN_* IDs
  3. `generate_independent_adversarial.py::generate_adversarial_dataset()` - variable transactions, GW_EXACT_*/LD_EXACT_*/BK_EXACT_* IDs
- Root cause: Evolution of the repository without cleanup - each new evaluation need created a new generator instead of consolidating
- File/location: `eval/independent_adversarial_eval.py`, `adversarial_evaluator.py`, `generate_independent_adversarial.py`
- Fix status: Pending

## 2026-09-01 21:46 IST
- Severity: CRITICAL
- Subsystem: Financial aggregate calculation / Logical vs physical record counting - RESOLVED
- Symptom: Ground truth gross (INR 9,667,841.75) differs from database gateway total (INR 9,645,541.75) by INR 22,300.00
- Reproduction: Compare ground truth totals with database transaction totals
- Expected behavior: Financial aggregates should match between ground truth (logical transactions) and database (physical records)
- Actual behavior: The evaluator's ground truth counts 60 logical transactions, but the database contains 58 gateway records because duplicate scenarios create 2 physical gateway records per logical transaction. The ground truth gross_amount for duplicate scenarios is counted once per logical transaction, but the database sums all physical records.
- Root cause: ROOT CAUSE IDENTIFIED AND EXPLAINED: This is NOT a bug - it's a semantic difference between two valid data models:
  - Ground truth model: Logical transaction model (60 scenarios, includes direct bank credits without gateway records, counts duplicate scenarios once)
  - Database model: Physical record model (actual records ingested: 58 gateway, 57 ledger, 55 bank = 170 total records)
  
  The INR 22,300.00 difference is exactly explained by:
  - Direct bank credit scenarios (5 transactions): INR 107,500.00 - these have NO gateway records in DB
  - Duplicate gateway scenarios (3 transactions): INR 85,200.00 - these have DOUBLE gateway records in DB (6 physical records for 3 logical transactions)
  
  Calculation: 9,667,841.75 - 107,500.00 + 85,200.00 = 9,645,541.75 ✓
  
  The ground truth is correct for logical transaction evaluation, and the database is correct for physical record reconciliation. The evaluator is incorrectly comparing apples to oranges by expecting them to match.
- File/location: `eval/independent_adversarial_eval.py` - The evaluator's aggregate comparison logic needs to account for the semantic difference between logical and physical models
- Fix status: Fixed - Modified evaluator to compute expected physical record model from logical ground truth and verify against database metrics. Gateway gross difference is now INR 0.00.

## 2026-09-01 21:47 IST
- Severity: CRITICAL
- Subsystem: Exception detection baseline / Ground truth mismatch
- Symptom: The original task mentioned "46/46 exception coverage" but the current independent evaluator only has 15 expected exceptions
- Reproduction: The current ground truth from `eval/independent_adversarial_eval.py` only specifies 15 expected exceptions, not 46
- Expected behavior: The 46/46 baseline mentioned in the task should be achievable with the current evaluator
- Actual behavior: The 46/46 baseline was from the old `adversarial_evaluator.py` ground truth (EVAL_TXN_* IDs with 100 transactions), not the current independent evaluator
- Root cause: The task description referenced the old ground truth baseline, but the independent evaluator uses a different, smaller dataset
- File/location: Task description vs current `eval/independent_adversarial_eval.py` implementation
- Fix status: Pending - Need to clarify which ground truth is the canonical baseline and whether to maintain the 46-scenario baseline

## 2026-09-01 21:48 IST
- Severity: HIGH
- Subsystem: Multiple tracing scripts with hardcoded run IDs
- Symptom: Multiple tracing scripts exist with hardcoded run IDs from different generations of the system
- Reproduction: Inspect `trace_exception_detection.py` (hardcoded run_id="adversarial_eval_7138"), `trace_matching.py` (hardcoded run_id="adversarial_eval_2442")
- Expected behavior: Tracing scripts should accept run ID as a parameter or use the latest run automatically
- Actual behavior: Scripts have stale hardcoded run IDs that don't match the current database state
- Root cause: Tracing scripts were created for specific evaluation runs and never generalized
- File/location: `trace_exception_detection.py`, `trace_matching.py`
- Fix status: Pending

## 2026-09-01 21:49 IST
- Severity: HIGH
- Subsystem: Multiple diagnostic/check scripts
- Symptom: Multiple check scripts exist for different diagnostic purposes, some with overlapping functionality
- Reproduction: `check_actual_domain_ids.py`, `check_current_exceptions.py`, `check_db_state.py`, `check_exceptions_api.py`, `check_exceptions_db.py`, `check_match_schema.py`, `check_run_state.py`, `check_schema.py`
- Expected behavior: Diagnostic tools should be consolidated into a unified CLI or well-documented separate tools
- Actual behavior: Eight separate check scripts with unclear purpose and overlap
- Root cause: Diagnostic scripts accumulated over time without consolidation
- File/location: Multiple check_*.py files
- Fix status: Pending

## 2026-09-01 21:50 IST
- Severity: HIGH
- Subsystem: Root-level temporary test files
- Symptom: Multiple test_*.py files exist in repository root with hardcoded run IDs and debugging purposes
- Reproduction: Root-level files: test_api_exceptions.py, test_batch_isolation.py, test_connection.py, test_db_connection.py, test_db_connection_simple.py, test_exception_classification.py, test_exception_detection.py, test_independent_adversarial.py, test_qa.py, test_reconciliation_pipeline.py, test_simple_ingest.py
- Expected behavior: All tests should be in the tests/ directory as part of the formal pytest suite
- Actual behavior: 11 temporary test files in repository root with hardcoded run IDs and debugging logic, separate from the organized tests/ directory
- Root cause: Debugging scripts were created during development and left in the repository root
- File/location: Multiple test_*.py files in repository root
- Fix status: Pending - Should remove obsolete debugging test files and keep only the formal tests/ directory

## 2026-09-01 21:51 IST
- Severity: MEDIUM
- Subsystem: Generated log files
- Symptom: Multiple .err and .out log files from previous runs litter the repository root
- Reproduction: `Get-ChildItem -Filter *.err` and `Get-ChildItem -Filter *.out` show 6 files each
- Expected behavior: Log files should be in a logs/ directory or .gitignore'd
- Actual behavior: Log files are in the repository root: streamlit-8502.err, streamlit-audit.err, streamlit-live.err, uvicorn-audit.err, uvicorn-current.err, uvicorn-live.err (and corresponding .out files)
- Root cause: Log files from previous development sessions were not cleaned up
- File/location: *.err, *.out files in repository root
- Fix status: Pending

## 2026-09-01 21:52 IST
- Severity: MEDIUM
- Subsystem: PDF documentation files
- Symptom: 12 PDF files (ps1.pdf through ps12.pdf) are present in the repository root
- Reproduction: `Get-ChildItem -Filter *.pdf` shows 12 PDF files
- Expected behavior: Documentation should be in docs/ directory or external references
- Actual behavior: PDF files are in the repository root, likely academic papers or reference materials
- Root cause: Reference materials were placed in the repository root instead of docs/
- File/location: ps*.pdf files
- Fix status: Pending

## 2026-09-01 22:15 IST
- Severity: CRITICAL
- Subsystem: Funding / settlement accounting semantics
- Symptom: Cash-position math silently ignored refund metadata and fell back to ledger totals when gateway values were present, which mis-stated the net settlement and could hide source disagreement.
- Reproduction: The regression in [tests/test_finance_controller_backend.py](tests/test_finance_controller_backend.py) creates one gateway amount of 1000.00 with 20.00 fee, 5.00 tax, and 30.00 refund metadata; expected net should be 945.00 and zero variance, but the prior implementation returned 0.00 refund total and treated the ledger as the authoritative gross.
- Expected behavior: Gateway business value should remain the authoritative gross when present, refund metadata should be included in expected net settlement, and the bank credits should reconcile against the same equation.
- Actual behavior: Refunds were never accumulated in [app/services/cash_position.py](app/services/cash_position.py), and [app/services/settlement_accounting_service.py](app/services/settlement_accounting_service.py) used a weaker fallback strategy instead of preserving the gateway’s business value.
- Root cause: Two accounting services were calculating the same financial quantity differently and both discarded refund metadata. The ledger value was being used as a fallback signal instead of preserving the source disagreement separately.
- File/location: [app/services/cash_position.py](app/services/cash_position.py), [app/services/settlement_accounting_service.py](app/services/settlement_accounting_service.py)
- Fix status: Fixed
- Verification: python -m pytest tests/test_finance_controller_backend.py -q; result: 15 passed in 2.82s

## 2026-09-01 22:30 IST
- Severity: CRITICAL
- Subsystem: Benchmark source-of-truth / ground-truth namespace validation
- Symptom: Legacy dataset files using EVAL_TXN_* IDs were still accepted as if they were the canonical benchmark, creating silent benchmark drift across evaluation scripts.
- Reproduction: Importing `eval.benchmark_registry.validate_ground_truth_namespace` with a legacy EVAL_TXN_* dict raised a validation error once the guard was in place; before the fix, the codebase implicitly trusted whichever `private_ground_truth.json` happened to be on disk.
- Expected behavior: The authoritative benchmark must be the canonical `ADV_*` dataset produced by `eval/independent_adversarial_eval.py`.
- Actual behavior: The repository permitted multiple ground-truth namespaces to coexist and be treated as interchangeable.
- Root cause: No namespace validation existed to reject legacy `EVAL_TXN_*` datasets before they were used by tracing and evaluation tooling.
- File/location: `eval/benchmark_registry.py`, `eval/independent_adversarial_eval.py`, `trace_exceptions_with_mapping.py`
- Fix status: Fixed - Added canonical benchmark validation and a regression test to reject legacy datasets.
- Verification: `python -m pytest tests/test_benchmark_canonical.py -q` -> 2 passed in 1.55s

## 2026-09-01 22:45 IST
- Severity: CRITICAL
- Subsystem: Canonical benchmark acceptance gate / live verification
- Symptom: The live canonical benchmark still fails the repository's required 46/46 acceptance gate because the current `ADV_*` generator defines only 15 expected exceptions and the real reconciler produces 29 detected exceptions, not 46.
- Reproduction:
  - `python clear_database.py`
  - `python -c "from eval.independent_adversarial_eval import generate_adversarial_dataset; d = generate_adversarial_dataset(); print(len(d['ground_truth'])); print(sum(1 for v in d['ground_truth'].values() if v.get('expected_exception'))); print({k: sum(1 for v in d['ground_truth'].values() if v.get('expected_category') == k) for k in sorted({v.get('expected_category') for v in d['ground_truth'].values() if v.get('expected_category')} )})"` -> `logical_transactions=60`, `expected_exception_count=15`
  - `python trace_exceptions_with_mapping.py ADV_BATCH_1788283776` -> `Expected exceptions: 15`, `Detected exceptions: 29`, `Coverage: 193.3%`
- Expected behavior: The benchmark should meet the pass gate: `Expected exceptions = 46`, `Detected exceptions = 46`, `Missing = 0`, `Unexpected = 0`, `Coverage = 100.0%`.
- Actual behavior: The current repo's canonical generator yields a 15-exception benchmark. The system then over-detects with 29 exceptions, so the target gate is not satisfied by the current implementation.
- Root cause: The repository still contains an older benchmark expectation (46/46) from a different benchmark definition, while the active canonical generator in `eval/independent_adversarial_eval.py` intentionally models a smaller 60-transaction / 15-exception scenario set. This is not a namespace bug anymore; it is a benchmark-definition mismatch between the repository's claimed acceptance target and the actual canonical dataset in code.
- File/location: `eval/independent_adversarial_eval.py`, `trace_exceptions_with_mapping.py`, `private_ground_truth.json`, `e2e_audit_log.md`
- Fix status: Remaining blocker - do not weaken the acceptance gate. The repo's intended benchmark target is different from the current canonical generator and therefore still needs an authoritative definition update or dataset re-baseline before the 46/46 gate can be claimed.

## 2026-09-01 23:22 IST
- Severity: CRITICAL
- Subsystem: Live canonical benchmark verification / Acceptance gate comparison
- Symptom: Canonical benchmark run `ADV_BATCH_1788285093` verified from a clean database state produces 15 expected exceptions and 29 detected exceptions across 60 logical transactions and 170 physical records.
- Reproduction:
  - `python clear_database.py`
  - `python eval/independent_adversarial_eval.py` -> Run ID: `ADV_BATCH_1788285093`
  - `python trace_exceptions_with_mapping.py ADV_BATCH_1788285093`
- Expected behavior (Pass Gate): Expected = 46, Detected = 46, Missing = 0, Unexpected = 0, Coverage = 100.0%.
- Actual behavior: Expected = 15, Detected = 29, Missing = 0, Unexpected = 11 scenario groups (Direct bank credits, fee overcharges, corrupt UTRs), Coverage = 100.0% of expected (193.3% raw ratio).
- Root cause: The 46-exception scenario expectation originated in `adversarial_evaluator.py` (which had 100 logical transactions and 46 exceptions), whereas the authoritative canonical generator `eval/independent_adversarial_eval.py` intentionally models a 60-transaction / 15-expected-exception dataset. The reconciliation engine correctly detects all 15 expected exceptions, but additionally flags 11 other non-standard scenario groups (5 direct credits without gateway, 3 fee overcharges, 3 corrupted UTRs without fuzzy recovery) as exceptions in the database.
- File/location: `eval/independent_adversarial_eval.py`, `eval/benchmark_registry.py`, `trace_exceptions_with_mapping.py`
- Fix status: Blocked on benchmark acceptance gate alignment (46 vs 15).
- Verification: `python trace_exceptions_with_mapping.py ADV_BATCH_1788285093` executed cleanly; financial physical model gross matches to 0.00 difference (INR 9,645,541.75).

## 2026-09-02 00:15 IST
- Severity: CRITICAL
- Subsystem: Canonical adversarial benchmark unification & consolidation
- Symptom: Multiplicity of adversarial data generators (`adversarial_evaluator.py`, `eval/independent_adversarial_eval.py`, `generate_independent_adversarial.py`) and divergence between the 46-scenario acceptance gate and 60-transaction cutdown generator.
- Reproduction: Running `trace_exceptions_with_mapping.py` or comparing `private_ground_truth.json` with `eval/independent_adversarial_eval.py`.
- Expected behavior: Exactly ONE canonical adversarial benchmark pipeline in `eval/independent_adversarial_eval.py` that implements the authoritative 100-logical-transaction / 46-exception Track 04 scenario set with strict `ADV_*` namespace, scenario-identity mapping, deterministic seed reproducibility, and exact accounting model parity (0.00 difference).
- Actual behavior: Conflicting generators, obsolete trace scripts, and disjoint ground-truth definitions existed across root and `eval/`.
- Root cause: Historical development artifacts remained in repo without consolidation.
- File/location: `eval/independent_adversarial_eval.py`, `adversarial_evaluator.py`, `generate_independent_adversarial.py`, `trace_exceptions_with_mapping.py`, `final_verification.py`
- Fix status: In Progress - Consolidating all scenario definitions into `eval/independent_adversarial_eval.py` with 100 logical transactions (54 clean, 46 exceptions), unified ground-truth generator, scenario-level evaluator, and removing obsolete generators.
