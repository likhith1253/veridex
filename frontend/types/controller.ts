/**
 * Type definitions for Veridex Controller, Overview, Funnel, Transactions, Exceptions & Copilot.
 * Verified directly against backend FastAPI schemas in app/api/routes/controller.py and app/services/finance_controller.py.
 */

export interface ControllerSummaryKPIs {
  // Authoritative Backend fields (from ControllerKPIs)
  total_records_processed: number;
  total_logical_transactions?: number;
  total_transaction_value_inr?: string;
  deterministic_matches?: number;
  ml_recovered_matches?: number;
  total_matched_records: number;
  automatic_matches?: number;
  manual_reviews?: number;
  unresolved_transactions: number;
  match_rate: number;
  reconciliation_precision?: number | null;
  reconciliation_recall?: number | null;
  f1_score?: number | null;
  exception_rate?: number;
  total_matched_monetary_value_inr?: string;
  unresolved_monetary_exposure_inr: string;
  manual_review_exposure_inr?: string;
  high_risk_exposure_inr?: string;
  delayed_settlement_inr?: string;
  duplicate_amount_inr?: string;
  fee_mismatch_inr?: string;
  processing_throughput_tps?: number | null;
  average_processing_latency_ms?: number | null;
  run_id?: string | null;
  currency?: string;

  // Run provenance — describes the most recent ReconciliationRun in the
  // database, independent of whether this response is scoped to a run_id.
  has_any_run?: boolean;
  latest_run_id?: string | null;
  latest_run_status?: "pending" | "running" | "completed" | "failed" | string | null;
  latest_run_started_at?: string | null;
  latest_run_completed_at?: string | null;

  // Normalized compatibility accessors
  total_records?: number;
  matched_records?: number;
  unmatched_records?: number;
  total_exceptions?: number;
  open_exceptions?: number;
  resolved_exceptions?: number;
  financial_exposure?: string | number;
  expected_cost?: string | number;
  total_financial_volume?: string | number;
  unreconciled_exposure_pct?: number;
}

export interface ReconciliationFunnel {
  // Authoritative Backend fields (from get_reconciliation_funnel)
  incoming_records: number;
  deterministic_matches: number;
  ml_recovered: number;
  manual_reviews: number;
  unresolved: number;
  final_match_rate: number;

  // Normalized compatibility aliases
  total_volume_inr?: string;
  reconciled_volume_inr?: string;
  pending_volume_inr?: string;
  ml_matches?: number;
  unmatched_exceptions?: number;
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
  // Authoritative Backend fields (from list_exceptions and ExceptionDetail)
  exception_id: string;
  run_id?: string | null;
  transaction_id: string;
  category: string;
  status: "open" | "investigating" | "resolved" | "approved" | "rejected" | "escalated" | string;
  confidence: number;
  financial_exposure_inr: number;
  expected_cost_inr: number;
  explanation: string;
  recommended_action: string;
  resolved: boolean;
  created_at?: string | null;

  // Normalized compatibility accessors
  id?: string;
  exception_category?: string;
  financial_exposure?: number | string;
  expected_cost?: number | string;
  assigned_to?: string | null;
  notes?: string | null;
}

export interface ExceptionListResponse {
  page: number;
  page_size: number;
  total_count: number;
  exceptions: ExceptionItem[];
}

export interface ExceptionAgingBucket {
  bucket: string;
  count: number;
  financial_exposure_inr: number;
}

export interface ExceptionAgingResponse {
  total_open_exceptions: number;
  total_aging_exposure_inr: number;
  buckets: ExceptionAgingBucket[];

  // Compatibility accessors
  total_open?: number;
  bucket_0_24h?: number;
  bucket_24_48h?: number;
  bucket_48_72h?: number;
  bucket_72h_plus?: number;
}

export interface CashPositionSummary {
  expected_amount: string;
  expected_gross: string;
  expected_net_settlement: string;
  received_amount: string;
  received_bank_credits: string;
  settlement_variance: string;
  total_deducted_fees?: string;
  total_deducted_taxes?: string;
  deducted_fees?: string;
  deducted_taxes?: string;
  total_refunded_amount?: string;
  pending_amount?: string;
  delayed_amount?: string;
  unreconciled_amount?: string;
  at_risk_amount?: string;
  currency: string;
  as_of?: string | null;
  breakdown_by_source?: Record<string, string | number>;
  breakdown_by_category?: Record<string, string | number>;
}

export interface CopilotQueryRequest {
  question: string;
  run_id?: string | null;
}

export interface CopilotQueryResponse {
  question: string;
  answer?: string;
  direct_answer?: string;
  interpretation?: string;
  recommendation?: string;
  key_metrics?: Record<string, string | number> | null;
  evidence_records?: Array<Record<string, unknown>> | null;
  evidence?: Array<Record<string, unknown>> | null;
  confidence?: number | null;
  sql_facts_used?: string[] | null;
  recommended_actions?: string[] | null;
  source?: string;
  needs_human_review?: boolean;
}

export interface CopilotBriefResponse {
  // Authoritative Backend fields (from CopilotBriefResponse)
  status: string;
  money_at_risk_inr: number;
  reconciliation_match_rate_percent: number;
  highest_risk_exception?: string | null;
  why: string;
  recommended_action: string;
  human_review_required: boolean;
  evidence?: Array<Record<string, unknown>>;
  source_health?: string;
  summary?: Record<string, unknown>;

  // Compatibility fields
  run_id?: string | null;
  headline?: string;
  reconciliation_health_score?: number;
  critical_findings?: string[];
  recommended_actions?: string[];
  generated_at?: string;
  key_metrics?: {
    match_rate_pct?: number;
    financial_exposure_inr?: string;
    open_exceptions_count?: number;
    settlement_variance_inr?: string;
  };
}

export interface BenchmarkMetricsResponse {
  scope?: string;
  benchmark?: {
    num_transactions: number;
    seed: number;
    currency: string;
    dataset_name: string;
  };
  result?: {
    num_transactions?: number;
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
    deterministic_matches?: number;
    ml_recovered_matches?: number;
    unresolved_records?: number;
    throughput_records_per_sec?: number;
    duration_ms?: number;
    duration_seconds?: number;
    scenarios_evaluated?: number;
    match_rate?: number;
    total_exceptions?: number;
  };
  num_transactions?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
  deterministic_matches?: number;
  ml_recovered_matches?: number;
  unresolved_records?: number;
  throughput_records_per_sec?: number;
  duration_ms?: number;
}

export interface BatchIngestResponse {
  batch_id: string;
  run_id: string;
  records_received: number;
  records_normalized: number;
  processing_status: string;
  processing_duration_ms: number;
  reconciliation_status: string;
  auto_matched_count: number;
  ml_recovered_count: number;
  manual_review_count: number;
  unresolved_count: number;

  // Normalized presentation aliases
  total_processed?: number;
  matches_found?: number;
  exceptions_detected?: number;
  duration_seconds?: number;
}
