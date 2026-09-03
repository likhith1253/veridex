# VERIDEX — v0 Frontend Implementation Specification

**Product:** VERIDEX — AI Financial Control & Reconciliation Engine  
**Tagline:** "Find the discrepancy. Prove the cause. Control the action."  
**Target Stack:** Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query v5, Lucide Icons  
**Target Audience:** v0 Prompting Engineers & Frontend Developers  
**Backend Base URL:** `http://127.0.0.1:8000`  

---

## 1. Core Architecture & Philosophy

The Veridex frontend is an enterprise financial operations terminal. It connects directly to the Veridex FastAPI backend without introducing mock state or client-side financial calculations.

### Tech Stack Choices
- **Framework**: Next.js (App Router, Server Components where applicable, Client Components for interactive data grids)
- **Styling**: Tailwind CSS with CSS variables for dark/light themes
- **Component Primitives**: shadcn/ui (Radix UI primitives)
- **Data Fetching**: TanStack Query (`@tanstack/react-query`) with automatic polling / cache invalidation on mutations
- **Icons**: `lucide-react`
- **Charts**: `recharts` for financial funnels and time-series variance charts

---

## 2. Directory Structure

```
frontend/
├── app/
│   ├── layout.tsx                     # Root layout with Sidebar, Topbar, TanStack Query provider
│   ├── page.tsx                       # Dashboard / Command Center
│   ├── reconciliation/
│   │   └── page.tsx                   # Batch reconciliation runner & feed tables
│   ├── exceptions/
│   │   ├── page.tsx                   # Exception queue & filter grid
│   │   └── [id]/
│   │       └── page.tsx               # Exception investigation & evidence dossier
│   ├── settlements/
│   │   ├── page.tsx                   # Settlement list & 3-way status
│   │   └── [id]/
│   │       ├── page.tsx               # Settlement financial breakdown & bank recon
│   │       └── tax-audit/
│   │           └── page.tsx           # Deterministic tax-line audit view
│   ├── actions/
│   │   ├── page.tsx                   # Policy-gated actions approval center
│   │   └── [id]/
│   │       └── page.tsx               # Action detail & execution status
│   ├── audit/
│   │   └── page.tsx                   # Immutable chronological audit event stream
│   ├── razorpay/
│   │   └── page.tsx                   # Connector status, webhook telemetry & live sync
│   ├── benchmark/
│   │   └── page.tsx                   # Canonical Track 4 evaluation & precision/recall metrics
│   └── settings/
│       └── page.tsx                   # System health, environment info & API key config
│
├── components/
│   ├── ui/                            # shadcn primitives (button, badge, dialog, table, card, etc.)
│   ├── layout/
│   │   ├── AppShell.tsx               # Application responsive layout frame
│   │   ├── Sidebar.tsx                # Left navigation bar with active route indicators
│   │   └── Topbar.tsx                 # System status indicator, search, API key status
│   ├── common/
│   │   ├── MetricCard.tsx             # Financial KPI card with sparklines & deltas
│   │   ├── StatusBadge.tsx            # Semantic colored badge for reconciliation & action states
│   │   ├── ConfidenceBadge.tsx        # High/Medium/Low percentage confidence pill
│   │   ├── LoadingSkeleton.tsx        # Multi-row table & card shimmer loaders
│   │   ├── EmptyState.tsx             # Professional empty state with contextual action
│   │   └── ErrorState.tsx             # API error banner with retry trigger
│   ├── reconciliation/
│   │   ├── FunnelChart.tsx            # Volume conversion funnel (Reconciled vs Unreconciled)
│   │   ├── TransactionTable.tsx       # Paginated high-density feed transactions grid
│   │   └── RunBatchDialog.tsx         # Modal to trigger synthetic or production run
│   ├── exceptions/
│   │   ├── ExceptionTable.tsx         # Filterable exception queue with exposure amounts
│   │   ├── EvidencePanel.tsx          # Side-by-side feed comparison (Gateway vs Bank vs Ledger)
│   │   └── AIInsightCard.tsx          # Grounded AI root-cause explanation card
│   ├── settlements/
│   │   ├── SettlementDecomposition.tsx# Visual equation: Gross - Fee - Tax = Net vs Bank
│   │   └── TaxAuditPanel.tsx          # GST tax-line audit matrix with variance badge
│   ├── actions/
│   │   ├── ActionCard.tsx             # Action card with bounding limits and workflow buttons
│   │   └── ApprovalModal.tsx          # Confirmation modal requiring human actor identity
│   ├── audit/
│   │   └── AuditTimeline.tsx          # Vertical chronological timeline of immutable events
│   └── razorpay/
│       ├── ConnectionCard.tsx         # Live credentials & connectivity ping status
│       └── WebhookTelemetry.tsx       # Real-time webhook event reception log
│
├── lib/
│   ├── api/
│   │   ├── client.ts                  # Axios / Fetch HTTP client with baseURL and auth headers
│   │   ├── controller.ts              # Endpoints for overview, funnel, exceptions, copilot
│   │   ├── reconciliation.ts          # Endpoints for runs, transactions, batch triggers
│   │   ├── settlements.ts             # Endpoints for breakdowns, linkages, tax audits
│   │   ├── actions.ts                 # Endpoints for recommend, approve, reject, execute
│   │   └── integrations.ts            # Endpoints for Razorpay status, sync, webhooks
│   └── utils/
│       ├── formatters.ts              # Currency formatting (INR), dates (UTC/IST), percentages
│       └── constants.ts               # Policy bound constants (INR 5,000 limit, etc.)
│
├── types/
│   ├── controller.ts                  # TypeScript interfaces for overview, exceptions, audit
│   ├── settlements.ts                 # Interfaces for financial breakdown & tax audit
│   └── actions.ts                     # Interfaces for action lifecycle states & execution
│
└── public/                            # Static SVG assets & favicon
```

