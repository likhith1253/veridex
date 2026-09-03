/**
 * Type definitions for Razorpay Integration & Webhook Telemetry.
 */

export interface RazorpayStatusResponse {
  configured: boolean;
  mode: "test" | "live" | string;
  key_id_prefix?: string | null;
  webhook_configured: boolean;
  api_reachable: boolean;
  last_sync_at?: string | null;
  last_webhook_at?: string | null;
  last_error?: string | null;
}

export interface RazorpaySyncRequest {
  limit?: number;
  skip?: number;
  from_timestamp?: number;
  to_timestamp?: number;
  auto_reconcile?: boolean;
  use_fallback_if_unconfigured?: boolean;
}

export interface RazorpaySyncResponse {
  source: string;
  mode: string;
  entity_type: string;
  records_fetched: number;
  records_normalized: number;
  records_inserted: number;
  records_updated: number;
  records_skipped: number;
  records_rejected: number;
  run_id: string;
  duration_ms: number;
  reconciliation_summary?: Record<string, unknown> | null;
  warning?: string | null;
  errors?: string[];
}

export interface RazorpayUnifiedSyncResponse {
  run_id: string;
  source: string;
  mode: string;
  total_records_fetched: number;
  total_records_normalized: number;
  total_records_inserted: number;
  total_records_skipped: number;
  total_records_rejected: number;
  payments: RazorpaySyncResponse;
  orders: RazorpaySyncResponse;
  settlements: RazorpaySyncResponse;
  total_duration_ms: number;
  errors?: string[];
}
