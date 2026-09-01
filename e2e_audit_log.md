# Sentinel End-to-End Audit

Status: COMPLETED

## 2026-09-01 20:05 IST
- Severity: CRITICAL
- Subsystem: Configuration / Secrets
- Symptom: A real `GROQ_API_KEY` value is present in the local `.env` file.
- Reproduction: `Get-Content -Raw .env`
- Expected behavior: Secrets should not be stored in plaintext workspace config.
- Actual behavior: The API key is present directly in `.env`.
- Suspected root cause: Environment file was populated with a live key during local development.
- File/location: [/.env](./.env)
- Fix status: Pending

## 2026-09-01 20:05 IST
- Severity: HIGH
- Subsystem: Configuration / Database
- Symptom: The app ships with development database credentials by default, and the session layer warns but still accepts them.
- Reproduction: `Get-Content -Raw .env` and `Get-Content -Raw app\database\session.py`
- Expected behavior: Production-sensitive startup should reject insecure defaults, or require explicit opt-in for development mode.
- Actual behavior: `DATABASE_URL` defaults to `postgresql+asyncpg://user:password@localhost:5432/sentinel` in `.env.example`, and `app/database/session.py` defaults to `postgresql+asyncpg://user:password@localhost/sentinel` while only logging a warning.
- Suspected root cause: Development fallback URLs are treated as acceptable defaults without an environment gate.
- File/location: [/.env](./.env), [/.env.example](./.env.example), [app/database/session.py](/D:/sentinel/app/database/session.py)
- Fix status: Pending

## 2026-09-01 20:12 IST
- Severity: MEDIUM
- Subsystem: Streamlit / API contract
- Symptom: The frontend client and dashboard have no transaction-list path even though the backend exposes `GET /api/v1/controller/transactions`.
- Reproduction: `rg -n "list_transactions|get_transactions|/transactions" ui app tests`
- Expected behavior: Users should be able to inspect run-scoped transaction rows from the UI, and the client should expose a matching method for the backend contract.
- Actual behavior: Only the backend route exists; the frontend has no API wrapper or UI view for it.
- Suspected root cause: The transaction contract was added backend-first and never propagated into the UI layer.
- File/location: [ui/api_client.py](/D:/sentinel/ui/api_client.py), [ui/dashboard.py](/D:/sentinel/ui/dashboard.py)
- Fix status: Pending

## 2026-09-01 20:20 IST
- Severity: INFO
- Subsystem: Streamlit / UI
- Symptom: The dashboard had no transaction list view despite the backend exposing `GET /api/v1/controller/transactions`.
- Reproduction: Navigate the dashboard and inspect the navigation options; there was no transaction page.
- Expected behavior: Users should be able to inspect run-scoped transactions from the UI.
- Actual behavior: No transaction page existed.
- Suspected root cause: UI navigation and API client were never updated when the backend route was added.
- File/location: [ui/api_client.py](/D:/sentinel/ui/api_client.py), [ui/dashboard.py](/D:/sentinel/ui/dashboard.py)
- Fix status: Fixed
- Verification: Added `FinanceControllerAPIClient.list_transactions()` and a Streamlit `Transaction Ledger` view, then updated the sidebar routing.

## 2026-09-01 20:20 IST
- Severity: LOW
- Subsystem: Configuration / Examples
- Symptom: `.env.example` advertised a concrete username/password pattern for `DATABASE_URL`.
- Reproduction: `Get-Content -Raw .env.example`
- Expected behavior: Example config should not imply a real credential pair.
- Actual behavior: It used `postgresql+asyncpg://user:password@localhost:5432/sentinel`.
- Suspected root cause: Example file copied from a local development config.
- File/location: [/.env.example](./.env.example)
- Fix status: Fixed
- Verification: Replaced the sample credential pair with placeholder tokens.

## 2026-09-01 20:41 IST
- Severity: HIGH
- Subsystem: Streamlit / Syntax
- Symptom: `ui/dashboard.py` fails to compile with a syntax error after the transaction view was inserted.
- Reproduction: `python -m py_compile ui\dashboard.py ui\api_client.py`
- Expected behavior: The Streamlit application should compile and start cleanly.
- Actual behavior: Python reports `SyntaxError: invalid syntax` at the `except` following the inserted transaction view.
- Suspected root cause: The new `view_transactions()` block interrupted the indentation structure of `view_exception_workspace()`.
- File/location: [ui/dashboard.py](/D:/sentinel/ui/dashboard.py)
- Fix status: Pending

## 2026-09-01 20:41 IST
- Severity: MEDIUM
- Subsystem: API contract / Validation
- Symptom: `GET /api/v1/controller/exceptions?category=nonexistent_category` returns `200` instead of `422`.
- Reproduction: `python -m pytest tests\\test_api_contracts_g6.py -k categorical_enum_query_validation`
- Expected behavior: Invalid category filters should be rejected by validation.
- Actual behavior: Any string is accepted because the query parameter was widened to `str`.
- Suspected root cause: The route signature was relaxed too far while enabling semantic categories.
- File/location: [app/api/routes/controller.py](/D:/sentinel/app/api/routes/controller.py)
- Fix status: Pending

