/**
 * Reconciliation Runs & Execution API Service.
 * Verified against FastAPI routes in app/api/routes/runs.py & app/api/routes/reconciliation.py.
 */

import { apiClient } from "./client";
import type {
  ReconciliationBatchResult,
  ReconciliationRunItem,
  ReconciliationRunListResponse,
} from "@/types/audit";

export const reconciliationApi = {
  /** List historical reconciliation runs */
  getRuns: async (limit = 20): Promise<ReconciliationRunListResponse> => {
    return apiClient<ReconciliationRunListResponse>(`/runs?limit=${limit}`);
  },

  /** Get execution summary for a reconciliation run */
  getRunSummary: async (runId: string): Promise<Record<string, unknown>> => {
    return apiClient<Record<string, unknown>>(`/runs/${encodeURIComponent(runId)}/summary`);
  },

  /** Execute a full 3-way reconciliation run across multi-source feeds */
  triggerRun: async (data: {
    run_id?: string;
    gateway_records?: Array<Record<string, unknown>>;
    ledger_records?: Array<Record<string, unknown>>;
    bank_records?: Array<Record<string, unknown>>;
  }): Promise<ReconciliationBatchResult> => {
    return apiClient<ReconciliationBatchResult>("/reconciliation/runs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};
