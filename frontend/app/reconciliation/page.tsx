"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { reconciliationApi } from "@/lib/api/reconciliationApi";
import { formatINR, formatDateTime, cn } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { RunBatchModal } from "@/components/reconciliation/RunBatchModal";
import {
  Play,
  CreditCard,
  Building2,
  Receipt,
  Layers,
} from "lucide-react";

export default function ReconciliationPage() {
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);

  // Raw feed transactions query
  const {
    data: txnsData,
    isLoading: txnsLoading,
    error: txnsError,
    refetch: refetchTxns,
  } = useQuery({
    queryKey: ["reconciliation-transactions"],
    queryFn: () => controllerApi.getTransactions({ limit: 100 }),
    refetchInterval: 15000,
  });

  // Reconciliation runs history query
  const {
    data: runsData,
    isLoading: runsLoading,
  } = useQuery({
    queryKey: ["reconciliation-runs"],
    queryFn: () => reconciliationApi.getRuns(10),
    refetchInterval: 20000,
  });

  const transactions = txnsData?.transactions || [];
  const filteredTxns =
    sourceFilter === "all"
      ? transactions
      : transactions.filter((t) => (t.source || "").toLowerCase() === (sourceFilter || "").toLowerCase());

  const getSourceIcon = (source?: string | null) => {
    switch ((source || "").toLowerCase()) {
      case "gateway":
        return <CreditCard className="h-3.5 w-3.5 text-[#949da6]" />;
      case "ledger":
        return <Receipt className="h-3.5 w-3.5 text-[#7eaa8e]" />;
      case "bank":
        return <Building2 className="h-3.5 w-3.5 text-[#ab9f90]" />;
      default:
        return <Layers className="h-3.5 w-3.5 text-[#8e96a0]" />;
    }
  };

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Page Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            Continuous Reconciliation Engine
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Multi-Source Feeds &amp; Ingestion Lineage
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Deterministic rule-matching, fuzzy metadata similarity, and ML arbitration across feeds
          </p>
        </div>

        <button
          onClick={() => setIsBatchModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xs font-semibold text-xs transition-micro"
          style={{
            color: "#080a0c",
            background: "var(--accent)",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          <span>Execute Reconciliation Batch</span>
        </button>
      </div>

      {/* Historical Runs Summary Table */}
      <div
        className="rounded-sm border p-6 text-[#eceae6]"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="flex items-center justify-between pb-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#8e96a0] flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#c9a96e]" />
            Reconciliation Run Execution History
          </h2>
          <span className="text-xs font-mono text-[#545e6a]">
            {runsData?.total_count || 0} runs executed
          </span>
        </div>

        {runsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={3} />
          </div>
        ) : !runsData?.runs || runsData.runs.length === 0 ? (
          <EmptyState
            title="No Reconciliation Runs Found"
            description="Run a new batch using the top button to trigger ingestion and 3-way matching."
          />
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left text-xs">
              <thead>
                <tr
                  className="text-[10px] uppercase font-semibold"
                  style={{
                    color: "var(--text-tertiary)",
                    borderBottom: "1px solid var(--border-subtle)",
                  }}
                >
                  <th className="py-2.5 px-3">Run Identifier</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Gateway Feed</th>
                  <th className="py-2.5 px-3">Ledger Feed</th>
                  <th className="py-2.5 px-3">Bank Feed</th>
                  <th className="py-2.5 px-3 text-right">Matched</th>
                  <th className="py-2.5 px-3 text-right">Exceptions</th>
                  <th className="py-2.5 px-3 text-right">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {runsData.runs.map((run, idx) => (
                  <tr
                    key={run.id ? `${run.id}-${idx}` : `run-${idx}`}
                    className="hover:bg-[#13161a] transition-micro"
                  >
                    <td className="py-3 px-3 font-mono font-bold text-[#eceae6]">{run.run_id}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="py-3 px-3 text-[#8e96a0] font-mono">{run.gateway_count} txns</td>
                    <td className="py-3 px-3 text-[#8e96a0] font-mono">{run.ledger_count} txns</td>
                    <td className="py-3 px-3 text-[#8e96a0] font-mono">{run.bank_count} txns</td>
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#6ecba0] font-tabular">
                      {run.match_count}
                    </td>
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#e07070] font-tabular">
                      {run.exception_count}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#545e6a] text-[11px]">
                      {formatDateTime(run.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Multi-Source Raw Transactions Feed Table */}
      <div
        className="rounded-sm border p-6 text-[#eceae6]"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#8e96a0]">
              Raw Multi-Source Transaction Feed
            </h2>
            <p className="text-xs text-[#545e6a] mt-0.5">
              Normalized ingested records across all source feeds ({filteredTxns.length} records shown)
            </p>
          </div>

          {/* Filter Pills */}
          <div
            className="flex items-center gap-1 p-1 rounded-xs border text-xs"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            {["all", "gateway", "ledger", "bank"].map((src) => (
              <button
                key={src}
                onClick={() => setSourceFilter(src)}
                className={cn(
                  "px-2.5 py-1 rounded-xs text-xs font-medium transition-micro uppercase",
                  sourceFilter === src
                    ? "font-semibold text-[#eceae6]"
                    : "text-[#8e96a0] hover:text-[#eceae6]"
                )}
                style={sourceFilter === src ? {
                  background: "var(--surface-3)",
                  border: "1px solid var(--border-standard)",
                } : {
                  border: "1px solid transparent",
                }}
              >
                {src}
              </button>
            ))}
          </div>
        </div>

        {txnsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={6} />
          </div>
        ) : txnsError ? (
          <ErrorState
            title="Failed to Load Ingested Transactions"
            message={txnsError instanceof Error ? txnsError.message : "Error connecting to backend"}
            onRetry={refetchTxns}
          />
        ) : filteredTxns.length === 0 ? (
          <EmptyState
            title="No Ingested Records Found"
            description="Run a reconciliation batch to ingest records from configured data sources."
          />
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left text-xs">
              <thead>
                <tr
                  className="text-[10px] uppercase font-semibold"
                  style={{
                    color: "var(--text-tertiary)",
                    borderBottom: "1px solid var(--border-subtle)",
                  }}
                >
                  <th className="py-2.5 px-3">Transaction ID</th>
                  <th className="py-2.5 px-3">Source</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {filteredTxns.slice(0, 30).map((t, idx) => {
                  const txnId = t.domain_transaction_id || t.id || `raw-txn-${idx}`;
                  return (
                    <tr
                      key={txnId}
                      className="hover:bg-[#13161a] transition-micro"
                    >
                      <td className="py-3 px-3 font-mono font-medium text-[#eceae6]">
                        {txnId}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1.5 capitalize text-[#8e96a0]">
                          {getSourceIcon(t.source)}
                          <span>{t.source}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={t.status} />
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold font-tabular text-[#eceae6]">
                        {formatINR(t.amount)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#545e6a] text-[11px]">
                        {formatDateTime(t.timestamp)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Batch Execution Modal */}
      {isBatchModalOpen && (
        <RunBatchModal
          isOpen={isBatchModalOpen}
          onClose={() => setIsBatchModalOpen(false)}
        />
      )}
    </div>
  );
}
