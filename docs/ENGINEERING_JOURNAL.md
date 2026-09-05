# Engineering Journal

This is a deliberately honest record of real bugs found — and fixed — while
building and deploying VERIDEX, plus the design decisions behind why the
system is shaped the way it is. Most demo projects show you the finished
product. This document shows the actual debugging trail, because the
debugging trail is the more honest signal of engineering quality.

Every entry below is real: found by testing the live deployed instance
end-to-end (not just localhost), root-caused to an exact line, fixed, and
re-verified — usually by reproducing the failure locally first so the fix
could be confirmed against a real stack trace, not a guess.

## Design principles, and why

**Single source of truth.** Every KPI shown anywhere — Command Center,
Reconciliation, Benchmark, Copilot answers — is computed once, by
`FinanceController.get_summary_kpis()`, and read from everywhere else. This
wasn't a "clean architecture" preference; it came from directly observing
what happens without it (see the Copilot bug below): two screens quietly
disagreeing about the same number, with no way for an operator to know
which one to trust.

**Deterministic → ML → LLM, in that order, and only as far as needed.**
Exact-match reconciliation runs first because it's fast, free, and fully
explainable. ML arbitration only sees what deterministic matching couldn't
resolve. An LLM investigation only runs for exceptions that survive both —
and even then, it explains a conclusion grounded in real linked transaction
records, it doesn't invent one. This keeps the expensive, harder-to-verify
step rare and bounded, rather than the default path for every record.

**Humans authorize, machines never execute.** Every corrective action —
write-off, adjustment, escalation — is *recommended*, never applied, until
an operator explicitly approves it. Policy ceilings (max adjustment, max
write-off) are enforced server-side, not just displayed as a suggestion.

## Real bugs found deploying to Neon + Render + Vercel

These were found by deliberately testing the live URL the way an evaluator
would — clicking through, running real batches, asking the Copilot real
questions, sending real signed webhooks — rather than only trusting a
green local test suite.

### 1. `webhook_events` table missing from a freshly migrated database
The `WebhookEvent` ORM model existed, but no Alembic migration was ever
authored for it — the table only ever existed in environments where someone
had manually run `Base.metadata.create_all()`, which silently masked the gap
in local development. Neon, provisioned purely via `alembic upgrade head`,
never got it. Every real Razorpay webhook crashed with
`UndefinedTableError`.
**Fix:** authored the missing migration, verified it against a genuinely
fresh database, and — since this class of drift can recur — added a
FastAPI startup hook that runs `alembic upgrade head` automatically on
boot, in a worker thread so it doesn't collide with the running event loop.

### 2. Reconciliation modal stuck on "Reconciling…" forever
A real batch completed successfully on Render, but the browser never found
out — the modal just sat there indefinitely. Root cause: Vercel's proxy
route held the connection open for the full duration of the upstream call,
but had no `maxDuration` set, so the platform silently killed the
connection before a slow batch (60–180s, real per-exception LLM
investigation) could finish. Render kept working; the browser just never
received the response.
**Fix:** set `maxDuration = 300` on the proxy route.

### 3. Crash recommending an action against a real run
`ensure_run_exists()` checked only the `ReconciliationRun.id` column, but a
run is also addressable by its separate human-readable `run_id` column.
Passing a real run's `run_id` string caused the lookup to miss, which then
tried to insert a duplicate placeholder row — colliding with the real row's
`run_id` unique constraint. The first fix (check both columns) surfaced a
second, deeper issue: `finance_actions.run_id` has a foreign key against
`reconciliation_runs.id` specifically, so even after the row was correctly
found, the raw human-readable string still failed the FK check on insert.
**Fix:** `ensure_run_exists()` now returns the row's real `id`, and callers
use that returned value instead of echoing back whatever string they were
given.

### 4. Copilot returning a different match rate than every dashboard
Asked "what's our reconciliation rate," the Copilot answered 97.02%. Every
dashboard on the same page said 82.45%. Root cause: this one Copilot branch
computed its own match rate directly from `COUNT(DISTINCT transaction_id)
FROM match_transactions`, instead of calling `get_summary_kpis()` like
everything else — a bare match row without a confirming `Decision(AUTO_MATCH)`
still counted as "matched" under that query, which is not what "matched"
means anywhere else in the system.
**Fix:** rewired the branch to call the same authoritative method. The test
that covered this had been asserting the *old* (wrong) numbers without
anyone noticing — its fixture didn't include the `Decision` row that
actually makes a transaction count as matched, so it was quietly validating
the bug.

### 5. Crash on a second webhook for an already-processed settlement
A genuinely realistic scenario — Razorpay resending `settlement.processed`
with a new event ID for a settlement already seen — crashed with
`AttributeError: 'str' object has no attribute 'id'`.
`TransactionRepository.get_orm_by_source_and_domain_id()` already returns
the transaction's id as a plain string (its own docstring and return type
say so), but the webhook handler called `.id` on that string as if it were
still the ORM row.
**Fix:** use the returned id directly. Reproduced locally with a full
traceback before touching the fix, to make sure the diagnosis was right
before writing the patch.

## What this list is *not*

It's not exhaustive, and it's not evidence the system is fragile — it's
evidence that the system was actually deployed and actually exercised
against real infrastructure (Neon's connection pooler, Render's cold
starts, Vercel's function limits) rather than only ever run against a
warm local Postgres instance. Every one of these was caught by deliberately
testing the deployed instance the way a user or evaluator actually would,
not by code review alone.
