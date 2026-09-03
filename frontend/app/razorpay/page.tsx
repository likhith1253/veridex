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
  AlertTriangle,
  Radio,
  Layers,
  ShieldCheck,
  Play,
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Razorpay Payment Gateway Connector
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Real-time API ingestion, webhook listener telemetry, and multi-entity normalization pipeline.
          </p>
        </div>

        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending || !status?.configured}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-black font-mono font-bold text-xs shadow-md disabled:opacity-50 transition-colors"
        >
          {syncMutation.isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Synchronizing Razorpay...</span>
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 font-mono text-xs">
          {/* API Connectivity */}
          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>API Gateway Reachability</span>
              <Radio className={`h-4 w-4 ${status?.api_reachable ? "text-emerald-400 animate-pulse" : "text-rose-500"}`} />
            </div>
            <div className="text-xl font-bold text-zinc-100 flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${status?.api_reachable ? "bg-emerald-400" : "bg-rose-500"}`} />
              {status?.api_reachable ? "Connected" : "Unreachable"}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">
              Mode: <strong className="text-zinc-300 uppercase">{status?.mode || "Test"}</strong>
            </div>
          </div>

          {/* Credentials Status */}
          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Authentication State</span>
              <ShieldCheck className="h-4 w-4 text-sky-400" />
            </div>
            <div className="text-xl font-bold text-zinc-100">
              {status?.configured ? "Key Configured" : "Missing Key"}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">
              Key Prefix: <span className="text-zinc-300">{status?.key_id_prefix || "rzp_test_***"}</span>
            </div>
          </div>

          {/* Webhook Status */}
          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Webhook Telemetry</span>
              <CheckCircle2 className={`h-4 w-4 ${status?.webhook_configured ? "text-emerald-400" : "text-amber-400"}`} />
            </div>
            <div className="text-xl font-bold text-zinc-100">
              {status?.webhook_configured ? "Listener Active" : "Polling Only"}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">
              Last event: {status?.last_webhook_at ? formatDateTime(status.last_webhook_at) : "No events"}
            </div>
          </div>

          {/* Last Sync */}
          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Last Ingestion Sync</span>
              <RefreshCw className="h-4 w-4 text-zinc-400" />
            </div>
            <div className="text-sm font-bold text-zinc-100 mt-1">
              {status?.last_sync_at ? formatDateTime(status.last_sync_at) : "Pending sync"}
            </div>
            <div className="text-[10px] text-zinc-500 mt-1">
              Idempotency deduping active
            </div>
          </div>
        </div>
      )}

      {/* Sync Execution Output Panel */}
      {syncResult && (
        <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-5 text-xs font-mono space-y-3">
          <div className="flex items-center justify-between text-emerald-400 font-bold border-b border-emerald-800/60 pb-2">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" /> Multi-Entity Synchronization Complete
            </span>
            <span className="text-zinc-400 font-normal">
              Run ID: <strong className="text-zinc-200">{syncResult.run_id}</strong> ({syncResult.total_duration_ms}ms)
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
            <div className="p-3 rounded bg-black/40 border border-emerald-900/40">
              <div className="text-zinc-400 uppercase text-[10px]">Payments Synchronized</div>
              <div className="text-base font-bold text-zinc-100 mt-1">
                {syncResult.payments.records_fetched} fetched | {syncResult.payments.records_inserted} new
              </div>
              <div className="text-[10px] text-zinc-500">{syncResult.payments.records_skipped} duplicates skipped</div>
            </div>

            <div className="p-3 rounded bg-black/40 border border-emerald-900/40">
              <div className="text-zinc-400 uppercase text-[10px]">Orders Synchronized</div>
              <div className="text-base font-bold text-zinc-100 mt-1">
                {syncResult.orders.records_fetched} fetched | {syncResult.orders.records_inserted} new
              </div>
              <div className="text-[10px] text-zinc-500">{syncResult.orders.records_skipped} duplicates skipped</div>
            </div>

            <div className="p-3 rounded bg-black/40 border border-emerald-900/40">
              <div className="text-zinc-400 uppercase text-[10px]">Settlements Synchronized</div>
              <div className="text-base font-bold text-zinc-100 mt-1">
                {syncResult.settlements.records_fetched} fetched | {syncResult.settlements.records_inserted} new
              </div>
              <div className="text-[10px] text-zinc-500">{syncResult.settlements.records_skipped} duplicates skipped</div>
            </div>
          </div>
        </div>
      )}

      {/* Integration Invariants & Documentation Note */}
      <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-5 text-xs text-zinc-400 font-mono space-y-2">
        <h2 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
          Integration Security & Invariant Guarantees
        </h2>
        <ul className="space-y-1 text-[11px] list-disc list-inside text-zinc-400">
          <li>API credentials (<code className="text-zinc-300">RAZORPAY_KEY_ID</code>) are accessed exclusively via secure server-side environment configurations.</li>
          <li>Secrets and webhook tokens are never exposed or rendered in client-side code.</li>
          <li>Ingestion uses SHA-256 idempotency hashing to prevent duplicate record processing on re-syncs.</li>
        </ul>
      </div>
    </div>
  );
}
