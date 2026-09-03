/**
 * Policy-Gated Finance Actions (Human-in-the-Loop) API Service.
 * Verified against FastAPI routes in app/api/routes/finance_actions.py.
 */

import { apiClient } from "./client";
import type {
  ActionDecisionRequest,
  ActionExecuteRequest,
  ActionRecommendRequest,
  FinanceAction,
} from "@/types/actions";

export const actionsApi = {
  /** List policy-gated finance actions */
  getActions: async (params?: {
    state?: string;
    entity_type?: string;
    entity_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<FinanceAction[]> => {
    const searchParams = new URLSearchParams();
    if (params?.state) searchParams.append("state", params.state);
    if (params?.entity_type) searchParams.append("entity_type", params.entity_type);
    if (params?.entity_id) searchParams.append("entity_id", params.entity_id);
    if (params?.limit) searchParams.append("limit", params.limit.toString());
    if (params?.offset) searchParams.append("offset", params.offset.toString());

    const qs = searchParams.toString();
    return apiClient<FinanceAction[]>(`/api/v1/actions${qs ? `?${qs}` : ""}`);
  },

  /** Get single finance action by ID */
  getActionById: async (id: string): Promise<FinanceAction> => {
    return apiClient<FinanceAction>(`/api/v1/actions/${encodeURIComponent(id)}`);
  },

  /** Recommend a bounded financial action */
  recommendAction: async (req: ActionRecommendRequest): Promise<FinanceAction> => {
    return apiClient<FinanceAction>("/api/v1/actions/recommend", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Explicit human approval for a pending action */
  approveAction: async (id: string, req: ActionDecisionRequest): Promise<FinanceAction> => {
    return apiClient<FinanceAction>(`/api/v1/actions/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Explicit human rejection for a pending action */
  rejectAction: async (id: string, req: ActionDecisionRequest): Promise<FinanceAction> => {
    return apiClient<FinanceAction>(`/api/v1/actions/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Bounded execution of an approved action */
  executeAction: async (id: string, req: ActionExecuteRequest): Promise<FinanceAction> => {
    return apiClient<FinanceAction>(`/api/v1/actions/${encodeURIComponent(id)}/execute`, {
      method: "POST",
      body: JSON.stringify(req),
    });
  },
};
