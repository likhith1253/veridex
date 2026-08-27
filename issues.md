# Project Sentinel — End-to-End Dashboard Issues & Verification Backlog

**Purpose:** This document is the single source of truth for fixing and re-verifying the current Project Sentinel Streamlit dashboard.

**Review standard:** Razorpay AI Buildathon / evaluator-style review. Findings are based only on the supplied dashboard screenshots/PDF captures and the supplied project/code/audit material. No issue below should be "fixed" by changing numbers merely to make the UI look consistent. Every correction must trace back to PostgreSQL/database state, the actual matching/investigation logic, or an explicitly defined product rule.

**Important:** Several items are confirmed inconsistencies from the supplied evidence. Items marked **VERIFY** are deliberate verification requirements where the screenshots expose a suspicious condition but do not, by themselves, prove the underlying defect.

---

## Severity

- **P0 — Critical:** Financial correctness, reconciliation integrity, false-match risk, or evaluator-critical functionality.
- **P1 — High:** Major feature correctness, auditability, AI grounding, or end-to-end workflow problem.
- **P2 — Medium:** UX/data presentation issue that can mislead an operator.
- **P3 — Low:** Polish/documentation/non-blocking issue.

## Fixing Rules

1. **Never hardcode a displayed metric to match a screenshot.**
2. **Never delete/reset production-like test data just to hide an inconsistency.**
3. Every financial metric must have one authoritative calculation path.
4. Every dashboard KPI must be traceable:
   `UI -> API -> service -> SQL/database records -> underlying feed data`.
5. Every AI answer must be independently reproducible from the same database state.
6. ML scores shown in the UI must be the actual model output for the displayed candidate, not a stored/demo value unless explicitly labelled.
7. Groq-backed investigation must prove an actual Groq API call occurred and that the displayed answer corresponds to the returned, validated result.
8. After each fix, run the relevant automated tests **and** re-open the Streamlit UI to verify the actual rendered result.
9. Do not mark an issue fixed from unit tests alone when the issue concerns cross-page consistency.
10. Preserve an evidence trail for every fix.

---

# P0 — Critical Correctness Issues

## ISSUE-001 — Executive funnel does not reconcile to total processed records

**Status:** OPEN  
**Severity:** P0  
**Area:** Executive Overview / Reconciliation

### Observed evidence

The Executive Overview screenshot shows:

- Total Processed = **30**
- Ingested = **30**
- Deterministic = **4**
- ML Recovered = **16**
- Manual Review = **3**
- Unresolved = **6**

The latter four stages sum to:

`4 + 16 + 3 + 6 = 29`

They therefore do not account for all 30 processed records.

### Why this matters

A financial controller dashboard cannot present a reconciliation funnel whose terminal categories fail to account for the population entering the funnel.

### Required investigation

Trace the 30 records from PostgreSQL through:

- `transactions`
- `matches`
- `decisions`
- `exceptions`
- reconciliation run identifiers

Determine whether the missing one record is:

- a genuine unclassified state,
- a duplicate,
- a feed-level record rather than a logical transaction,
- a decision omitted from the query,
- or a counting-definition error.

### Acceptance criteria

- Funnel categories reconcile exactly to the defined population.
- The denominator is explicitly defined.
- No record silently disappears.
- A database query can reproduce every displayed funnel number.

---

## ISSUE-002 — Executive "Reconciliation Rate 55%" has an unclear/inconsistent denominator

**Status:** OPEN  
**Severity:** P0  
**Area:** Executive Overview

The dashboard shows **55.0%** reconciliation while the visible funnel has:

- 4 deterministic
- 16 ML
- 3 manual
- 6 unresolved

The apparent matched count is 20, but 20/30 = **66.67%**, not 55%.

The supplied controller code also calculates match rate as:

`(auto_matches + ml_count) / total_decisions`

This requires verification because `auto_matches` and `ml_count` may overlap depending on how ML decisions are represented.

### Required fix

Define exactly:

