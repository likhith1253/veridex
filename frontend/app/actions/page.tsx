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
  Filter,
  CheckCircle2,
  Clock,
  Play,
  ArrowRight,
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Policy-Gated Action Controls (HITL)
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            AI recommends ledger adjustments and write-offs $\rightarrow$ Authorized Human Controller approves $\rightarrow$ Bounded Execution $\rightarrow$ Immutable Audit.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-zinc-400">Pending Review:</span>
          <span className="font-mono text-sm font-bold text-amber-400 px-2.5 py-1 rounded bg-amber-950/60 border border-amber-800/60">
            {pendingCount} Actions
          </span>
        </div>
      </div>

      {/* Policy Limits Infobar */}
      <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4 text-xs font-mono text-zinc-300 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Max Single Adjustment: <strong>INR 5,000.00</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-amber-400" />
          <span>Max Write-off Limit: <strong>INR 100.00</strong></span>
        </div>
        <div className="flex items-center gap-2 text-sky-400">
          <Clock className="h-4 w-4" />
          <span>Human-in-the-Loop Approval Required</span>
        </div>
      </div>

      {/* State Filter Pills */}
      <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[#11131a] border border-zinc-800 text-xs font-mono w-fit">
        {["all", "PENDING_APPROVAL", "APPROVED", "EXECUTED", "REJECTED"].map((st) => (
          <button
            key={st}
            onClick={() => setStateFilter(st)}
            className={cn(
              "px-3 py-1 rounded font-medium transition-colors uppercase",
              stateFilter === st
                ? "bg-sky-500 text-black font-bold"
                : "text-zinc-400 hover:text-zinc-200"
            )}
          >
            {st.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Action Cards Feed */}
      {isLoading ? (
        <div className="space-y-4">
          <LoadingSkeleton variant="card" count={3} />
        </div>
      ) : error ? (
        <ErrorState
          title="Failed to Load Finance Actions"
          message={error instanceof Error ? error.message : "Error connecting to backend"}
          onRetry={refetch}
        />
      ) : actionsList.length === 0 ? (
        <EmptyState
          title="No Finance Actions Found"
          description="Actions will appear here when recommended from exception dossiers or automated policies."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {actionsList.map((action, idx) => (
            <ActionCard key={action.id ? `${action.id}-${idx}` : `action-${idx}`} action={action} />
          ))}
        </div>
      )}
    </div>
  );
}
