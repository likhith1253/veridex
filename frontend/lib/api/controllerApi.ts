/**
 * Controller, Overview, Funnel, Transactions, Exceptions, and Copilot API Services.
 * Verified against FastAPI routes in app/api/routes/controller.py and app/services/finance_controller.py.
 */

import { apiClient } from "./client";
import type {
  BatchIngestResponse,
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
    const res = await apiClient<ControllerSummaryKPIs>(`/api/v1/controller/summary${query}`);

    // Clean normalization adapter to authoritative and UI fields
    const totalRecords = res.total_records_processed ?? res.total_records ?? 0;
    const matchedRecords = res.total_matched_records ?? res.matched_records ?? 0;
    const unresolved = res.unresolved_transactions ?? res.unmatched_records ?? 0;
    const manual = res.manual_reviews ?? 0;
    const totalExceptions = unresolved + manual;

    // Normalize match rate: if backend gave 27.02 (0-100), convert to decimal 0.2702 for standard percentage formatters
    let matchRateDec = res.match_rate ?? 0;
    if (matchRateDec > 1.0) {
      matchRateDec = matchRateDec / 100.0;
    }

    return {
      ...res,
      total_records_processed: totalRecords,
      total_records: totalRecords,
      total_matched_records: matchedRecords,
      matched_records: matchedRecords,
      unresolved_transactions: unresolved,
      unmatched_records: unresolved,
      total_exceptions: res.total_exceptions ?? totalExceptions,
      open_exceptions: res.open_exceptions ?? unresolved,
      resolved_exceptions: res.resolved_exceptions ?? 0,
      match_rate: matchRateDec,
      financial_exposure: res.unresolved_monetary_exposure_inr ?? res.financial_exposure ?? "0.00",
      unresolved_monetary_exposure_inr: res.unresolved_monetary_exposure_inr ?? "0.00",
      total_financial_volume: res.total_transaction_value_inr ?? res.total_financial_volume ?? "0.00",
      total_transaction_value_inr: res.total_transaction_value_inr ?? "0.00",
      expected_cost: res.manual_review_exposure_inr ?? res.expected_cost ?? "0.00",
      unreconciled_exposure_pct: totalRecords > 0 ? (unresolved / totalRecords) : 0,
      currency: res.currency || "INR",
    };
  },

  /** Retrieve multi-stage reconciliation funnel */
  getFunnel: async (runId?: string): Promise<ReconciliationFunnel> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    const res = await apiClient<ReconciliationFunnel>(`/api/v1/controller/funnel${query}`);

    let matchRateDec = res.final_match_rate ?? 0;
    if (matchRateDec > 1.0) {
      matchRateDec = matchRateDec / 100.0;
    }

    return {
      ...res,
      incoming_records: res.incoming_records ?? 0,
      deterministic_matches: res.deterministic_matches ?? 0,
      ml_recovered: res.ml_recovered ?? 0,
      manual_reviews: res.manual_reviews ?? 0,
      unresolved: res.unresolved ?? 0,
      final_match_rate: matchRateDec,
      // Compatibility aliases
      ml_matches: res.ml_recovered ?? 0,
      unmatched_exceptions: res.unresolved ?? 0,
    };
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
    const res = await apiClient<ExceptionListResponse>(`/api/v1/controller/exceptions${qs ? `?${qs}` : ""}`);

    // Clean normalization adapter for exception list items
    const rawExceptions = res.exceptions || [];
    const normalizedExceptions: ExceptionItem[] = rawExceptions.map((ex) => {
      const id = ex.exception_id || ex.id || "";
      const cat = ex.category || ex.exception_category || "unexplained";
      const expInr = ex.financial_exposure_inr !== undefined ? ex.financial_exposure_inr : (Number(ex.financial_exposure) || 0);
      const costInr = ex.expected_cost_inr !== undefined ? ex.expected_cost_inr : (Number(ex.expected_cost) || 0);

      return {
        ...ex,
        exception_id: id,
        id: id,
        category: cat,
        exception_category: cat,
        financial_exposure_inr: expInr,
        financial_exposure: expInr,
        expected_cost_inr: costInr,
        expected_cost: costInr,
      };
    });

    return {
      page: res.page ?? 1,
      page_size: res.page_size ?? normalizedExceptions.length,
      total_count: res.total_count ?? normalizedExceptions.length,
      exceptions: normalizedExceptions,
    };
  },

  /** Retrieve full structured evidence and investigation details for a single exception */
  getExceptionDetail: async (id: string): Promise<ExceptionItem> => {
    const ex = await apiClient<ExceptionItem>(`/api/v1/controller/exceptions/${encodeURIComponent(id)}`);
    const excId = ex.exception_id || ex.id || id;
    const cat = ex.category || ex.exception_category || "unexplained";
    const expInr = ex.financial_exposure_inr !== undefined ? ex.financial_exposure_inr : (Number(ex.financial_exposure) || 0);
    const costInr = ex.expected_cost_inr !== undefined ? ex.expected_cost_inr : (Number(ex.expected_cost) || 0);

    return {
      ...ex,
      exception_id: excId,
      id: excId,
      category: cat,
      exception_category: cat,
      financial_exposure_inr: expInr,
      financial_exposure: expInr,
      expected_cost_inr: costInr,
      expected_cost: costInr,
    };
  },

  /** Exception aging distribution across standard time buckets */
  getExceptionAging: async (runId?: string): Promise<ExceptionAgingResponse> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    const res = await apiClient<ExceptionAgingResponse>(`/api/v1/controller/exceptions/aging${query}`);
    const buckets = res.buckets || [];

    // Map buckets into convenient accessors
    const findCount = (label: string) => {
      const b = buckets.find((item) => item.bucket === label);
      return b ? b.count : 0;
    };

    return {
      ...res,
      total_open_exceptions: res.total_open_exceptions ?? 0,
      total_aging_exposure_inr: res.total_aging_exposure_inr ?? 0,
      buckets: buckets,
      total_open: res.total_open_exceptions ?? 0,
      bucket_0_24h: findCount("<1 day"),
      bucket_24_48h: findCount("1-3 days"),
      bucket_48_72h: findCount("3-7 days"),
      bucket_72h_plus: findCount("7-30 days") + findCount("30+ days"),
    };
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
    const res = await apiClient<{ run_id?: string | null; total_count: number; transactions: TransactionRecord[] }>(
      `/api/v1/controller/transactions${qs ? `?${qs}` : ""}`
    );
    return {
      run_id: res.run_id ?? null,
      total_count: res.total_count ?? (res.transactions ? res.transactions.length : 0),
      transactions: res.transactions || [],
    };
  },

  /** Retrieve grounded multi-source cash position summary */
  getCashPosition: async (runId?: string): Promise<CashPositionSummary> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiClient<CashPositionSummary>(`/api/v1/controller/cash-position${query}`);
  },

  /** Answer grounded finance-control questions with PostgreSQL facts */
  queryCopilot: async (req: CopilotQueryRequest): Promise<CopilotQueryResponse> => {
    const raw = await apiClient<CopilotQueryResponse>("/api/v1/controller/copilot/query", {
      method: "POST",
      body: JSON.stringify(req),
    });

    // Backend sends fact_summary as { key: value } object; normalize to sql_facts_used string[]
    const factSummary = (raw as any).fact_summary;
    let sqlFacts: string[] = raw.sql_facts_used || [];
    if (!sqlFacts.length && factSummary && typeof factSummary === "object") {
      sqlFacts = Object.entries(factSummary).map(
        ([k, v]) => `${k.replace(/_/g, " ")}: ${v}`
      );
    }

    return {
      ...raw,
      answer: raw.answer || raw.direct_answer,
      direct_answer: raw.direct_answer || raw.answer,
      interpretation: raw.interpretation,
      recommendation: raw.recommendation,
      sql_facts_used: sqlFacts,
    };
  },

  /** Render executive daily brief from current controller state */
  getCopilotBrief: async (runId?: string): Promise<CopilotBriefResponse> => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    const res = await apiClient<CopilotBriefResponse>(`/api/v1/controller/copilot/brief${query}`);

    return {
      ...res,
      headline: res.why || "Daily Executive Brief",
      reconciliation_health_score: Math.round(res.reconciliation_match_rate_percent || 0),
      critical_findings: res.highest_risk_exception ? [res.highest_risk_exception] : [],
      recommended_actions: res.recommended_action ? [res.recommended_action] : [],
    };
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
    const raw = await apiClient<AuditTimelineItem[] | { value: AuditTimelineItem[] }>(
      `/api/v1/controller/audit/timeline${qs ? `?${qs}` : ""}`
    );

    // Backend returns either a direct array or { value: [...] } envelope
    const rawEvents: AuditTimelineItem[] = Array.isArray(raw)
      ? raw
      : (raw as any)?.value ?? [];

    return rawEvents.map((ev) => ({
      ...ev,
      id: ev.event_id || ev.id,
      stage: ev.event_type || ev.stage || "AUDIT_EVENT",
      event: (ev.details && typeof ev.details === "object" && "explanation" in ev.details ? String((ev.details as any).explanation) : null) || ev.event || ev.event_type,
      evidence: ev.details || ev.evidence || {},
    }));
  },

  /** Run in-memory benchmark evaluation (authoritative measured metrics) */
  getBenchmark: async (numTransactions = 100, seed = 42): Promise<BenchmarkMetricsResponse> => {
    const res = await apiClient<BenchmarkMetricsResponse>(
      `/api/v1/controller/benchmark?num_transactions=${numTransactions}&seed=${seed}`
    );
    // Backend response shape: { scope, benchmark, result: { overall, dataset, ... } }
    const overall = (res as any).result?.overall ?? {};
    const dataset = (res as any).result?.dataset ?? {};
    const benchmarkMeta = (res as any).benchmark ?? {};

    // Compute throughput from dataset: total_transactions / execution_time_seconds
    const execSec = dataset.execution_time_seconds ?? 0;
    const totalRecords = dataset.total_transactions ?? numTransactions * 3;
    const throughput = execSec > 0 ? Math.round(totalRecords / execSec) : 0;
    const durationMs = execSec ? execSec * 1000 : 0;

    // Deterministic / ML breakdown from decision_distribution
    const decisions = (res as any).result?.decision_distribution ?? {};
    const autoMatch = decisions?.auto_match?.count ?? overall.true_positives ?? 0;
    const mlRecovered = decisions?.propose_match?.count ?? decisions?.ml_recovered?.count ?? 0;
    const unresolved = decisions?.unresolved?.count ?? overall.false_negatives ?? 0;

    return {
      ...res,
      num_transactions: benchmarkMeta.num_transactions ?? numTransactions,
      accuracy: overall.accuracy ?? 0,
      precision: overall.precision ?? 0,
      recall: overall.recall ?? 0,
      f1_score: overall.f1_score ?? 0,
      deterministic_matches: autoMatch,
      ml_recovered_matches: mlRecovered,
      unresolved_records: unresolved,
      throughput_records_per_sec: throughput,
      duration_ms: durationMs,
    };
  },

  /** Apply human decision (approve, reject, escalate, resolve) on exception */
  applyHumanDecision: async (
    exceptionId: string,
    data: { action: string; actor: string; reason?: string }
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
  }): Promise<BatchIngestResponse> => {
    const res = await apiClient<BatchIngestResponse>("/api/v1/controller/ingest/batch", {
      method: "POST",
      body: JSON.stringify(data),
    });

    const durationSeconds = res.processing_duration_ms ? (res.processing_duration_ms / 1000) : 0;
    return {
      ...res,
      total_processed: res.records_received ?? res.records_normalized ?? 0,
      matches_found: (res.auto_matched_count ?? 0) + (res.ml_recovered_count ?? 0),
      exceptions_detected: res.unresolved_count ?? res.manual_review_count ?? 0,
      duration_seconds: durationSeconds,
    };
  },
};