- numerator,
- denominator,
- whether the unit is feed records, logical transactions, decisions, or matches,
- whether ML matches are already included in `AUTO_MATCH`.

### Acceptance criteria

For one frozen run, the UI, API, SQL calculation, and independent manual calculation all return the same reconciliation rate.

---

## ISSUE-003 — `total_matched_records` is calculated with a hardcoded `* 2`

**Status:** OPEN  
**Severity:** P0  
**Area:** FinanceController KPI calculation

The supplied code calculates:

`total_matched_records = (det_count + ml_count) * 2`

This is not a database-derived count and does not obviously correspond to the three-feed architecture.

### Why this matters

A match may involve two or three feed records. Multiplying match count by two can create incorrect operational totals.

### Required fix

Calculate matched records from the actual match-to-transaction relationship in PostgreSQL.

### Acceptance criteria

- No fixed multiplier.
- Count can be independently derived from `match_transactions` / actual relationships.
- Correct for 2-way, 3-way, duplicate, and partial scenarios.

---

## ISSUE-004 — Reconciliation precision/recall/F1 are hardcoded in the live KPI service

**Status:** RESOLVED  
**Severity:** P0  
**Area:** FinanceController

The supplied code sets:

- precision = **89.86** when ML exists
- recall = **100.0** when ML exists
- F1 = **94.66** when ML exists

These are constants rather than metrics calculated from the current live run.

### Why this matters

The UI presents these as live reconciliation quality metrics. Hardcoded values make the dashboard potentially misleading.

### Required fix

Calculate metrics from explicit ground truth/evaluation data only where ground truth exists. If live production data has no ground truth, do not fabricate precision/recall; label benchmark metrics separately.

### Acceptance criteria

- Live operational KPI ≠ benchmark metric unless explicitly labelled.
- Changing the run changes only metrics that should change.
- Every quality metric has a documented denominator.

---

## ISSUE-005 — Throughput is hardcoded while Executive Overview displays N/A

**Status:** RESOLVED  
**Severity:** P0  
**Area:** Executive Overview

The supplied service sets:

- throughput = **1800.0 TPS**
- latency = **0.55 ms**

Yet the supplied Executive Overview screenshot displays **Throughput: N/A**.

### Required investigation

Determine whether:

1. the API actually returns 1800/0.55,
2. the frontend schema/client drops those fields,
3. the UI intentionally suppresses them,
4. or the values are hardcoded but not meaningful.

### Required fix

If throughput is shown, it must be calculated from a real measured interval. If unavailable, show N/A with an explicit reason. Do not use a constant 1800 TPS.

### Acceptance criteria

A real ingestion run reports:

`processed records / elapsed processing time`

with units and measurement window.

---

## ISSUE-006 — Settlement/accounting expected amount conflicts with cash position

**Status:** OPEN  
**Severity:** P0  
**Area:** Settlement & Accounting / Cash Position

Settlement screenshot:

- Gross Gateway Volume = **₹2,310,799.00**
- MDR Fees = **₹46,215.98**
- GST = **₹8,318.88**
- Refunds = **₹0.00**
- Expected Net Bank Settlement = **₹2,256,264.14**
- Actual Bank Credits = **₹2,310,799.00**
- Net Settlement Variance = **₹54,534.86**

The Cash Position screenshot instead shows:

- Expected Total = **₹2,310,799.00**
- Received Bank Settlement = **₹2,310,799.00**
- Pending = **₹0**
- Unreconciled Exposure = **₹0**

The expected settlement figure therefore has two different meanings across pages.

### Required fix

Choose one authoritative semantic definition:

- `expected_gross`
- `expected_net_settlement`
- `received_bank_credits`
- `settlement_variance`

Expose them separately rather than using "Expected" for different concepts.

### Acceptance criteria

For the displayed dataset:

`Gross - MDR - GST - Refunds = Expected Net`

and:

`Actual Bank Credits - Expected Net = Variance`

must hold across every page.

---

## ISSUE-007 — Settlement variance exists while cash exposure is zero

