# Security audit (October 2026)

Scope: the FastAPI backend (`app/api/**`, Razorpay integration) and the Next.js proxy route (`frontend/app/api/proxy`). Method: code review plus requests against a local in-process instance (httpx ASGI transport). No production URL was contacted. Regression tests: `tests/test_security_audit_overhaul.py`.

## Route classification

| Route(s) | Intended | Enforcement |
|---|---|---|
| `GET /`, `GET /health` | public | none |
| `POST /api/v1/webhooks/razorpay` | public, machine-to-machine | HMAC-SHA256 of raw body with `RAZORPAY_WEBHOOK_SECRET`; durable idempotency by event id |
| `/api/v1/controller/**`, `/api/v1/actions/**`, `/api/v1/integrations/**`, `/api/v1/investigations/**`, `/api/v1/settlements/**`, `/runs/**`, `/reconciliation/**` | protected | `X-API-Key` / Bearer key via `verify_api_key` router dependency |
| `POST /api/v1/integrations/razorpay/webhook` | protected legacy webhook | API key and HMAC |
| `/docs`, `/openapi.json` | public (FastAPI default) | none; the proxy does not forward them |

The app is single-tenant, so there is no per-user object ownership to check (no IDOR surface beyond "anyone with the key sees everything"). There are no debug or internal endpoints beyond `/api/v1/controller/simulate-failure` and `/benchmark`, which are protected and operate on in-memory or clearly simulated data.

## Findings and status

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | Critical | `RazorpayWebhookHandler.verify_signature` accepted HMACs made with hardcoded fallback secrets (`rzp_test_secret_sentinel`, `your_webhook_secret`) in addition to the configured one, so anyone reading the source could forge webhook events (including against the public webhook route). | Fixed: only the configured secret is accepted; with none configured every webhook is rejected. Tests set an explicit test secret. |
| 2 | High | `POST /api/v1/integrations/razorpay/webhook` skipped signature verification entirely when the `X-Razorpay-Signature` header was absent. | Fixed: signature is mandatory. |
| 3 | High | API auth failed open: with no key env var set (e.g. a misconfigured deploy) every protected route was public. | Fixed: with `ENVIRONMENT=production` and no key, protected routes return 503. Dev/test remain open for convenience. **Deploy note:** production must set `SENTINEL_API_KEY` (or `VERIDEX_API_KEY`) before this ships. |
| 4 | Medium | CORS used `allow_origins=["*"]` with credentials, and the 500 handler reflected any `Origin` with `Allow-Credentials: true`. `ALLOWED_ORIGINS` was documented but never read. | Fixed: origins come from `ALLOWED_ORIGINS` (default localhost dev origins), credentials disabled, methods and headers restricted, 500 handler only echoes allowed origins. |
| 5 | Medium | Many 500 responses returned `str(e)` (DB errors, internals) to the client. | Fixed: generic messages; details stay in server logs. Remaining `str(e)` in 400/404 responses are domain-validation messages (e.g. policy violations, "not found"). |
| 6 | Medium | Next.js proxy exposed every backend path (including the webhook receiver and docs) and echoed the raw upstream fetch error (internal URL) to the browser. | Fixed: webhooks/docs/openapi and `..` path segments are blocked; error text no longer returned. The API key itself was never exposed to the browser (server-only env var). |
| 7 | Low | API key compared with `!=` (timing side channel). | Fixed: `hmac.compare_digest`. |
| 8 | Low | Unbounded batch sizes on `/ingest/batch` and `/reconciliation/runs`. | Fixed: max 10,000 records per feed. |

## Open items

- **Public demo = effectively unauthenticated.** The proxy attaches the API key for every visitor, so anyone on the internet can use all non-blocked routes, including write routes (ingest, Razorpay sync, finance-action approvals). Acceptable for a portfolio demo with synthetic data; unacceptable with real data. Fix would need real user auth (e.g. OAuth/session) in the Next.js layer.
- **Approver identity is client-supplied** (`actor`, `recommended_by` fields): the audit trail records what the caller claims.
- **No rate limiting** in the app; webhook route is unauthenticated apart from HMAC. Use platform-level limits (Render/Vercel/Cloudflare).
- **Dependency advisories not upgraded** (pip-audit): `langgraph` 0.2.45, `langgraph-checkpoint`, `langgraph-sdk`, `langchain-core` need a major version jump that was not verified; `pytest` (dev only). npm audit: 5 high findings remain, all in the ESLint toolchain (`eslint-config-next` chain), dev-only; the suggested "fix" is a downgrade. Upgraded in this pass: `fastapi` 0.115.0 to 0.159.0 (starlette 0.38.6 to 1.9.0, 14 advisories), `python-dotenv`, `uvicorn`, `next` 16.3.4 to 16.4.2 (critical advisory, and the older version could not build against current Google Fonts).
- `app/integrations/razorpay_adapter.py` still has a default test webhook secret; it is not used by the application (only by a unit test).
- `/docs` and `/openapi.json` are public on the backend.

## Credentials

A previous `audit.md` in git history quoted partial fragments of a Groq API key. Treat that key as exposed and rotate it. No secret values were found in the current tree (only obvious placeholders in tests and `.env.example`).
