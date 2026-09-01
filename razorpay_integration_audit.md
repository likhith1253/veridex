# Project Sentinel — Phase 2: Razorpay Integration Architecture Audit
**Document Type:** Backend & Payments Integration Audit  
**Author:** Senior Backend & Payments Integration Engineer  
**Baseline Test Status:** 395/395 tests passing (0 failures)  
**Date:** September 2, 2026  

---

## 1. Existing Relevant Architecture

Project Sentinel's core is composed of clean, decoupled modules:
1. **Domain Models (`app/models/transaction.py`):** `Transaction` with `txn_id`, `source` (`GATEWAY`, `LEDGER`, `BANK`), `reference_number` (UTR/RRN), `amount` (Decimal), `currency`, `timestamp`, `fee`, `tax`, `status`, `order_id`, `metadata`.
2. **Reconciliation Engines:**
   - **Batch Pipeline (`app/services/reconciliation.py`):** Multi-source candidate generation, deterministic matching ($c \ge 0.90$), XGBoost feature scoring ($0.70 \le c < 0.90$), decision policy, and exception classification.
   - **Incremental Pipeline (`app/services/incremental_reconciliation.py`):** Real-time single transaction / micro-batch ingestion, candidate scoping ($\pm 3$ days), idempotency check, matching, and exception generation.
3. **Database & Persistence (`app/database/`):**
   - PostgreSQL async engine (`asyncpg` + SQLAlchemy 2.0).
   - Repositories: `TransactionRepository`, `MatchRepository`, `DecisionRepository`, `ExceptionRepository`, `AuditRepository`, `ReconciliationRepository`, `InvestigationRepository`.
4. **API Layer (`app/api/`):**
   - FastAPI application with CORS, security headers (`nosniff`, `DENY`), API key authentication middleware (`verify_api_key`), and structured exception handlers.
   - Routes: `controller.py`, `runs.py`, `reconciliation.py`, `investigations.py`, `health.py`, `integrations.py`.
5. **Existing Integrations (`app/integrations/razorpay_adapter.py`):**
   - Initial webhook parsing logic for `payment.captured`.
   - HMAC-SHA256 signature verification stub.

---

## 2. Integration Points Discovered & Reusable Components

| Component | File Path | Role in Phase 2 | Status |
|---|---|---|---|
| `Transaction` Model | `app/models/transaction.py` | Canonical model for normalized Razorpay payments, orders, and settlements. | **Reuse As-Is** |
| `IncrementalReconciliationService` | `app/services/incremental_reconciliation.py` | Core engine for real-time webhook and synced transaction processing. | **Reuse & Extend** |
| `ReconciliationService` | `app/services/reconciliation.py` | Batch reconciliation for synchronized historical feeds. | **Reuse As-Is** |
| `AuditRepository` & `AuditEvent` | `app/database/models/audit.py` | Immutable audit logging for all Razorpay sync and webhook operations. | **Reuse & Extend** |
| `RazorpayAdapter` | `app/integrations/razorpay_adapter.py` | Upgrade into modular `app/integrations/razorpay/` package. | **Refactor & Extend** |
| Integrations Router | `app/api/routes/integrations.py` | Mount payment sync, settlement sync, status, and webhook endpoints. | **Extend** |

---

## 3. Required New Components for Phase 2