**Status:** OPEN  
**Severity:** P0  
**Area:** Cash / Settlement / Exposure

Settlement reports a **₹54,534.86** variance and labels it:

`DISCREPANCY_DETECTED — Unsettled delayed exposure: ₹54,534.86`

Cash Position reports:

`Unreconciled Exposure = ₹0.00`

### Required investigation

Trace the same exposure through:

- settlement accounting API,
- cash-position service,
- exception table,
- exposure calculation,
- exception status.

Determine why the same financial discrepancy is not represented consistently.

### Acceptance criteria

Either:

- the variance is a true unresolved exposure and appears consistently,

or:

- it is explicitly classified as a non-exposure accounting variance with a documented reason.

---

## ISSUE-008 — Source Health per-feed metrics are artificially distributed

**Status:** OPEN  
**Severity:** P0  
**Area:** Source Health

The supplied source-health implementation contains:

`approx_excs = total_excs // 3`

and then assigns the same approximate exception count to each feed.

This means feed-level exceptions are not actually derived from each feed's records.

### Why this matters

The UI claims to show health for:

- Payment Gateway
- Internal Ledger
- Core Bank Statement

but the implementation distributes total exceptions rather than measuring each source.

### Required fix

Compute per-source:

- record count,
- volume,
- matched records,
- exceptions,
- match rate,
- exception rate,
- status

directly from source-specific database relationships.

### Acceptance criteria

A deliberately injected exception in only one feed changes that feed's health without artificially changing all three feeds.

---

## ISSUE-009 — `ANOMALOUS` source health branch is unreachable

**Status:** OPEN  
**Severity:** P0  
**Area:** Source Health

The supplied implementation checks:

- `if exception_rate > 20%: DEGRADED`
- `elif exception_rate > 40%: ANOMALOUS`

The second condition can never execute because anything above 40% is already above 20%.

### Required fix

Order thresholds from highest to lowest, e.g. evaluate the anomalous threshold before degraded, according to the actual intended policy.

### Acceptance criteria

A test source with >40% exception rate produces `ANOMALOUS`.

---

# P0 — ML / Matching Issues

## ISSUE-010 — Displayed ML scores conflict with the stated auto-match threshold

**Status:** OPEN  
**Severity:** P0  
**Area:** Reconciliation Operations / Finance AI Q&A

Decision Policy screenshot states:

- ML Scored Match threshold = **>= 0.90**
- Action = **Auto-Commit**

The AI Q&A evidence table displays ML candidate scores including values around:

- **0.9492**
- **0.8968**
- **0.9006**
- **0.3452**

Yet the answer says:

`16 transaction matches (80.0% of all matches)`

and the UI categorizes 16 as ML recovered.

### Required investigation

For every displayed ML match:

- retrieve the actual decision,
- retrieve the actual model probability,
- retrieve the decision action,
- retrieve the threshold applied.

### Acceptance criteria

No ML match may be labelled Auto-Commit when its actual probability is below the configured auto-commit threshold.

If lower-score candidates are stored for evidence but not committed, label them as candidates rather than recovered matches.

---

## ISSUE-011 — ML benchmark reports contradictory aggregate/scenario results

**Status:** OPEN  
**Severity:** P0  
**Area:** Benchmark & Model Evaluation

The benchmark UI shows overall:

- Precision = **0.9000**
- Recall = **1.0000**
- F1 = **0.9474**
- False match rate = **0.1000**

It also shows scenario data where the `duplicate` scenario has:

- total_records = 10
- matched_records = 0
- correct_matches = 0
- false_matches = 20
- unresolved_records = 10

`false_matches = 20` exceeds `total_records = 10`.

### Required fix

Audit benchmark definitions and aggregation. A scenario must have internally valid counts.

### Acceptance criteria

For every scenario:

`TP + FP + FN + TN`

and/or the chosen scenario-specific accounting must be mathematically coherent and documented.

No category can contain more false matches than the evaluated population without an explicit pair-level denominator.

---

