/**
 * Type definitions for Audit Timeline and Reconciliation Batches.
 * Verified against app/api/routes/controller.py, app/services/finance_controller.py and app/api/schemas/controller.py.
 */

export interface AuditTimelineItem {
  event_id: string;
  timestamp?: string | null;
  event_type: string;
  run_id?: string | null;
  transaction_id?: string | null;
  details?: Record<string, unknown> | null;

  // Normalized compatibility accessors
  id?: string;
  stage?: string;
  event?: string;
  actor?: string | null;
  evidence?: Record<string, unknown> | null;
}

export interface ReconciliationRunItem {
  id: string;
  run_id: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  gateway_count: number;
  ledger_count: number;
  bank_count: number;
  match_count: number;
  exception_count: number;
}

export interface ReconciliationRunListResponse {
  total_count: number;
  runs: ReconciliationRunItem[];
}

export interface ReconciliationBatchResult {
  batch_id?: string;
  run_id: string;
  processing_status?: string;
  status?: string;
  records_received?: number;
  records_normalized?: number;
  auto_matched_count?: number;
  ml_recovered_count?: number;
  manual_review_count?: number;
  unresolved_count?: number;
  processing_duration_ms?: number;

  // Presentation accessors
  total_processed?: number;
  matches_found?: number;
  exceptions_detected?: number;
  duration_seconds?: number;
}