---

## 3. Environment Variable Strategy

Create `.env.local` for local development:
```bash
# Public API URL consumed by browser client
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000

# Optional Veridex API Key (if configured on backend)
NEXT_PUBLIC_VERIDEX_API_KEY=
```

### Security Directives for v0
- **NEVER** expose backend secrets in `NEXT_PUBLIC_*` variables.
- **NEVER** place `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `GROQ_API_KEY`, or database connection strings in the frontend repository or bundle.
- All LLM queries and Razorpay API calls **must** route strictly through the backend FastAPI endpoints.

---

## 4. Reusable Component Inventory

| Component Name | File Path | Props & Description |
|---|---|---|
| `AppShell` | `components/layout/AppShell.tsx` | Main responsive viewport shell with collapsible sidebar. |
| `Sidebar` | `components/layout/Sidebar.tsx` | Nav links with active route highlight and badge count for open exceptions. |
| `Topbar` | `components/layout/Topbar.tsx` | Global header with live backend connectivity badge and run selector. |
| `MetricCard` | `components/common/MetricCard.tsx` | `title`, `value`, `delta`, `icon`, `statusColor` for executive financial metrics. |
| `StatusBadge` | `components/common/StatusBadge.tsx` | `status: "MATCHED" | "VARIANCE" | "PENDING_APPROVAL" | "EXECUTED" | "REJECTED"`. |
| `ConfidenceBadge` | `components/common/ConfidenceBadge.tsx` | `confidence: number` (0.0 to 1.0) formatted as color-graded percentage pill. |
| `LoadingSkeleton` | `components/common/LoadingSkeleton.tsx` | `variant: "table" | "card" | "dossier"`, animated shimmer placeholder. |
| `EmptyState` | `components/common/EmptyState.tsx` | `title`, `description`, `icon`, optional `actionButton` for clean empty views. |
| `ErrorState` | `components/common/ErrorState.tsx` | `error: Error`, `onRetry: () => void` displayed on failed API responses. |
| `FunnelChart` | `components/reconciliation/FunnelChart.tsx` | Recharts bar/funnel visualizing Reconciled vs Unreconciled volume. |
| `TransactionTable` | `components/reconciliation/TransactionTable.tsx` | Paginated table of raw records across Gateway, Ledger, Bank. |
| `ExceptionTable` | `components/exceptions/ExceptionTable.tsx` | High-density grid of open exceptions with category, exposure, and action links. |
| `EvidencePanel` | `components/exceptions/EvidencePanel.tsx` | Side-by-side 3-way reconciliation comparison of discrepancy items. |
| `AIInsightCard` | `components/exceptions/AIInsightCard.tsx` | Grounded investigation findings with confidence score and evidence citations. |
| `SettlementDecomposition`| `components/settlements/SettlementDecomposition.tsx` | Visual math breakdown: `Gross - Fee - Tax = Net` compared against Bank credit. |
| `TaxAuditPanel` | `components/settlements/TaxAuditPanel.tsx` | GST rate audit table highlighting reported vs expected tax and variance. |
| `ActionCard` | `components/actions/ActionCard.tsx` | Card displaying action type, bounding limit check, actor, and status. |
| `ApprovalModal` | `components/actions/ApprovalModal.tsx` | Confirmation dialog requiring human actor name before approval/execution. |
| `AuditTimeline` | `components/audit/AuditTimeline.tsx` | Vertical timeline component for cryptographic audit event logs. |
| `ConnectionCard` | `components/razorpay/ConnectionCard.tsx` | Live Razorpay status indicator (Connected, Test Mode, Masked Key). |

---

## 5. API Client Implementation Guide

Use a centralized Axios or Fetch client in `lib/api/client.ts`:

```typescript
// lib/api/client.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = process.env.NEXT_PUBLIC_VERIDEX_API_KEY || process.env.NEXT_PUBLIC_SENTINEL_API_KEY || '';

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    ...options.headers,
  };

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API request failed with status ${response.status}`);
  }

  return response.json();
}
```

---

## 6. Frontend Acceptance Criteria

1. **Deterministic Data Binding**: All values displayed on cards and tables must originate from live backend endpoints. No hardcoded mock values in production routes.
2. **Safe Monetary Formatting**: All financial numbers must be formatted with commas and 2 decimal places using safe string utilities (e.g. `INR 1,234.56`).
3. **Approval Security**: The **Execute** button for financial actions must remain disabled until an action has transitioned to the `APPROVED` state. Actor names containing `ai` or `agent` must be validated and rejected.
4. **Honest Razorpay Empty State**: When `/api/v1/integrations/razorpay/sync` reports 0 records, the UI must display: *"0 records found in Razorpay Test Mode. All test credentials verified successfully."*
5. **Tax Audit Visualization**:
   - Status `MATCHED`: Green badge (`#10b981`), variance `INR 0.00`.
   - Status `VARIANCE`: Red badge (`#f43f5e`), explicit variance delta.
   - Status `INSUFFICIENT_EVIDENCE`: Neutral gray/amber badge (`#f59e0b`), explanation displayed.