## ISSUE-012 — Benchmark `total_transactions = 300` conflicts with dataset label `n_100`

**Status:** OPEN  
**Severity:** P1  
**Area:** Benchmark

Dataset name:

`benchmark_seed_42_n_100`

UI input:

`Logical transactions = 100`

Full Evaluation JSON:

`total_transactions = 300`

### Required investigation

Determine whether 100 means logical transactions while 300 means three feed records per logical transaction.

### Required fix

If this is intentional, label it explicitly:

`100 logical transactions / 300 feed records`

Do not call both "transactions."

### Acceptance criteria

Benchmark terminology is unambiguous.

---

## ISSUE-013 — Benchmark scenario totals need to reconcile to the declared dataset population

**Status:** OPEN  
**Severity:** P1  
**Area:** Benchmark

Visible scenario totals include:

- normal = 60
- duplicate = 10
- fee_mismatch = 5
- wrong_reference = 8
- unexplained = 5
- ambiguous = 10
- delayed_settlement = 5

These total **103**, not 100.

The full evaluation section also reports 300 total transactions.

### Required investigation

Determine whether scenario totals represent logical transactions, feed records, candidate pairs, or another unit.

### Acceptance criteria

The benchmark UI explicitly states the unit of each total and all totals reconcile under that definition.

---

## ISSUE-014 — Risk-bucket totals use a different population/denominator than the headline benchmark

**Status:** OPEN  
**Severity:** P1  
**Area:** Benchmark

Risk bucket data shows transaction counts such as:

- Low: 3
- Medium: 10
- High: 26
- Critical: 61

These sum to **100**, while match counts are larger and exposure totals are separate.

This may be intentional, but the UI does not clearly distinguish transaction population from match population.

### Required fix

Add explicit labels:

- logical transactions,
- candidate matches,
- evaluated decisions,
- exposure.

### Acceptance criteria

An evaluator can determine exactly what every count refers to without reverse-engineering JSON.

---

# P1 — AI / Groq / Grounding

## ISSUE-015 — Finance AI Q&A claims "zero hallucinations" but needs runtime proof of grounding

**Status:** OPEN  
**Severity:** P1  
**Area:** Finance AI Q&A

The UI states:

`grounded strictly in PostgreSQL state (zero hallucinations)`

and displays SQL facts used.

### Required verification

Run a matrix of questions against live PostgreSQL state:

1. total processed records
2. total matched records
3. ML recovered count
4. unresolved exposure
5. highest exposure exception
6. source health
7. settlement variance
8. refunds
9. duplicates
10. deliberately unsupported question
11. ambiguous natural-language question
12. question asking for information absent from the DB

### Acceptance criteria

For supported questions:

- answer agrees with SQL,
- key metrics agree with SQL,
- evidence records correspond to the answer.

For unsupported questions:

- AI refuses/qualifies rather than inventing facts.

---

## ISSUE-016 — Groq integration must be verified from the actual runtime path, not only a verification script

**Status:** OPEN  
**Severity:** P1  
**Area:** AI Investigation / Groq

Supplied project material states that live Groq was verified using:

`openai/gpt-oss-20b` via Groq API

with a Pydantic validation firewall.

However, the dashboard screenshots alone do not prove that every displayed investigation was generated by a live Groq request.

### Required verification

For a fresh exception:

1. create/ingest the exception,
2. trigger investigation from the UI,
3. capture the request path,
4. prove Groq was called,
5. capture model name,
6. validate returned schema,
7. verify displayed root cause equals validated result,
8. verify no stale previous investigation was displayed.

### Acceptance criteria

A fresh UI-triggered investigation produces a traceable Groq call and a new investigation record.

---

## ISSUE-017 — AI investigation confidence is inconsistent with the displayed ML probability

**Status:** OPEN  
**Severity:** P1  
**Area:** Exception Workspace

The workspace screenshot shows:

- Human Review Required
- Confidence = **34.5%**

The evidence shows:

- ML Probability = **0.345159**
- Investigation confidence = **0.8000**
- Investigation method = `deterministic`