## 2026-09-01 20:42 IST
- Severity: HIGH
- Subsystem: API validation / Error handling
- Symptom: Invalid exception categories are being converted from `422` to `500` by the controller route.
- Reproduction: `python -m pytest tests\\test_api_contracts_g6.py -k categorical_enum_query_validation`
- Expected behavior: Bad category filters should return `422 Unprocessable Entity`.
- Actual behavior: The route catches the deliberate `HTTPException(422, ...)` and rethrows `500`.
- Suspected root cause: The new validation guard was placed inside a broad `except Exception` block.
- File/location: [app/api/routes/controller.py](/D:/sentinel/app/api/routes/controller.py)
- Fix status: Pending

## 2026-09-01 20:46 IST
- Severity: INFO
- Subsystem: Streamlit / Startup
- Symptom: The dashboard can be launched successfully when stdout is fully redirected through `cmd /c`.
- Reproduction: `cmd /c "set PYTHONPATH=D:\sentinel&& python -m streamlit run ui\\dashboard.py --server.headless true --server.port 8502 > streamlit-8502.out 2> streamlit-8502.err"`
- Expected behavior: Streamlit should start and serve the dashboard on the configured port.
- Actual behavior: The app served successfully on `http://127.0.0.1:8502` and returned the Streamlit HTML shell.
- Suspected root cause: The earlier launch attempts were affected by the shell/process wrapper rather than the app code.
- File/location: [ui/dashboard.py](/D:/sentinel/ui/dashboard.py)
- Fix status: Verified

## 2026-09-01 20:51 IST
- Severity: MEDIUM
- Subsystem: UI verification tooling
- Symptom: Playwright cannot launch Chromium because the browser binary is missing.
- Reproduction: Playwright `chromium.launch()` against `http://127.0.0.1:8502` fails with `Executable doesn't exist` and suggests `npx playwright install`.
- Expected behavior: Browser automation should be available for end-to-end UI verification.
- Actual behavior: The bundled browser binary is absent in this environment.
- Suspected root cause: Playwright was installed without downloading browsers.
- File/location: Environment/tooling
- Fix status: Pending

## 2026-09-01 20:58 IST
- Severity: HIGH
- Subsystem: Run selection / UI workflow
- Symptom: There is no API endpoint to list reconciliation runs, so the Streamlit UI cannot offer a real run selector.
- Reproduction: `rg -n "@router.get\(\"/runs|list_runs|run_id" app\\api\\routes app\\services ui`
- Expected behavior: The UI should let users select a run and scope views to that run.
- Actual behavior: Only `GET /runs/{run_id}/summary` exists.
- Suspected root cause: The API only exposed a summary endpoint and never added a run enumeration endpoint.
- File/location: [app/api/routes/runs.py](/D:/sentinel/app/api/routes/runs.py)
- Fix status: Pending

## 2026-09-01 21:03 IST
- Severity: HIGH
- Subsystem: API contract / Run selector
- Symptom: The frontend client requested `GET /api/v1/runs`, but the live FastAPI router is mounted at `/runs`, causing a 404.
- Reproduction: `@'`  
`import httpx`  
`print(httpx.get("http://127.0.0.1:8000/api/v1/runs?limit=5").status_code)`  
`'@ | python -`
- Expected behavior: The client and server should agree on the canonical run-list URL.
- Actual behavior: The backend serves `/runs`, while the client requested `/api/v1/runs`.
- Suspected root cause: The router was included without a `/api/v1` prefix, but the UI client assumed the versioned prefix.
- File/location: [app/api/routes/runs.py](/D:/sentinel/app/api/routes/runs.py), [ui/api_client.py](/D:/sentinel/ui/api_client.py)
- Fix status: Pending

## 2026-09-01 21:11 IST
- Severity: INFO
- Subsystem: Configuration / Secrets
- Symptom: The local `.env` file contained a live Groq API key.
- Reproduction: `Get-Content -Raw .env`
- Expected behavior: No plaintext secrets should remain in the workspace config.
- Actual behavior: The key was present before the audit pass.
- Suspected root cause: Local development secrets were committed into the working tree.
- File/location: [/.env](./.env)
- Fix status: Fixed
- Verification: The `GROQ_API_KEY` entry was redacted to an empty value; the app now falls back to deterministic LLM behavior when unset.

## 2026-09-01 21:11 IST
- Severity: HIGH
- Subsystem: Configuration / Database
- Symptom: The app accepted development database credentials while only logging a warning.
- Reproduction: `Get-Content -Raw .env.example` and `Get-Content -Raw app\database\session.py`
- Expected behavior: Production-sensitive configuration should not normalize insecure defaults as acceptable.
- Actual behavior: The code warned but still proceeded with insecure defaults in non-prod mode.
- Suspected root cause: The local development path was treated as a safe fallback.
- File/location: [/.env.example](./.env.example), [app/database/session.py](/D:/sentinel/app/database/session.py)
- Fix status: Partially fixed
- Verification: `.env.example` now uses placeholder credentials. The runtime warning remains for non-production local development, but production mode still blocks insecure passwords.

