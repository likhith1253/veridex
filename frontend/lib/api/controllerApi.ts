/**
 * Controller, Overview, Funnel, Transactions, Exceptions, and Copilot API Services.
 * Verified against FastAPI routes in app/api/routes/controller.py.
 */

import { apiClient } from "./client";
import type {
  BenchmarkMetricsResponse,
  CashPositionSummary,
  ControllerSummaryKPIs,
  CopilotBriefResponse,
  CopilotQueryRequest,
  CopilotQueryResponse,
  ExceptionAgingResponse,
  ExceptionItem,
  ExceptionListResponse,
  ReconciliationFunnel,
  TransactionRecord,
} from "@/types/controller";
import type { AuditTimelineItem } from "@/types/audit";

export const controllerApi = {
  /** Retrieve executive financial KPIs and reconciliation metrics */
  getOverview: async (runId?: string): Promise<ControllerSummaryKPIs> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiClient<ControllerSummaryKPIs>(`/api/v1/controller/summary${query}`);
  },

  /** Retrieve multi-stage reconciliation funnel */
  getFunnel: async (runId?: string): Promise<ReconciliationFunnel> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiClient<ReconciliationFunnel>(`/api/v1/controller/funnel${query}`);
  },

  /** Query exceptions with multi-criteria filtering and pagination */
  getExceptions: async (params?: {
    status?: string;
    category?: string;
    min_exposure?: number;
    max_exposure?: number;
    transaction_id?: string;
    run_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<ExceptionListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.category) searchParams.append("category", params.category);
    if (params?.min_exposure !== undefined) searchParams.append("min_exposure", params.min_exposure.toString());
    if (params?.max_exposure !== undefined) searchParams.append("max_exposure", params.max_exposure.toString());
    if (params?.transaction_id) searchParams.append("transaction_id", params.transaction_id);
    if (params?.run_id) searchParams.append("run_id", params.run_id);
    if (params?.page) searchParams.append("page", params.page.toString());
    if (params?.page_size) searchParams.append("page_size", params.page_size.toString());

    const qs = searchParams.toString();
    return apiClient<ExceptionListResponse>(`/api/v1/controller/exceptions${qs ? `?${qs}` : ""}`);
  },

  /** Retrieve full structured evidence and investigation details for a single exception */
  getExceptionDetail: async (id: string): Promise<ExceptionItem> => {
    return apiClient<ExceptionItem>(`/api/v1/controller/exceptions/${encodeURIComponent(id)}`);
  },

  /** Exception aging distribution across standard time buckets */
  getExceptionAging: async (runId?: string): Promise<ExceptionAgingResponse> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiClient<ExceptionAgingResponse>(`/api/v1/controller/exceptions/aging${query}`);
  },

  /** List raw multi-source feed transactions (Gateway, Ledger, Bank) */
  getTransactions: async (params?: {
    run_id?: string;
    limit?: number;
  }): Promise<{ run_id?: string | null; total_count: number; transactions: TransactionRecord[] }> => {
    const searchParams = new URLSearchParams();
    if (params?.run_id) searchParams.append("run_id", params.run_id);
    if (params?.limit) searchParams.append("limit", params.limit.toString());

    const qs = searchParams.toString();
    return apiClient<{ run_id?: string | null; total_count: number; transactions: TransactionRecord[] }>(
      `/api/v1/controller/transactions${qs ? `?${qs}` : ""}`
    );
  },

  /** Retrieve grounded multi-source cash position summary */
  getCashPosition: async (runId?: string): Promise<CashPositionSummary> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiClient<CashPositionSummary>(`/api/v1/controller/cash-position${query}`);
  },

  /** Answer grounded finance-control questions with PostgreSQL facts */
  queryCopilot: async (req: CopilotQueryRequest): Promise<CopilotQueryResponse> => {
    return apiClient<CopilotQueryResponse>("/api/v1/controller/copilot/query", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Render executive daily brief from current controller state */
  getCopilotBrief: async (runId?: string): Promise<CopilotBriefResponse> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiClient<CopilotBriefResponse>(`/api/v1/controller/copilot/brief${query}`);
  },

  /** Retrieve chronological audit timeline */
  getAuditTimeline: async (params?: {
    run_id?: string;
    transaction_id?: string;
  }): Promise<AuditTimelineItem[]> => {
    const searchParams = new URLSearchParams();
    if (params?.run_id) searchParams.append("run_id", params.run_id);
    if (params?.transaction_id) searchParams.append("transaction_id", params.transaction_id);

    const qs = searchParams.toString();
    return apiClient<AuditTimelineItem[]>(`/api/v1/controller/audit/timeline${qs ? `?${qs}` : ""}`);
  },

  /** Run in-memory benchmark evaluation (authoritative measured metrics) */
  getBenchmark: async (numTransactions = 100, seed = 42): Promise<BenchmarkMetricsResponse> => {
    return apiClient<BenchmarkMetricsResponse>(
      `/api/v1/controller/benchmark?num_transactions=${numTransactions}&seed=${seed}`
    );
  },

  /** Apply human decision (approve, reject, escalate, resolve) on exception */
  applyHumanDecision: async (
    exceptionId: string,
    data: { action: string; actor: string; reason: string }
  ): Promise<Record<string, unknown>> => {
    return apiClient<Record<string, unknown>>(`/api/v1/controller/exceptions/${encodeURIComponent(exceptionId)}/decision`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** Ingest batch of records across Gateway, Ledger, Bank feeds */
  ingestBatch: async (data: {
    batch_id?: string;
    gateway_records: Array<Record<string, unknown>>;
    ledger_records: Array<Record<string, unknown>>;
    bank_records: Array<Record<string, unknown>>;
  }): Promise<{
    batch_id?: string;
    status: string;
    total_processed: number;
    matches_found: number;
    exceptions_detected: number;
    duration_seconds: number;
  }> => {
    return apiClient("/api/v1/controller/ingest/batch", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};