These are different confidence concepts but are presented close together without clear semantic separation.

### Required fix

Use explicit labels:

- ML match probability
- Investigation confidence
- Decision confidence
- Human-review rule

### Acceptance criteria

An evaluator can tell which confidence value controls which decision.

---

## ISSUE-018 — AI investigation for an `unknown` category must explain classification source

**Status:** OPEN  
**Severity:** P1  
**Area:** Exception Workspace

The exception data shows:

- category = `unknown`
- risk_bucket = `low`
- exposure = ₹0
- recommended_action = `investigate_further`

Yet the workspace provides a specific root cause:

`Mismatched external reference / UTR across feeds despite matching order ID`

### Required verification

Trace:

`exception.category -> investigation input -> deterministic explanation -> Groq/LLM output -> UI`.

### Acceptance criteria

The category shown in the UI must correspond to a real classification rule or be explicitly labelled as an unresolved category.

---

# P1 — Settlement / Refund / Duplicate Controls

## ISSUE-019 — Duplicate incident exposure may be double-counted

**Status:** VERIFY  
**Severity:** P1  
**Area:** Refunds & Duplicates

The duplicate page shows:

- Total Incidents = **2**
- Duplicate Gateway Charges = **1**
- Duplicate Bank Credits = **1**
- each displays **₹285,637.00** exposure

The evidence table contains two incidents with the same:

- `record_count = 3`
- `total_amount = 302800`
- `excess_exposure = 285637`

### Required verification

Determine whether the two incidents represent independent financial exposures or two classifications of the same underlying duplicated money.

### Acceptance criteria

The total exposure is not double-counted across dashboard summaries.

---

## ISSUE-020 — Duplicate incident `total_amount` vs `excess_exposure` needs explicit definition

**Status:** VERIFY  
**Severity:** P1  
**Area:** Refunds & Duplicates

The evidence shows:

`total_amount = ₹302,800`

and:

`excess_exposure = ₹285,637`

Difference:

`₹17,163`

The UI does not explain what ₹17,163 represents.

### Required fix

Show the calculation/evidence for:

`excess exposure = duplicate total - legitimate/original amount`

if that is the intended rule.

---

## ISSUE-021 — Settlement variance classification needs explicit linkage to delayed settlement

**Status:** VERIFY  
**Severity:** P1  
**Area:** Settlement

The settlement page calls the variance a delayed exposure.

### Required verification

Find the underlying transaction(s), settlement timing fields, and exception category that justify this classification.

### Acceptance criteria

No variance is labelled `delayed settlement` without transaction-level evidence.

---

# P1 — Exception Workflow / Auditability

## ISSUE-022 — Exception Queue status filter and aging summary appear to use different populations

**Status:** VERIFY  
**Severity:** P1  
**Area:** Exception Queue

The screenshot shows the filter:

`Status = approved`

while the aging section displays:

`1-3 days = 7 open`

and other open buckets.

### Required investigation

Determine whether aging is intentionally global or should reflect the selected filters.

### Required fix

Either:

- make aging obey filters,

or

- clearly label it as "All Open Exceptions" independent of the filter.

---

## ISSUE-023 — Exception Workspace exposes financial exposure of ₹0 for a transaction amount of ₹49,623

**Status:** VERIFY  
**Severity:** P1  
**Area:** Exception Workspace

The selected exception shows:

- Transaction Amount = **₹49,623.00**
- Monetary Exposure = **₹0.00**

This may be legitimate, but the UI needs to explain why a financial exception has zero exposure.

### Required verification

Trace the exception's `amount_delta`, `financial_exposure`, expected cost, and resolution state.

### Acceptance criteria

Zero exposure is supported by a documented calculation.

---

## ISSUE-024 — Decision controls need state-transition verification

**Status:** VERIFY  
**Severity:** P1  
**Area:** Exception Workspace

Available controls include:

- APPROVE
- REJECT
- ESCALATE
- RESOLVE
- INVESTIGATE
- Assign Exception
- Attach Note

