/**
 * Type definitions for Veridex Controller, Overview, Funnel, Transactions, Exceptions & Copilot.
 * Verified directly against backend FastAPI schemas.
 */

export interface ControllerSummaryKPIs {
  total_records: number;
  matched_records: number;
  unmatched_records: number;
  match_rate: number;
  total_exceptions: number;
  open_exceptions: number;
  resolved_exceptions: number;
  financial_exposure: string;
  expected_cost: string;
  total_financial_volume: string;
  unreconciled_exposure_pct: number;
  run_id: string | null;
  currency: string;
}

export interface ReconciliationFunnel {
  total_volume_inr: string;
  reconciled_volume_inr: string;
  pending_volume_inr: string;
  deterministic_matches: number;
  ml_matches: number;
  unmatched_exceptions: number;
}

export interface TransactionRecord {
  id: string;
  run_id?: string | null;
  domain_transaction_id: string;
  source: "gateway" | "ledger" | "bank" | string;
  reference_number?: string | null;
  order_id?: string | null;
  amount: string;
  currency: string;
  timestamp?: string | null;
  fee?: string | null;
  tax?: string | null;
  status: string;
  narration?: string | null;
}

export interface ExceptionItem {
  id: string;
  run_id?: string | null;
  transaction_id: string;
  exception_category: string;
  status: "open" | "investigating" | "resolved" | "approved" | "rejected" | "escalated" | string;
  confidence: number;
  financial_exposure: string;
  expected_cost: string;
  explanation: string;
  recommended_action: string;
  resolved: boolean;
  assigned_to?: string | null;
  notes?: string | null;
  created_at?: string | null;
}

export interface ExceptionListResponse {
  page: number;
  page_size: number;
  total_count: number;
  exceptions: ExceptionItem[];
}

export interface ExceptionAgingResponse {
  total_open: number;
  bucket_0_24h: number;
  bucket_24_48h: number;
  bucket_48_72h: number;
  bucket_72h_plus: number;
  oldest_exception_age_hours?: number | null;
  average_exception_age_hours?: number | null;
}

export interface CashPositionSummary {
  run_id?: string | null;
  expected_gross: string;
  deducted_fees: string;
  deducted_taxes: string;
  expected_net_settlement: string;
  received_bank_credits: string;
  settlement_variance: string;
  unreconciled_exposure: string;
  currency: string;
  as_of?: string | null;
}

export interface CopilotQueryRequest {
  question: string;
  run_id?: string | null;
}

export interface CopilotQueryResponse {
  question: string;
  direct_answer: string;
  key_metrics?: Record<string, string | number> | null;
  evidence_records?: Array<Record<string, unknown>> | null;
  confidence?: number | null;
  sql_facts_used?: string[] | null;
  recommended_actions?: string[] | null;
}

export interface CopilotBriefResponse {
  run_id?: string | null;
  headline: string;
  reconciliation_health_score: number;
  key_metrics: {
    match_rate_pct: number;
    financial_exposure_inr: string;
    open_exceptions_count: number;
    settlement_variance_inr: string;
  };
  critical_findings: string[];
  recommended_actions: string[];
  generated_at: string;
}

export interface BenchmarkMetricsResponse {
  num_transactions: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  deterministic_matches: number;
  ml_recovered_matches: number;
  unresolved_records: number;
  throughput_records_per_sec: number;
  duration_ms: number;
  scenarios_evaluated?: number;
}
