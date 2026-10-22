<div align="center">

# 🛡️ VERIDEX
### AI Financial Control & Reconciliation Engine

*"Find the discrepancy. Prove the cause. Control the action."*

[![Live App](https://img.shields.io/badge/🚀_Live_App-veridex--three.vercel.app-c9a96e?style=for-the-badge)](https://veridex-three.vercel.app)
[![API](https://img.shields.io/badge/⚙️_API-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://veridex-378i.onrender.com/health)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?style=flat-square&logo=typescript&logoColor=white)
[![CI](https://github.com/likhith1253/veridex/actions/workflows/ci.yml/badge.svg)](https://github.com/likhith1253/veridex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

</div>

---

Every payments company reconciles three fragmented records of the same
transaction — what the **payment gateway** processed, what the **internal
ledger** recorded, and what the **bank statement** actually confirms. They
don't always agree. VERIDEX matches all three automatically, finds exactly
which leg broke when they disagree, explains *why* with real evidence — not
a guess — and never moves money without a human saying yes.

## 🔗 Quick links

| | |
|---|---|
| 🚀 **Live app** | [veridex-three.vercel.app](https://veridex-three.vercel.app) |
| ⚙️ **API** | [veridex-378i.onrender.com](https://veridex-378i.onrender.com/health) &middot; [docs](https://veridex-378i.onrender.com/docs) |
| 🏗️ **Architecture** | [ARCHITECTURE.md](ARCHITECTURE.md) &middot; [diagram](docs/architecture-diagram.svg) |
| 🔍 **Real bugs found & fixed while deploying** | [docs/ENGINEERING_JOURNAL.md](docs/ENGINEERING_JOURNAL.md) |

> **A note on the live links:** both the frontend and backend run on free
> tiers. Render's free tier sleeps after inactivity and can take 30-60s to
> wake up on the first request — that's hosting, not the app. Give it a
> moment on first load.

## 📸 Screenshots

<table>
<tr>
<td width="50%"><img src="docs/screenshots/landing.png" alt="Landing page" /><br/><sub align="center">Landing page</sub></td>
<td width="50%"><img src="docs/screenshots/control-center.png" alt="Control Center" /><br/><sub>Control Center</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/reconciliation.png" alt="Reconciliation dashboard" /><br/><sub>Reconciliation — live match rate, throughput, exception breakdown</sub></td>
<td width="50%"><img src="docs/screenshots/exceptions.png" alt="Exception queue" /><br/><sub>Exception queue with real root-cause categories</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/actions.png" alt="Review Actions" /><br/><sub>Human-in-the-loop action approval workflow</sub></td>
<td width="50%"><img src="docs/screenshots/settlements.png" alt="Settlements" /><br/><sub>Settlement intelligence — expected vs. actual bank credit</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/benchmark.png" alt="Benchmark" /><br/><sub>Live run metrics vs. the fixed evaluation harness</sub></td>
<td width="50%"><img src="docs/screenshots/audit.png" alt="Audit trail" /><br/><sub>Immutable audit trail of every decision</sub></td>
</tr>
</table>

## ✨ What it does

1. 🔄 **Reconciles** Gateway, Ledger, and Bank records three ways: deterministic exact-match rules first, then an ML arbitration model for the harder ambiguous cases.
2. 🏷️ **Classifies every exception** by real root cause (missing source, timing lag, fee mismatch, tax mismatch, duplicate, amount mismatch) instead of a generic "unresolved" bucket.
3. 🕵️ **Investigates automatically** — a per-exception LLM-assisted investigation reads the actual linked transaction evidence and writes a grounded root-cause explanation, visualized as a real Gateway → Ledger → Bank evidence pipeline showing exactly which leg broke.
4. 💰 **Tracks settlement intelligence** — matches what the gateway says it settled against what actually landed in the bank account, accounting for fees and taxes.
5. 🔐 **Keeps humans in control** — every corrective action (post an adjustment, write off a discrepancy, flag for investigation) goes through a policy-gated approval workflow with ceilings enforced server-side, and an append-only audit trail.
6. 💬 **Answers questions directly** — a Copilot assistant that computes real answers from the live database first and only uses an LLM to phrase the response, plus a separate "how does this product work" knowledge mode.
7. 📊 **Evaluates itself** — a seed-based benchmark harness scores the reconciliation engine against simulator ground truth, kept separate from live usage numbers and labeled as such in the UI. Real results, including the weak spots, are in [Evaluation](#-evaluation) below.

## 🧠 Why this is built the way it is

- **Single source of truth.** Every number, on every page, is computed once
  (`FinanceController.get_summary_kpis()`) and read everywhere else — never
  recomputed independently per page. See the journal for what happens
  without this discipline.
- **Deterministic → ML → LLM, in that order.** The expensive, harder-to-verify
  step (LLM investigation) only runs for exceptions that survive the two
  cheaper, fully-explainable stages first.
- **Humans authorize, machines never execute.** Policy ceilings (max adjustment,
  max write-off, bounded transaction size) are enforced server-side in the
  finance-action service (`app/services/finance_action_service.py`), not just
  displayed as a UI suggestion.
- **Tested against real infrastructure, not just localhost.** Every bug in
  [ENGINEERING_JOURNAL.md](docs/ENGINEERING_JOURNAL.md) was found by
  exercising the actual deployed Neon + Render + Vercel stack — cold starts,
  connection poolers, function timeouts included — because that's the
  environment real users and evaluators actually touch.

## 🏗️ Architecture

- Deterministic matching
- ML candidate scoring
- Selective LLM judgment (Groq)
- Investigation service with real evidence-graph construction
- Root-cause classification
- Financial risk / expected-cost calculation
- Human-in-the-loop finance actions with policy ceilings
- Immutable audit trail
- Canonical evaluation harness against a fixed-seed ground truth (reproducible, not a held-out set)

<p align="center"><img src="docs/architecture-diagram.svg" alt="Architecture diagram" width="900"/></p>

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full detailed system design.

**Tech stack:**

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind, React Query, Framer Motion |
| Backend | FastAPI (async), SQLAlchemy, Alembic |
| Database | PostgreSQL ([Neon](https://neon.tech)) |
| Matching / ML | scikit-learn, XGBoost |
| Investigation / reasoning | LangGraph, Groq LLM |
| Vector retrieval | Qdrant |
| Hosting | [Vercel](https://vercel.com) (frontend) + [Render](https://render.com) (backend) |

## 🚀 Running locally

Requires Python 3.11+, Node 20+, and PostgreSQL 14+.

**Backend:**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # set DATABASE_URL at minimum
alembic upgrade head
uvicorn app.api.main:app --reload --port 8000
```
Without `GROQ_API_KEY` the investigation step uses a deterministic fake LLM client, so everything runs offline. Set `RAZORPAY_WEBHOOK_SECRET` to receive webhooks (with no secret configured, all webhook deliveries are rejected). Set `SENTINEL_API_KEY` to require an `X-API-Key` header on all non-public routes; with `ENVIRONMENT=production` and no key set, protected routes return 503 instead of being open.

**Frontend:**
```bash
cd frontend
cp .env.example .env.local    # VERIDEX_BACKEND_URL, optional VERIDEX_API_KEY
npm ci
npm run dev
```

## ☁️ Deploying it yourself

VERIDEX deploys as three independent pieces — a Postgres database, a FastAPI backend, and a Next.js frontend — and is designed to work on each platform's free tier.

<details>
<summary><b>1. Neon (PostgreSQL)</b></summary>

1. Create a project at [neon.tech](https://neon.tech), grab the connection string.
2. Convert its scheme to the async driver and run migrations once:
   ```bash
   DATABASE_URL="postgresql+asyncpg://<user>:<password>@<host>/<db>?sslmode=require" alembic upgrade head
   ```
3. That's it — the backend also runs `alembic upgrade head` automatically on every boot, so schema drift can't silently ship to production again (see [ENGINEERING_JOURNAL.md](docs/ENGINEERING_JOURNAL.md) for why that matters).

> If you're behind a network that blocks outbound port 5432 (some campus/corporate networks do), run the migration from a different network, or let the backend's own startup hook handle it on first deploy.
</details>

<details>
<summary><b>2. Render (backend)</b></summary>

1. New Web Service → connect this repo → root directory blank (repo root).
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
4. Environment variables: `DATABASE_URL` (from Neon), `ENVIRONMENT=production`, `PYTHON_VERSION=3.11.9`, `GROQ_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_MODE=test`, and `SENTINEL_API_KEY` (required when `ENVIRONMENT=production`; use the same value as `VERIDEX_API_KEY` on Vercel).
</details>

<details>
<summary><b>3. Vercel (frontend)</b></summary>

1. Import this repo → set **Root Directory** to `frontend`.
2. Environment variables: `VERIDEX_BACKEND_URL` = your Render URL (no trailing slash). Optionally `VERIDEX_API_KEY` if you set `SENTINEL_API_KEY` on Render.
3. Set `ALLOWED_ORIGINS` on Render only if something other than the Vercel proxy calls the API directly from a browser.
4. **Do not** set `NEXT_PUBLIC_API_BASE_URL` — the frontend proxies through a server-side route (`/api/proxy`) specifically so the backend URL and API key never reach the browser bundle.
</details>

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel
python -m pytest tests/ -q
```
482 tests across 54 modules, run on every push via GitHub Actions (badge above, with a PostgreSQL 16 service container). The suite never runs against the configured database: it derives and creates a separate `*_test` database (or uses `TEST_DATABASE_URL`). `tests/test_security_audit_overhaul.py` covers webhook signature verification, API-key enforcement, CORS and input bounds. The frontend job runs `tsc --noEmit` and `next build`.

## 📏 Evaluation

The benchmark harness is `eval/` (simulator-generated three-way feeds with injected corruptions, scored against known ground truth). Run it with:

```bash
python -m eval.run_evaluation --num-transactions 500 --seed 42
```

Result of that exact command (500 logical transactions = 1,500 feed records, seed 42), reproduced locally when this README was written:

| Metric | Value |
|---|---|
| Precision | 85.32% |
| Recall | 95.56% |
| F1 | 90.15% |
| Matches via exact-UTR rule / via ML scoring | 63 / 441 |

Per-scenario highlights from the same run: `fee_mismatch`, `wrong_reference` and `unexplained` scenarios 100% F1; `normal` 97.5%; `delayed_settlement` 50.0%; **`duplicate` 0.0%**. Duplicates are not handled by the matcher itself (there is a separate duplicate audit endpoint, `/api/v1/controller/duplicates/audit`).

Additional committed artifacts from earlier red-team scripts (`eval/independent_redteam_eval.py`, results in `eval/independent_redteam_results.json`):

- Canonical 100-scenario run: 54/54 clean matches passed, 46/46 injected exceptions detected, financial parity check passed.
- **Fresh-data generalization (75 scenarios, different data): 40/40 clean matches passed but 0/35 exceptions detected (0% recall).** The canonical result does not generalize to unseen exception data; treat it as a regression benchmark, not evidence of general accuracy.
- Copilot Q&A check: 10/20 prompts factually correct and aligned, 20/20 grounded in retrieved evidence.
- Throughput measured end to end: about 104-160 feed records/s (30 to 3,000 records) on the author's machine.

`eval/canonical_ground_truth.json` is the simulator's fixed-seed output and is public, so it is a reproducible regression benchmark, not a held-out test set. Live usage numbers are tracked separately from these.

## 🔒 Security notes

- All routes except `/`, `/health` and the HMAC-verified `POST /api/v1/webhooks/razorpay` require the shared API key when one is configured; production fails closed as described above.
- Webhooks are verified with HMAC-SHA256 over the raw body using only `RAZORPAY_WEBHOOK_SECRET`, deduplicated by event id, and rejected outright when no secret is configured.
- The browser only talks to the Next.js `/api/proxy` route, which attaches the API key server-side. The public demo UI can therefore reach the backend with the key; that is a demo convenience, not user-level authentication.
- See [docs/SECURITY.md](docs/SECURITY.md) for the audit findings and what remains open.

## ⚠️ Limitations

- Single-tenant: one shared API key, no user accounts or per-user authorization. The `actor` on an approval is a client-supplied string, not an authenticated identity.
- Evaluation data is synthetic. Duplicate transactions are not matched, delayed settlements are weak (50% F1), and unseen exception types were not detected in the committed red-team run (see Evaluation).
- No rate limiting in the app; rely on the hosting platform.
- Free-tier hosting cold starts take 30-60 s on first request.
- `langgraph` 0.2.x and `langchain-core` have known advisories that need a major upgrade not verified here (see docs/SECURITY.md).
- ESLint reports 29 errors (mostly `no-explicit-any` and React hooks purity rules); `tsc` and `next build` pass.

---

<div align="center">

Built for the Razorpay AI Buildathon — Track 4

</div>