1. **`app/integrations/razorpay/config.py`:**
   - Secure configuration loading: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_MODE` (`test` vs `live`).
   - Helper methods to provide non-sensitive status metadata (prefix, mode, configured boolean) while shielding secrets.
2. **`app/integrations/razorpay/client.py`:**
   - Asynchronous HTTPS client (`httpx.AsyncClient`) with Basic Auth (`key_id:key_secret`).
   - Configurable timeout (10s), exponential backoff retries (3 attempts), rate-limit handling (HTTP 429), and structured error typing.
   - Methods: `fetch_payments()`, `fetch_payment_by_id()`, `fetch_orders()`, `fetch_settlements()`, `fetch_settlement_by_id()`, `fetch_combined_recon()`.
3. **`app/integrations/razorpay/normalizer.py`:**
   - Translates Razorpay entity schemas (paise to INR Decimal, epoch timestamps to UTC datetime, fee & GST breakdowns, UTR / RRN extraction) into canonical Sentinel `Transaction` models.
4. **`app/integrations/razorpay/webhook_handler.py`:**
   - Raw byte HMAC-SHA256 signature verification.
   - Durable idempotency check against a dedicated `WebhookEventORM` table (or hash-based audit event check).
   - Event dispatcher handling `settlement.processed`, `payment.captured`, `payment.failed`, `refund.processed`.
5. **`app/integrations/razorpay/service.py`:**
   - Orchestration service executing payment sync, settlement sync, order mapping, and automatic reconciliation dispatch.
6. **`app/database/models/webhook_event.py` (and migration/model registration):**
   - Durable table for tracking received webhook IDs, event types, payloads, timestamps, and processing statuses for idempotency.
7. **`app/api/routes/integrations.py` & `app/api/routes/webhooks.py`:**
   - `GET /api/v1/integrations/razorpay/status`
   - `POST /api/v1/integrations/razorpay/sync/payments`
   - `POST /api/v1/integrations/razorpay/sync/settlements`
   - `POST /api/v1/webhooks/razorpay` (raw byte body, no API key requirement, HMAC-only).

---

## 4. Security Risks & Mitigations

1. **Secret Leakage:**
   - *Risk:* `RAZORPAY_KEY_SECRET` or `RAZORPAY_WEBHOOK_SECRET` logged in exceptions, returned in status endpoints, or passed in frontend payloads.
   - *Mitigation:* Secrets exist purely in backend memory. Status endpoint only returns `key_id_prefix` (e.g. `rzp_test_...`) and booleans. Client headers are redacted in all logs.
2. **Webhook Forgery / Replay Attack:**
   - *Risk:* Malicious actor posting forged financial events to corrupt the ledger.
   - *Mitigation:* Exact raw byte HMAC-SHA256 signature verification using `hmac.compare_digest`. Webhooks without valid signatures are rejected with HTTP 400.
3. **Webhook Duplication & Double Processing:**
   - *Risk:* Razorpay network retries causing duplicate transaction insertion or multiple reconciliation runs.
   - *Mitigation:* Durable idempotency database table with unique `event_id` constraint. Subsequent duplicate events return HTTP 200 with `status: DUPLICATE_IGNORED`.

---

## 5. Compatibility & Canonical Benchmark Invariance

- **Zero Regression on Canonical Benchmark:** All existing synthetic test suites and adversarial evaluations remain 100% operational.
- **Graceful Fallback Mode:** If `RAZORPAY_KEY_ID` or `RAZORPAY_KEY_SECRET` are not present, endpoints cleanly report `mode: synthetic` and fallback to the synthetic data simulator without crashing.
- **Independent Accounting:** Live/Test Razorpay fee and tax deductions are dynamically parsed from API payloads, completely separated from synthetic benchmark 2% MDR / 18% GST assumptions.

---

## 6. Comprehensive Test Plan

1. **Authentication & Config Tests:** Missing credentials, invalid credentials, test vs live mode flags.
2. **HTTP Client & Resilience Tests:** Mocked 200 OK, 401 Unauthorized, 429 Rate Limit, 500 Server Error, and timeout handling.
3. **Normalization Tests:** Paise-to-Rupee conversion, timestamp parsing, fee & GST extraction, metadata preservation.
4. **Webhook & Signature Tests:** Valid signature, invalid signature, missing signature, replay / duplicate idempotency.
5. **Settlement State & Ingestion Tests:** `settlement.processed` lifecycle tracking (`RAZORPAY_PROCESSED` $\rightarrow$ `BANK_CREDIT_PENDING` $\rightarrow$ `RECONCILED`).
6. **Full End-to-End Regression:** `pytest -q` (395 baseline tests + new integration tests), canonical adversarial evaluation (`100% exception detection`).
