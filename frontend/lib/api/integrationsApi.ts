/**
 * Razorpay Connector & Synchronization API Service.
 * Verified against FastAPI routes in app/api/routes/integrations.py.
 */

import { apiClient } from "./client";
import type {
  RazorpayStatusResponse,
  RazorpaySyncRequest,
  RazorpaySyncResponse,
  RazorpayUnifiedSyncResponse,
} from "@/types/integrations";

export const integrationsApi = {
  /** Query safe connectivity status and metadata */
  getRazorpayStatus: async (): Promise<RazorpayStatusResponse> => {
    return apiClient<RazorpayStatusResponse>("/api/v1/integrations/razorpay/status");
  },

  /** Trigger multi-entity synchronization across payments, orders, and settlements */
  syncAll: async (req: RazorpaySyncRequest = { limit: 50 }): Promise<RazorpayUnifiedSyncResponse> => {
    return apiClient<RazorpayUnifiedSyncResponse>("/api/v1/integrations/razorpay/sync", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Synchronize payments */
  syncPayments: async (req: RazorpaySyncRequest = { limit: 50 }): Promise<RazorpaySyncResponse> => {
    return apiClient<RazorpaySyncResponse>("/api/v1/integrations/razorpay/sync/payments", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Synchronize orders */
  syncOrders: async (req: RazorpaySyncRequest = { limit: 50 }): Promise<RazorpaySyncResponse> => {
    return apiClient<RazorpaySyncResponse>("/api/v1/integrations/razorpay/sync/orders", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Synchronize settlements */
  syncSettlements: async (req: RazorpaySyncRequest = { limit: 50 }): Promise<RazorpaySyncResponse> => {
    return apiClient<RazorpaySyncResponse>("/api/v1/integrations/razorpay/sync/settlements", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },
};
