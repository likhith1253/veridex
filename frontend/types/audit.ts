/**
 * Type definitions for Audit Timeline and Reconciliation Batches.
 */

export interface AuditTimelineItem {
  id?: string;
  run_id?: string | null;
  stage: string;
  event: string;
  actor?: string | null;
  timestamp: string;
  evidence?: Record<string, unknown> | null;
  transaction_id?: string | null;
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
  run_id: string;
  status: string;
  total_processed: number;
  matches_found: number;
  exceptions_detected: number;
  duration_seconds: number;
}
