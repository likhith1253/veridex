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
  GitMerge,
  Play,
  Filter,
  CreditCard,
  Building2,
  Receipt,
  Layers,
  CheckCircle2,
  Clock,
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
      : transactions.filter((t) => t.source.toLowerCase() === sourceFilter.toLowerCase());

  const getSourceIcon = (source: string) => {
    switch (source.toLowerCase()) {
      case "gateway":
        return <CreditCard className="h-3.5 w-3.5 text-sky-400" />;
      case "ledger":
        return <Receipt className="h-3.5 w-3.5 text-indigo-400" />;
      case "bank":
        return <Building2 className="h-3.5 w-3.5 text-emerald-400" />;
      default:
        return <Layers className="h-3.5 w-3.5 text-zinc-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Reconciliation Engine & Multi-Source Feeds
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Deterministic rule-matching, fuzzy similarity, and ML arbitration across Gateway, Ledger, and Bank feeds.
          </p>
        </div>

        <button
          onClick={() => setIsBatchModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-black font-mono font-bold text-xs shadow-md transition-colors"
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          <span>Execute Reconciliation Batch</span>
        </button>
      </div>

      {/* Historical Runs Summary Table */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono flex items-center gap-2">
            <Layers className="h-4 w-4 text-sky-400" />
            Reconciliation Run Execution History
          </h2>
          <span className="text-xs font-mono text-zinc-500">
            {runsData?.total_count || 0} runs executed
          </span>
        </div>

        {runsLoading ? (
          <LoadingSkeleton variant="table" count={3} />
        ) : !runsData?.runs || runsData.runs.length === 0 ? (
          <EmptyState
            title="No Reconciliation Runs Found"
            description="Run a new batch using the top button to trigger ingestion and 3-way matching."
          />
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
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
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {runsData.runs.map((run) => (
                  <tr key={run.id} className="hover:bg-[#171a23] transition-colors">
                    <td className="py-3 px-3 font-bold text-zinc-100">{run.run_id}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="py-3 px-3 text-zinc-400">{run.gateway_count} txns</td>
                    <td className="py-3 px-3 text-zinc-400">{run.ledger_count} txns</td>
                    <td className="py-3 px-3 text-zinc-400">{run.bank_count} txns</td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-400">
                      {run.match_count}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-rose-400">
                      {run.exception_count}
                    </td>
                    <td className="py-3 px-3 text-right text-zinc-500 text-[11px]">
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
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-zinc-800">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
              Raw Multi-Source Transaction Feed
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              Normalized ingested records across all source feeds ({filteredTxns.length} records shown)
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[#171a23] border border-zinc-800 text-xs font-mono">
            {["all", "gateway", "ledger", "bank"].map((src) => (
              <button
                key={src}
                onClick={() => setSourceFilter(src)}
                className={cn(
                  "px-2.5 py-1 rounded text-xs font-medium transition-colors uppercase",
                  sourceFilter === src
                    ? "bg-sky-500 text-black font-bold"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                {src}
              </button>
            ))}
          </div>
        </div>

        {txnsLoading ? (
          <LoadingSkeleton variant="table" count={6} />
        ) : txnsError ? (
          <ErrorState
            title="Failed to Load Ingested Transactions"
            message={txnsError instanceof Error ? txnsError.message : "Error connecting to backend"}
            onRetry={refetchTxns}
          />
        ) : filteredTxns.length === 0 ? (
          <EmptyState
            title="No Ingested Feed Records"
            description="Use the Execute Reconciliation Batch modal above or synchronize via Razorpay."
          />
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                  <th className="py-2.5 px-3">Transaction / Ref ID</th>
                  <th className="py-2.5 px-3">Feed Source</th>
                  <th className="py-2.5 px-3">Order Ref</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-right">Fee / Tax</th>
                  <th className="py-2.5 px-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {filteredTxns.map((t) => (
                  <tr key={t.id} className="hover:bg-[#171a23] transition-colors">
                    <td className="py-3 px-3 font-semibold text-zinc-100">
                      <div>{t.domain_transaction_id}</div>
                      {t.reference_number && (
                        <div className="text-[10px] text-zinc-500">{t.reference_number}</div>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono capitalize">
                        {getSourceIcon(t.source)}
                        {t.source}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-zinc-400">{t.order_id || "—"}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="py-3 px-3 text-right font-bold font-tabular text-zinc-100">
                      {formatINR(t.amount)}
                    </td>
                    <td className="py-3 px-3 text-right text-zinc-400 font-tabular text-[11px]">
                      {t.fee ? formatINR(t.fee) : "—"} / {t.tax ? formatINR(t.tax) : "—"}
                    </td>
                    <td className="py-3 px-3 text-right text-zinc-500 text-[11px]">
                      {formatDateTime(t.timestamp)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Batch Runner Modal */}
      <RunBatchModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
      />
    </div>
  );
}
