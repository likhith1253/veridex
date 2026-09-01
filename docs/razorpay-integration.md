# Razorpay Test Mode Connector & Settlement Webhook Engine

## Overview

Project Sentinel integrates natively with Razorpay's payment infrastructure to ingest real-time and batch financial events, perform cryptographic signature verification, enforce durable idempotency, and execute incremental multi-source financial reconciliation across Gateway, Ledger, and Bank feeds.

---

## 1. Environment Configuration

Sentinel uses standard environment variables to configure connectivity with Razorpay APIs and webhook endpoints.

| Variable | Type | Default | Description |
|---|---|---|---|
| `RAZORPAY_KEY_ID` | String | `""` | Razorpay API Key ID (e.g. `rzp_test_...`) |
| `RAZORPAY_KEY_SECRET` | String | `""` | Razorpay API Key Secret |
| `RAZORPAY_WEBHOOK_SECRET` | String | `rzp_test_secret_sentinel` | HMAC-SHA256 secret for verifying webhook payloads |
| `RAZORPAY_MODE` | String | `test` | Gateway operating mode (`test` or `live`) |
| `RAZORPAY_BASE_URL` | String | `https://api.razorpay.com/v1` | Razorpay API Base URL |

> **Security Invariant**: `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are strictly masked. They are never logged to console/files, never exposed in JSON API responses, and never stored in client-side state.

---

## 2. API Endpoints

### 2.1 Get Integration Status
- **Endpoint**: `GET /api/v1/integrations/razorpay/status`
- **Authentication**: Bearer API Key
- **Response**:
```json
{
  "configured": true,
  "mode": "test",
  "key_id_prefix": "rzp_test...",
  "webhook_configured": true,
  "api_reachable": true,
  "last_sync_at": "2026-09-01T19:30:21Z",
  "last_webhook_at": "2026-09-01T19:35:12Z",
  "last_error": null
}
```

### 2.2 Synchronize Payments Feed
- **Endpoint**: `POST /api/v1/integrations/razorpay/sync/payments`
- **Payload**:
```json
{
  "limit": 50,
  "skip": 0,
  "auto_reconcile": true,
  "use_fallback_if_unconfigured": true
}
```
- **Response**:
```json
{
  "source": "razorpay_test",
  "mode": "test",
  "entity_type": "payments",
  "records_fetched": 50,
  "records_normalized": 50,
  "records_rejected": 0,
  "run_id": "rzp_sync_pay_1788291044",
  "duration_ms": 14.2,
  "reconciliation_summary": {
    "total_processed": 50,
    "matched_count": 48,
    "exception_count": 2
  }
}
```

### 2.3 Synchronize Settlements Feed
- **Endpoint**: `POST /api/v1/integrations/razorpay/sync/settlements`
- **Payload**:
```json
{
  "limit": 20,
  "auto_reconcile": true,
  "use_fallback_if_unconfigured": true
}
```

---

## 3. Webhook Intake Engine

### 3.1 Public Endpoint
- **Endpoint**: `POST /api/v1/webhooks/razorpay`
- **Authentication**: Cryptographic HMAC-SHA256 Header (`X-Razorpay-Signature`)

### 3.2 HMAC Signature Verification Flow
```
Incoming HTTP Request -> Read Raw Request Bytes -> Compute HMAC-SHA256(secret, raw_bytes)
                                                     |
               --------------------------------------
               |                                    |
            Matches                              Mismatch
               |                                    |
      Check Event Idempotency               HTTP 400 Bad Request
               |                          (Invalid HMAC Signature)
               v
      Incrementally Reconcile
```

1. The raw request body is read as unparsed bytes (`await request.body()`).
2. An HMAC-SHA256 hash is computed using the configured `RAZORPAY_WEBHOOK_SECRET`.
3. `hmac.compare_digest` is used to prevent timing attacks.
4. If invalid, the request is immediately rejected with `400 Bad Request`.

### 3.3 Durable Idempotency
Every incoming webhook event is recorded in the PostgreSQL table `webhook_events`:
- **`event_id`**: Unique Razorpay event ID (`evt_...`).
- **`status`**: `PROCESSING` -> `PROCESSED`.
- **Replay Protection**: Duplicate deliveries return HTTP 200 with status `DUPLICATE_IGNORED` and the original result without re-executing business logic or creating duplicate transactions.

---

## 4. Normalization Rules

Razorpay entity payloads are converted to Sentinel canonical `Transaction` models using exact financial precision:

1. **Monetary Units**: Amounts in paise (integer) are converted to INR `Decimal` by dividing by `Decimal("100")`.
2. **Timestamps**: Unix epoch timestamps are converted to timezone-aware UTC `datetime` instances.
3. **Fee & Tax Accounting**:
   - Fees (2% MDR) and GST (18% on fees) are extracted and audited.
   - Bank UTR and reference numbers (`acquirer_data.utr`, `acquirer_data.rrn`) are mapped into `reference_number`.

---

## 5. Controlled Synthetic Simulation Fallback

When Razorpay credentials are not yet configured in a development or offline demo environment:
- The connector falls back safely to realistic synthetic simulation feeds when `use_fallback_if_unconfigured=True`.
- The response explicitly flags `"source": "synthetic_fallback"` and includes a descriptive warning in the response body.
- No network timeouts or unhandled exceptions are surfaced to callers.