### Required end-to-end test

For each action:

1. perform it from Streamlit,
2. verify HTTP response,
3. verify DB state,
4. verify exception state,
5. verify audit event,
6. refresh page,
7. verify other dashboards update consistently.

### Acceptance criteria

No UI action may appear successful while the database remains unchanged.

---

## ISSUE-025 — Audit trail contains repeated `investigation_completed` events for the same run

**Status:** VERIFY  
**Severity:** P1  
**Area:** Audit Trail

The audit screenshot contains many repeated:

`investigation_completed`

events associated with the same run identifier.

### Required investigation

Determine whether these correspond to distinct investigations or accidental duplicate events.

### Acceptance criteria

Every audit event corresponds to one real state transition/action, with stable event identity and no duplicate emission from retries/reruns unless explicitly recorded as a retry.

---

# P2 — Forecast / Data Presentation

## ISSUE-026 — Forecast methodology label does not match the implementation description

**Status:** OPEN  
**Severity:** P2  
**Area:** Cash Forecast

The UI says:

`7-Day Historical Moving Average with Weekend Liquidity Smoothing`

The supplied implementation calculates:

`total gateway volume / 30`

as the baseline daily average, then applies weekday factors.

That is not a literal seven-day historical moving average.

### Required fix

Either:

- implement a true 7-day historical moving average,

or

- rename the methodology to accurately describe the 30-day-base calculation.

### Acceptance criteria

Methodology text and code are semantically identical.

---

## ISSUE-027 — Forecast should expose the data window used for the baseline

**Status:** OPEN  
**Severity:** P2  
**Area:** Cash Forecast

The forecast currently exposes the methodology but not a clear historical data window.

### Required fix

Display:

- historical period,
- number of source records,
- baseline daily volume,
- weekend factor policy,
- forecast date range.

---

## ISSUE-028 — Forecast confidence intervals are fixed ±15% and need explicit statistical meaning

**Status:** VERIFY  
**Severity:** P2  
**Area:** Cash Forecast

The supplied implementation calculates:

- low = forecast × 0.85
- high = forecast × 1.15

This is a deterministic band, not necessarily a statistically estimated confidence interval.

### Required fix

Either call it a:

`±15% planning range`

or implement a statistically justified confidence interval.

---

# P2 — UI / Evaluator Clarity

## ISSUE-029 — Long KPI values are visually truncated

**Status:** OPEN  
**Severity:** P2  
**Area:** Executive Overview

The screenshot visibly truncates several KPI values with ellipses, including monetary figures and labels.

### Required fix

Use responsive metric cards, tooltips, wrapping, or abbreviated formatting with accessible full values.

### Acceptance criteria

No important financial number is visually ambiguous at the evaluator's normal browser width.

---

## ISSUE-030 — Raw JSON is exposed as the primary presentation in several dashboard views

**Status:** OPEN  
**Severity:** P2  
**Area:** AI Q&A / Copilot / Benchmark

The supplied screenshots show large raw JSON blocks in the user-facing dashboard.

### Required fix

Keep raw JSON available as an expandable evidence/debug section, but present the key facts in human-readable tables/cards first.

---

## ISSUE-031 — AI Q&A evidence table contains opaque UUIDs without transaction context

**Status:** P2  
**Area:** Finance AI Q&A

Evidence rows show match IDs and scores but do not immediately expose:

- source transaction IDs,
- amounts,
- dates,
- references,
- reason for matching.

### Required fix

Allow an evaluator/controller to drill from an AI answer to the exact underlying financial records.

---

## ISSUE-032 — Dashboard labels need explicit distinction between "records", "transactions", "matches", and "decisions"

**Status:** P1  
**Area:** Entire dashboard

The project uses all of these terms:

- records
- logical transactions
- matches
- decisions
- candidate matches
- exceptions

The benchmark currently demonstrates that these can be numerically different.

### Required fix

Create a data dictionary and use the terminology consistently throughout all 12 views.

---

# P1 — End-to-End Verification Requirements