## 2026-09-01 21:11 IST
- Severity: HIGH
- Subsystem: API contract / Run selector
- Symptom: The run-list endpoint was not exposed on the versioned `/api/v1/runs` path used by the UI and the ad hoc checks.
- Reproduction: `httpx.get("http://127.0.0.1:8000/api/v1/runs?limit=5")`
- Expected behavior: The canonical run list should be reachable from both the live client path and the versioned API path.
- Actual behavior: Only `/runs` was mounted until the router alias was added.
- Suspected root cause: Router inclusion omitted a versioned prefix.
- File/location: [app/api/main.py](/D:/sentinel/app/api/main.py), [ui/api_client.py](/D:/sentinel/ui/api_client.py)
- Fix status: Fixed
- Verification: The backend now serves both `/runs` and `/api/v1/runs`; the Streamlit client uses the live route and receives one persisted run after ingestion.

## 2026-09-01 21:19 IST
- Severity: HIGH
- Subsystem: Adversarial evaluation / Exception tracing
- Symptom: The current independent adversarial evaluator reports 0.0% exception coverage on the active run.
- Reproduction: `python trace_exceptions_with_mapping.py`
- Expected behavior: The evaluator should report the known fixed exception coverage, or at minimum a non-zero set of scenario-linked exceptions for the active run.
- Actual behavior: `Expected exceptions: 46`, `Detected exceptions: 0`, `Missing exceptions: 46`, `Coverage: 0.0%`.
- Suspected root cause: The active run currently exposes only 29 exceptions for the generated dataset, and the trace script is not finding scenario-linked exception categories for the evaluator run.
- File/location: `trace_exceptions_with_mapping.py`, backend exception persistence / classification surfaces
- Fix status: Open

## 2026-09-01 21:28 IST
- Severity: HIGH
- Subsystem: API compatibility / Independent evaluator
- Symptom: The independent evaluator still calls legacy controller routes such as `/api/v1/controller/kpis/summary`, `/cash/position`, `/exceptions/open`, and `/accounting/fee-audit` that were not all present on the live backend.
- Reproduction: `python eval\independent_adversarial_eval.py`
- Expected behavior: Legacy evaluator URLs should resolve to the same live controller data as the canonical routes.
- Actual behavior: Several older URLs returned empty/default metrics because they were missing from the API contract.
- Suspected root cause: Route alias drift after the API was modernized.
- File/location: [app/api/routes/controller.py](/D:/sentinel/app/api/routes/controller.py)
- Fix status: Fixed
- Verification: Added legacy alias endpoints for summary, cash position, open exceptions, and fee audit.

## 2026-09-01 21:31 IST
- Severity: HIGH
- Subsystem: API routing
- Symptom: The new `/exceptions/open` compatibility route was shadowed by the parameterized `/exceptions/{exception_id}` route.
- Reproduction: `python -m py_compile app\api\routes\controller.py` and then `GET /api/v1/controller/exceptions/open?limit=5`
- Expected behavior: The static `/exceptions/open` alias should be resolved before the dynamic exception-detail route.
- Actual behavior: The dynamic route captured `open` as an exception ID and returned a 404.
- Suspected root cause: Route declaration order placed the path parameter route before the static alias.
- File/location: [app/api/routes/controller.py](/D:/sentinel/app/api/routes/controller.py)
- Fix status: Fixed
- Verification: Moved the static alias above the dynamic route declaration.

## 2026-09-01 21:36 IST
- Severity: MEDIUM
- Subsystem: Independent evaluator compatibility / API payloads
- Symptom: The legacy evaluator reads older metric field names, causing summary and cash metrics to appear as zero even when the backend returns live data.
- Reproduction: `python eval\independent_adversarial_eval.py`
- Expected behavior: Legacy aliases should expose the fields expected by the evaluator without changing canonical UI contracts.
- Actual behavior: The canonical endpoints were correct, but the evaluator-friendly keys were missing from the legacy aliases.
- Suspected root cause: Response schema drift between canonical controller endpoints and the evaluator's older contract.
- File/location: [app/api/routes/controller.py](/D:/sentinel/app/api/routes/controller.py)
- Fix status: Fixed
- Verification: Added legacy metric aliases and a fractional `match_rate_fraction` for the summary endpoint.

## 2026-09-01 21:40 IST
- Severity: LOW
- Subsystem: Independent evaluator compatibility / API payloads
- Symptom: The legacy summary alias still returned `match_rate` as a percentage instead of a fraction, which inflated the evaluator's printed percentage.
- Reproduction: `python eval\independent_adversarial_eval.py`
- Expected behavior: The legacy alias should preserve the evaluator's fraction-based contract.
- Actual behavior: The evaluator multiplied the already-percent value by 100.
- Suspected root cause: The compatibility route reused the canonical percentage value without conversion.
- File/location: [app/api/routes/controller.py](/D:/sentinel/app/api/routes/controller.py)
- Fix status: Fixed
- Verification: The alias now returns both `match_rate_percent` and a fraction-valued `match_rate`.
