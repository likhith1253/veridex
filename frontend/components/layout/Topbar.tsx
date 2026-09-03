"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import {
  Activity,
  Play,
  RotateCcw,
  Shield,
  Layers,
  Sparkles,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { reconciliationApi } from "@/lib/api/reconciliationApi";

interface TopbarProps {
  onOpenBatchModal?: () => void;
  onToggleCopilot?: () => void;
}

export function Topbar({ onOpenBatchModal, onToggleCopilot }: TopbarProps) {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Backend Health Check Query
  const { data: healthData, isError: healthError } = useQuery({
    queryKey: ["backend-health"],
    queryFn: () => apiClient<{ status: string; app?: string; version?: string }>("/health"),
    refetchInterval: 15000,
  });

  // Recent Runs Query for run context
  const { data: runsData } = useQuery({
    queryKey: ["reconciliation-runs-topbar"],
    queryFn: () => reconciliationApi.getRuns(5),
    staleTime: 30000,
  });

  const latestRunId = runsData?.runs?.[0]?.run_id || "Live Ledger";

  // Map route names
  const getPageTitle = (path: string) => {
    if (path === "/") return "Command Center";
    if (path.startsWith("/reconciliation")) return "Reconciliation Engine";
    if (path.startsWith("/exceptions/")) return "Forensic Investigation Dossier";
    if (path.startsWith("/exceptions")) return "Exception Queue & Workspace";
    if (path.startsWith("/settlements/") && path.includes("tax-audit")) return "GST Tax Line Auditor";
    if (path.startsWith("/settlements/")) return "Settlement Financial Breakdown";
    if (path.startsWith("/settlements")) return "Settlements & Payouts";
    if (path.startsWith("/actions/")) return "Finance Action Review";
    if (path.startsWith("/actions")) return "Policy-Gated Approvals (HITL)";
    if (path.startsWith("/audit")) return "Immutable Audit Trail";
    if (path.startsWith("/razorpay")) return "Razorpay Gateway Connector";
    if (path.startsWith("/benchmark")) return "Benchmark & Accuracy Evaluation";
    if (path.startsWith("/settings")) return "System Diagnostics & Settings";
    return "Operations Workspace";
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const isConnected = healthData?.status === "ok" && !healthError;

  return (
    <header className="h-14 border-b border-[#222634] bg-[#0c0e14] px-6 flex items-center justify-between gap-4 select-none">
      {/* Page Title & Breadcrumb */}
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-bold text-zinc-100 font-mono tracking-tight">
          {getPageTitle(pathname)}
        </h1>
        <span className="text-zinc-600">/</span>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#171a23] border border-zinc-800 text-[11px] font-mono text-zinc-400">
          <Layers className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-300">Run: {latestRunId}</span>
        </div>
      </div>

      {/* Right Operational Controls */}
      <div className="flex items-center gap-3">
        {/* Backend Status Indicator */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#171a23] border border-zinc-800 text-xs font-mono"
          title={isConnected ? "FastAPI Backend Connected (http://127.0.0.1:8000)" : "Backend Disconnected"}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              isConnected ? "bg-emerald-400 animate-pulse" : "bg-rose-500"
            }`}
          />
          <span className="text-zinc-300 text-[11px]">
            {isConnected ? "Engine Ready" : "Backend Offline"}
          </span>
        </div>

        {/* Global Refresh Trigger */}
        <button
          onClick={handleRefresh}
          className="p-1.5 rounded text-zinc-400 hover:text-zinc-100 hover:bg-[#171a23] border border-transparent hover:border-zinc-800 transition-colors"
          title="Refresh live data"
        >
          <RotateCcw className={`h-4 w-4 ${isRefreshing ? "animate-spin text-sky-400" : ""}`} />
        </button>

        {/* Copilot Assistant Trigger */}
        {onToggleCopilot && (
          <button
            onClick={onToggleCopilot}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#171a23] hover:bg-[#1e222e] text-indigo-300 border border-indigo-500/30 transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            <span className="font-mono text-[11px]">AI Copilot</span>
          </button>
        )}

        {/* Run Batch Modal Trigger */}
        {onOpenBatchModal && (
          <button
            onClick={onOpenBatchModal}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-black shadow-sm transition-colors"
          >
            <Play className="h-3 w-3 fill-current" />
            <span>Run Batch (N=50)</span>
          </button>
        )}
      </div>
    </header>
  );
}
