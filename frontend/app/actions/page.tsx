"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { actionsApi } from "@/lib/api/actionsApi";
import { formatINR, cn } from "@/lib/utils/formatters";
import { ActionCard } from "@/components/actions/ActionCard";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ShieldCheck,
  ShieldAlert,
  Clock,
} from "lucide-react";

export default function ActionsPage() {
  const [stateFilter, setStateFilter] = useState<string>("all");

  const {
    data: actions,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["actions-list", stateFilter],
    queryFn: () =>
      actionsApi.getActions({
        state: stateFilter === "all" ? undefined : stateFilter,
      }),
    refetchInterval: 10000,
  });

  const actionsList = actions || [];
  const pendingCount = actionsList.filter(
    (a) => a.state === "PENDING_APPROVAL" || a.state === "RECOMMENDED"
  ).length;

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
            Policy Enforcement
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Policy-Gated Action Controls (HITL)
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            AI recommends adjustments → Authorized Human Controller approves → Bounded Execution → Immutable Audit
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[#8e96a0]">Pending Authorization:</span>
          <span
            className="font-mono text-xs font-bold px-2.5 py-1 rounded-xs"
            style={{
              color: pendingCount > 0 ? "var(--pending-text)" : "var(--matched-text)",
              background: pendingCount > 0 ? "var(--pending-bg)" : "var(--matched-bg)",
              border: `1px solid ${pendingCount > 0 ? "var(--pending-border)" : "var(--matched-border)"}`,
            }}
          >
            {pendingCount} Actions
          </span>
        </div>
      </div>

      {/* Policy Limits Infobar */}
      <div
        className="rounded-sm border p-4 text-xs text-[#eceae6] grid grid-cols-1 sm:grid-cols-3 gap-3"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[#6ecba0]" />
          <span>Max Single Adjustment: <strong className="font-mono text-[#eceae6]">INR 5,000.00</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-[#d4a84e]" />
          <span>Max Write-off Limit: <strong className="font-mono text-[#eceae6]">INR 100.00</strong></span>
        </div>
        <div className="flex items-center gap-2 text-[#c9a96e]">
          <Clock className="h-4 w-4" />
          <span>Human-in-the-Loop Approval Mandatory</span>
        </div>
      </div>

      {/* State Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {["all", "PENDING_APPROVAL", "APPROVED", "EXECUTED", "REJECTED"].map((st) => (
          <button
            key={st}
            onClick={() => setStateFilter(st)}
            className={cn(
              "px-3 py-1.5 rounded-xs text-xs font-medium transition-micro",
              stateFilter === st
                ? "font-semibold text-[#eceae6]"
                : "text-[#8e96a0] hover:text-[#eceae6]"
            )}
            style={stateFilter === st ? {
              background: "var(--surface-3)",
              border: "1px solid var(--border-standard)",
            } : {
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            {st === "all" ? "All States" : st.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Actions Feed */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-40 rounded-sm skeleton" />
          ))}
        </div>
      ) : error ? (
        <ErrorState
          title="Failed to Load Actions"
          message={error instanceof Error ? error.message : "Error connecting to backend"}
          onRetry={refetch}
        />
      ) : actionsList.length === 0 ? (
        <EmptyState
          title="No Actions in Selected State"
          description="Actions recommended during exception investigation will appear here for policy authorization."
        />
      ) : (
        <div className="space-y-4">
          {actionsList.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))}
        </div>
      )}
    </div>
  );
}