## ISSUE-033 — No final cross-page reconciliation test exists

**Status:** OPEN  
**Severity:** P1

Create an automated invariant suite that fetches all reporting endpoints for one run and verifies:

### Core population invariants

- source counts
- logical transaction count
- match count
- decision count
- exception count

### Financial invariants

`Gross - Fees - Taxes - Refunds = Expected Net`

`Actual Bank Credits - Expected Net = Settlement Variance`

### Workflow invariants

- unresolved decisions correspond to open exceptions,
- resolved exceptions have corresponding audit events,
- human decisions update the exception state,
- assignments/notes create audit evidence.

### UI/API invariants

Every dashboard KPI must equal the corresponding API value.

---

## ISSUE-034 — Fresh-run reproducibility is required

**Status:** OPEN  
**Severity:** P1

Create a clean test run with a known dataset containing at least:

1. exact 3-way match,
2. corrupted UTR,
3. amount mismatch,
4. missing bank credit,
5. duplicate gateway charge,
6. duplicate bank settlement,
7. fee/tax scenario,
8. refund scenario,
9. delayed settlement,
10. ambiguous candidate.

Record the expected result for every logical transaction.

### Acceptance criteria

The dashboard reproduces the expected classifications without manual database edits.

---

## ISSUE-035 — Negative/abuse cases need explicit testing

**Status:** OPEN  
**Severity:** P1

Test:

- duplicate webhook,
- invalid webhook signature,
- missing reference,
- malformed amount,
- unsupported currency,
- repeated transaction ID,
- replayed event,
- extremely high amount,
- zero amount,
- negative amount,
- missing source,
- invalid exception ID,
- stale investigation,
- failed Groq response,
- malformed Groq response,
- database unavailable,
- API unavailable.

### Acceptance criteria

Failures are handled safely and do not silently mutate financial state.

---

# P1 — Groq/AI Safety & Reliability Verification

## ISSUE-036 — Groq failure/fallback behavior must be tested

**Status:** OPEN  
**Severity:** P1

Force:

- missing API key,
- invalid API key,
- timeout,
- rate limit,
- malformed response,
- model/API failure.

### Required behavior

The system must never display a successful AI investigation when the Groq request failed.

If deterministic fallback exists, label it clearly as:

`Deterministic fallback — Groq unavailable`

---

## ISSUE-037 — AI must not invent financial numbers

**Status:** OPEN  
**Severity:** P1

Run adversarial questions such as:

- "What will our revenue be next year?"
- "What was the exact bank fee for transaction XYZ?" when absent
- "Assume transaction ABC was approved; explain why."
- "Tell me the customer's name" when not in DB.

### Acceptance criteria

The assistant either:

- answers from verified database evidence,
- states that the requested information is unavailable,
- or clearly identifies assumptions.

---

# P2 — Data / State Management

## ISSUE-038 — Dashboard should expose the active reconciliation run

**Status:** OPEN  
**Severity:** P2

The backend supports `run_id` filters, but the visible dashboard does not consistently expose which run generated the displayed KPIs.

### Required fix

Show:

- active run ID,
- run creation time,
- source record count,
- run status.

This is essential for reproducibility.

---

## ISSUE-039 — Dashboard refresh must not silently mix historical runs

**Status:** VERIFY  
**Severity:** P1

Test:

1. run A,
2. ingest/run B,
3. refresh each page,
4. verify all metrics refer to the same intended run/population.

### Acceptance criteria

No page silently combines records from unrelated runs unless explicitly configured as an all-runs view.

---

# P2 — Documentation / Evaluator Readiness

## ISSUE-040 — Benchmark claims must be separated from live production-state metrics

**Status:** OPEN  
**Severity:** P1

The application contains benchmark metrics and live operational metrics in adjacent views.

### Required fix

Every benchmark number must be labelled:

`Evaluation-only`

and every live number:

`Live PostgreSQL state`

Do not reuse benchmark precision/recall/F1 as current production KPI values.

---

# Required Fix Order

