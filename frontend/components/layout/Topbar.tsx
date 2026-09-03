"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { RotateCcw, Brain, Shield } from "lucide-react";
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

  const { data: healthData, isError: healthError } = useQuery({
    queryKey: ["backend-health"],
    queryFn: () => apiClient<{ status: string }>("/health"),
    refetchInterval: 15000,
  });

  const { data: runsData } = useQuery({
    queryKey: ["reconciliation-runs-topbar"],
    queryFn: () => reconciliationApi.getRuns(5),
    staleTime: 30000,
  });

  const latestRunId = runsData?.runs?.[0]?.run_id;

  const getPageContext = (path: string): { title: string; category?: string } => {
    if (path === "/") return { title: "Command Center", category: "Operations" };
    if (path.startsWith("/exceptions/")) return { title: "Investigation Dossier", category: "Forensic Analysis" };
    if (path.startsWith("/exceptions")) return { title: "Exceptions Queue", category: "Operations" };
    if (path.startsWith("/settlements/") && path.includes("tax-audit")) return { title: "Tax Line Auditor", category: "Statutory Parity" };
    if (path.startsWith("/settlements/")) return { title: "Settlement Breakdown", category: "Payout Parity" };
    if (path.startsWith("/settlements")) return { title: "Settlements", category: "Operations" };
    if (path.startsWith("/actions/")) return { title: "Action Review", category: "Human-in-the-Loop" };
    if (path.startsWith("/actions")) return { title: "Action Controls", category: "Operations" };
    if (path.startsWith("/audit")) return { title: "Audit Trail", category: "Operations" };
    if (path.startsWith("/razorpay")) return { title: "Razorpay Gateway", category: "Infrastructure" };
    if (path.startsWith("/benchmark")) return { title: "Engine Validation", category: "Infrastructure" };
    if (path.startsWith("/settings")) return { title: "System Settings", category: "System" };
    if (path.startsWith("/reconciliation")) return { title: "Reconciliation Engine", category: "Operations" };
    return { title: "Control Deck", category: "Operations" };
  };

  const pageContext = getPageContext(pathname);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const isConnected = healthData?.status === "ok" && !healthError;

  return (
    <header
      className="h-14 px-6 flex items-center justify-between gap-4 select-none"
      style={{
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      {/* Context & Page Title */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-baseline gap-2">
          {pageContext.category && (
            <span
              className="text-[10px] uppercase font-semibold tracking-wider hidden sm:inline"
              style={{ color: "var(--text-tertiary)" }}
            >
              {pageContext.category} /
            </span>
          )}
          <h1
            className="text-sm font-semibold tracking-tight text-[#eceae6] truncate"
          >
            {pageContext.title}
          </h1>
        </div>

        {latestRunId && (
          <div
            className="hidden md:flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-[10px] font-mono truncate max-w-[220px]"
            style={{
              color: "var(--text-tertiary)",
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <span>run:</span>
            <span className="text-[#9098a2]">{latestRunId}</span>
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2.5">
        {/* Backend Connectivity Status */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-[11px] font-mono"
          style={{
            color: "var(--text-secondary)",
            background: "var(--surface-2)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              display: "inline-block",
              background: isConnected ? "var(--matched-text)" : "var(--variance-text)",
            }}
          />
          <span className="text-[11px]">{isConnected ? "Engine Active" : "Disconnected"}</span>
        </div>

        {/* Refresh Trigger */}
        <button
          onClick={handleRefresh}
          className="p-1.5 rounded-xs transition-micro text-[#545e6a] hover:text-[#eceae6] hover:bg-[#181c22]"
          title="Refresh operational telemetry"
        >
          <RotateCcw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
        </button>

        {/* Copilot Trigger */}
        {onToggleCopilot && (
          <button
            onClick={onToggleCopilot}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-medium transition-micro text-[#9098a2] hover:text-[#eceae6] hover:bg-[#181c22]"
            style={{
              border: "1px solid var(--border-subtle)",
            }}
          >
            <Brain className="h-3.5 w-3.5 text-[#c9a96e]" />
            <span>Copilot</span>
          </button>
        )}

        {/* Primary Action: Run Batch (Gold Identity) */}
        {onOpenBatchModal && (
          <button
            onClick={onOpenBatchModal}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-semibold transition-micro"
            style={{
              color: "#080a0c",
              background: "var(--accent)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
          >
            <span>Run Batch</span>
          </button>
        )}
      </div>
    </header>
  );
}
