"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { integrationsApi } from "@/lib/api/integrationsApi";
import { formatDateTime } from "@/lib/utils/formatters";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  CreditCard,
  RefreshCw,
  CheckCircle2,
  Radio,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import type { RazorpayUnifiedSyncResponse } from "@/types/integrations";

export default function RazorpayPage() {
  const queryClient = useQueryClient();
  const [syncResult, setSyncResult] = useState<RazorpayUnifiedSyncResponse | null>(null);

  // Status Query
  const {
    data: status,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["razorpay-status"],
    queryFn: () => integrationsApi.getRazorpayStatus(),
    refetchInterval: 15000,
  });

  // Sync Mutation
  const syncMutation = useMutation({
    mutationFn: () => integrationsApi.syncAll({ limit: 50, auto_reconcile: true }),
    onSuccess: (data) => {
      setSyncResult(data);
      queryClient.invalidateQueries();
    },
  });

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            Infrastructure Connector
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Razorpay Gateway Connector &amp; Webhooks
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Direct API synchronization, webhook listener telemetry, and canonical normalization
          </p>
        </div>

        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending || !status?.configured}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xs font-semibold text-xs transition-micro disabled:opacity-50"
          style={{
            color: "#080a0c",
            background: "var(--accent)",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
        >
          {syncMutation.isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Synchronizing Gateway…</span>
            </>
          ) : (
            <>
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Trigger Multi-Entity Sync</span>
            </>
          )}
        </button>
      </div>

      {/* Connectivity & Metadata Telemetry Grid */}
      {isLoading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : error ? (
        <ErrorState
          title="Failed to Connect to Gateway Engine"
          message={error instanceof Error ? error.message : "Error querying connector status"}
          onRetry={refetch}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs">
          {/* API Connectivity */}
          <div
            className="rounded-sm border p-4"
            style={{
              borderColor: status?.api_reachable ? "var(--matched-border)" : "var(--border-subtle)",
              background: "var(--surface-1)",
              borderTop: status?.api_reachable ? "2px solid var(--matched)" : "2px solid var(--variance)",
            }}
          >
            <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] pb-2 font-semibold">
              <span>API Reachability</span>
              <Radio
                className="h-4 w-4"
                style={{ color: status?.api_reachable ? "var(--matched-text)" : "var(--variance-text)" }}
              />
            </div>
            <div
              className="text-lg font-bold font-mono"
              style={{ color: status?.api_reachable ? "var(--matched-text)" : "var(--variance-text)" }}
            >
              {status?.api_reachable ? "REACHABLE (200 OK)" : "UNREACHABLE"}
            </div>
            <div className="text-[11px] text-[#545e6a] mt-1 font-mono">
              Status: {status?.api_reachable ? "Online" : "Unreachable"}
            </div>
          </div>

          {/* Configuration State */}
          <div
            className="rounded-sm border p-4"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
              borderTop: "2px solid var(--accent)",
            }}
          >
            <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] pb-2 font-semibold">
              <span>Key Provisioning</span>
              <ShieldCheck className="h-4 w-4 text-[#c9a96e]" />
            </div>
            <div className="text-lg font-bold text-[#eceae6] font-mono">
              {status?.configured ? "ACTIVE CREDENTIALS" : "UNCONFIGURED"}
            </div>
            <div className="text-[11px] text-[#8e96a0] mt-1 font-mono">
              Prefix: {status?.key_id_prefix || "rzp_test_..."}
            </div>
          </div>

          {/* Webhook Listener Status */}
          <div
            className="rounded-sm border p-4"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] pb-2 font-semibold">
              <span>Webhook Signature</span>
              <CheckCircle2 className="h-4 w-4 text-[#6ecba0]" />
            </div>
            <div className="text-lg font-bold text-[#eceae6] font-mono">
              {status?.webhook_configured ? "HMAC SHA256 ACTIVE" : "UNCONFIGURED"}
            </div>
            <div className="text-[11px] text-[#545e6a] mt-1">
              Cryptographic webhook validation
            </div>
          </div>

          {/* Environment Target */}
          <div
            className="rounded-sm border p-4"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] pb-2 font-semibold">
              <span>Deployment Mode</span>
              <CreditCard className="h-4 w-4 text-[#8e96a0]" />
            </div>
            <div className="text-lg font-bold font-mono text-[#c9a96e] uppercase">
              {status?.mode || "SANDBOX / TEST"}
            </div>
            <div className="text-[11px] text-[#545e6a] mt-1">
              Razorpay standard pipeline
            </div>
          </div>
        </div>
      )}

      {/* Sync Execution Output */}
      {syncResult && (
        <div
          className="rounded-sm border p-6 text-xs text-[#eceae6] space-y-4"
          style={{
            borderColor: "var(--matched-border)",
            background: "var(--surface-1)",
          }}
        >
          <div className="flex items-center justify-between pb-3 border-b" style={{ borderColor: "var(--border-subtle)" }}>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-[#6ecba0]" />
              <span className="font-bold text-sm text-[#eceae6]">
                Multi-Entity Gateway Sync Completed
              </span>
            </div>
            <span className="font-mono text-[11px] text-[#545e6a]">
              Duration: {syncResult.total_duration_ms} ms
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono">
            <div className="p-3 rounded-xs border" style={{ borderColor: "var(--border-subtle)", background: "var(--surface-2)" }}>
              <div className="text-[10px] text-[#8e96a0] uppercase">Payments Ingested</div>
              <div className="text-xl font-bold text-[#eceae6] mt-1">{syncResult.payments?.records_inserted ?? 0}</div>
            </div>
            <div className="p-3 rounded-xs border" style={{ borderColor: "var(--border-subtle)", background: "var(--surface-2)" }}>
              <div className="text-[10px] text-[#8e96a0] uppercase">Settlements Ingested</div>
              <div className="text-xl font-bold text-[#eceae6] mt-1">{syncResult.settlements?.records_inserted ?? 0}</div>
            </div>
            <div className="p-3 rounded-xs border" style={{ borderColor: "var(--border-subtle)", background: "var(--surface-2)" }}>
              <div className="text-[10px] text-[#8e96a0] uppercase">Orders Ingested</div>
              <div className="text-xl font-bold text-[#eceae6] mt-1">{syncResult.orders?.records_inserted ?? 0}</div>
            </div>
            <div className="p-3 rounded-xs border" style={{ borderColor: "var(--border-subtle)", background: "var(--surface-2)" }}>
              <div className="text-[10px] text-[#8e96a0] uppercase">Total Normalized</div>
              <div className="text-xl font-bold text-[#6ecba0] mt-1">
                {syncResult.total_records_normalized ?? 0}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