Fix in this order. Do not skip directly to UI polish.

1. **ISSUE-001** — Funnel population mismatch
2. **ISSUE-002** — Reconciliation-rate denominator
3. **ISSUE-003** — Hardcoded matched-record multiplier
4. **ISSUE-004** — Hardcoded precision/recall/F1
5. **ISSUE-005** — Throughput hardcoding/N/A mismatch
6. **ISSUE-006** — Settlement vs cash expected amount
7. **ISSUE-007** — Settlement variance vs zero exposure
8. **ISSUE-008** — Source-health artificial distribution
9. **ISSUE-009** — Unreachable ANOMALOUS branch
10. **ISSUE-010** — ML threshold inconsistency
11. **ISSUE-011** — Benchmark scenario arithmetic
12. **ISSUE-012/013/014** — Benchmark population definitions
13. **ISSUE-015/016/017/018** — AI/Groq grounding
14. **ISSUE-019/020/021** — Duplicate/settlement exposure
15. **ISSUE-022/023/024/025** — Exception workflow
16. **ISSUE-026/027/028** — Forecast methodology
17. **ISSUE-032** — Data terminology
18. **ISSUE-033/034/035** — End-to-end invariant/negative tests
19. **ISSUE-036/037** — Groq failure/adversarial tests
20. **ISSUE-038/039/040** — Run isolation/evaluator clarity
21. UI polish: **ISSUE-029/030/031**

---

# Definition of Done

The project is not considered evaluator-ready until all P0 issues are closed and the following are demonstrated from a fresh run:

- [ ] All 12 Streamlit navigation features load without errors.
- [ ] Every displayed KPI is traceable to live API/database state.
- [ ] Funnel totals reconcile.
- [ ] Reconciliation rate has a documented denominator.
- [ ] Settlement equation reconciles exactly.
- [ ] Cash position and settlement pages agree on financial semantics.
- [ ] Source health is calculated independently for each feed.
- [ ] ML probabilities match the actual loaded model output.
- [ ] ML decision thresholds are enforced exactly.
- [ ] Benchmark metrics are computed, not hardcoded.
- [ ] Benchmark populations reconcile.
- [ ] Exception workflow actions mutate DB state correctly.
- [ ] Every material state transition creates an audit event.
- [ ] Groq investigation is proven live from a fresh UI action.
- [ ] Groq output passes schema validation.
- [ ] Groq failure cannot masquerade as successful AI output.
- [ ] Finance Q&A answers are reproducible from PostgreSQL.
- [ ] Unsupported questions do not produce fabricated financial facts.
- [ ] Forecast methodology matches implementation.
- [ ] Duplicate exposure is not double-counted.
- [ ] Fresh-run test dataset produces expected classifications.
- [ ] Negative/security/failure cases pass.
- [ ] Final screenshots show no misleading truncation or contradictory numbers.

---

# Evidence Basis

This backlog was prepared from the supplied Project Sentinel dashboard captures/PDFs and the supplied project/code/audit material.

Key evidence sets include:

- `Project Sentinel _ AI Finance Controller.pdf` — Benchmark & Model Evaluation
- `Project Sentinel _ AI Finance Controller1.pdf` — Audit Timeline & Operational Controls
- `Project Sentinel _ AI Finance Controller2.pdf` — AI Finance Brief & Copilot / Finance Q&A / exception evidence
- `Project Sentinel _ AI Finance Controller3.pdf` — Grounded Finance Controller AI Q&A
- `Project Sentinel _ AI Finance Controller4.pdf` — Cash Position & 7-Day Forecast
- supplied standalone dashboard screenshot — Feed Source Health & Data Quality
- supplied source/audit material containing FinanceController, SourceHealthService, forecast, Groq verification, and benchmark implementation details

## Evidence policy

A future fix must include:

1. issue ID,
2. root cause,
3. files changed,
4. test command(s),
5. before/after API values,
6. before/after UI verification,
7. database verification where relevant,
8. explicit statement that no unrelated metrics regressed.
