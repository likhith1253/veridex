"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { RotateCcw, Brain } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { reconciliationApi } from "@/lib/api/reconciliationApi";
import { TechnicalReference } from "@/components/common/TechnicalReference";

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
    if (path === "/" || path === "/app") return { title: "Command Center", category: "Operations" };
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
    <header className="h-14 px-6 flex items-center justify-between gap-4 select-none bg-[#FFFFFF] border-b border-[#D7D3CA]">
      {/* Context & Page Title */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-baseline gap-2">
          {pageContext.category && (
            <span className="text-[10px] uppercase font-semibold tracking-wider text-[#6F747A] hidden sm:inline">
              {pageContext.category} /
            </span>
          )}
          <h1 className="text-sm font-semibold tracking-tight text-[#17191C] truncate">
            {pageContext.title}
          </h1>
        </div>

        {latestRunId && (
          <div className="hidden md:flex items-center">
            <TechnicalReference id={latestRunId} label="run" maxVisible={18} />
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2.5">
        {/* Backend Connectivity Status */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-[11px] font-mono text-[#555B61] bg-[#F1EFE9] border border-[#D7D3CA]">
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              display: "inline-block",
              background: isConnected ? "#1E7B4D" : "#B83A3A",
            }}
          />
          <span className="font-medium text-[#17191C]">{isConnected ? "Engine Active" : "Disconnected"}</span>
        </div>

        {/* Refresh Trigger */}
        <button
          onClick={handleRefresh}
          className="p-1.5 rounded-xs transition-micro text-[#555B61] hover:text-[#17191C] hover:bg-[#F1EFE9] border border-transparent hover:border-[#D7D3CA]"
          title="Refresh operational telemetry"
        >
          <RotateCcw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
        </button>

        {/* Copilot Trigger */}
        {onToggleCopilot && (
          <button
            onClick={onToggleCopilot}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-medium transition-micro text-[#17191C] bg-[#FFFFFF] border border-[#D7D3CA] hover:bg-[#F1EFE9]"
          >
            <Brain className="h-3.5 w-3.5 text-[#C9A96E]" />
            <span>Copilot</span>
          </button>
        )}

        {/* Primary Action: Run Batch (Gold Identity) */}
        {onOpenBatchModal && (
          <button
            onClick={onOpenBatchModal}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-semibold transition-micro text-[#171A1E] bg-[#C9A96E] hover:bg-[#D8BC8A] shadow-xs"
          >
            <span>Run Batch</span>
          </button>
        )}
      </div>
    </header>
  );
}
