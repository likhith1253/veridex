"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatINR, formatPercent, cn } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import {
  AlertOctagon,
  Search,
  Filter,
  ArrowRight,
  Clock,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export default function ExceptionsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  // Exceptions Query
  const {
    data: exceptionsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["exceptions-queue", statusFilter, categoryFilter, searchQuery, page],
    queryFn: () =>
      controllerApi.getExceptions({
        status: statusFilter === "all" ? undefined : statusFilter,
        category: categoryFilter === "all" ? undefined : categoryFilter,
        transaction_id: searchQuery ? searchQuery : undefined,
        page,
        page_size: pageSize,
      }),
    refetchInterval: 15000,
  });

  // Exception Aging Metrics Query
  const { data: aging } = useQuery({
    queryKey: ["exceptions-aging"],
    queryFn: () => controllerApi.getExceptionAging(),
    staleTime: 30000,
  });

  const exceptions = exceptionsData?.exceptions || [];
  const totalCount = exceptionsData?.total_count || 0;
  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Exception Queue & Investigation Workspace
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Forensic discrepancy resolution queue with root-cause ML arbitration and policy recommendations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-zinc-400">Total Unresolved:</span>
          <span className="font-mono text-sm font-bold text-rose-400 px-2.5 py-1 rounded bg-rose-950/60 border border-rose-800/60">
            {totalCount} Exceptions
          </span>
        </div>
      </div>

      {/* Exception Aging Distribution Widgets */}
      {aging && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 font-mono text-xs">
          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-3.5">
            <div className="text-[10px] text-zinc-500 uppercase">0 - 24 Hours Aging</div>
            <div className="mt-1 text-xl font-bold text-emerald-400 font-tabular">{aging.bucket_0_24h}</div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Fresh exceptions</div>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-3.5">
            <div className="text-[10px] text-zinc-500 uppercase">24 - 48 Hours Aging</div>
            <div className="mt-1 text-xl font-bold text-amber-400 font-tabular">{aging.bucket_24_48h}</div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Review in progress</div>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-3.5">
            <div className="text-[10px] text-zinc-500 uppercase">48 - 72 Hours Aging</div>
            <div className="mt-1 text-xl font-bold text-rose-300 font-tabular">{aging.bucket_48_72h}</div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Approaching SLA breach</div>
          </div>

          <div className="rounded-lg border border-rose-900/50 bg-rose-950/20 p-3.5">
            <div className="text-[10px] text-rose-400 uppercase">72+ Hours (Critical SLA)</div>
            <div className="mt-1 text-xl font-bold text-rose-400 font-tabular">{aging.bucket_72h_plus}</div>
            <div className="text-[10px] text-rose-300 mt-0.5">High financial exposure</div>
          </div>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-4 flex flex-col md:flex-row items-center justify-between gap-3 text-xs font-mono">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search by Txn ID / Ref Number..."
            className="w-full rounded border border-zinc-800 bg-[#171a23] pl-9 pr-3 py-1.5 text-zinc-200 placeholder-zinc-500 focus:border-sky-500 focus:outline-hidden"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded border border-zinc-800 bg-[#171a23] px-3 py-1.5 text-zinc-300 focus:border-sky-500 focus:outline-hidden"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>

          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            className="rounded border border-zinc-800 bg-[#171a23] px-3 py-1.5 text-zinc-300 focus:border-sky-500 focus:outline-hidden"
          >
            <option value="all">All Categories</option>
            <option value="AMOUNT_MISMATCH">Amount Mismatch</option>
            <option value="FEE_DISCREPANCY">Fee Discrepancy</option>
            <option value="TAX_VARIANCE">Tax Variance</option>
            <option value="MISSING_BANK_CREDIT">Missing Bank Credit</option>
            <option value="TIMING_DELAY">Timing Delay</option>
            <option value="OVER_REFUND">Over Refund</option>
            <option value="DUPLICATE_TRANSACTION">Duplicate Transaction</option>
          </select>
        </div>
      </div>

      {/* Exception Records Table */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        {isLoading ? (
          <LoadingSkeleton variant="table" count={8} />
        ) : error ? (
          <ErrorState
            title="Failed to Load Exceptions"
            message={error instanceof Error ? error.message : "Error connecting to backend"}
            onRetry={refetch}
          />
        ) : exceptions.length === 0 ? (
          <EmptyState
            title="No Exceptions Match Filter"
            description="All records in the current scope are reconciled, or try clearing search filters."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                  <th className="py-2.5 px-3">Exception / Entity ID</th>
                  <th className="py-2.5 px-3">Discrepancy Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">AI Confidence</th>
                  <th className="py-2.5 px-3 text-right">Exposure Amount</th>
                  <th className="py-2.5 px-3">Recommended Policy Action</th>
                  <th className="py-2.5 px-3 text-right">Dossier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {exceptions.map((ex) => (
                  <tr key={ex.id} className="hover:bg-[#171a23] transition-colors">
                    <td className="py-3 px-3 font-semibold text-zinc-100">
                      <div>{ex.id}</div>
                      <div className="text-[10px] text-zinc-500">{ex.transaction_id}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-zinc-200">{(ex.exception_category || "UNKNOWN").replace(/_/g, " ")}</span>
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={ex.status} />
                    </td>
                    <td className="py-3 px-3">
                      <ConfidenceBadge confidence={ex.confidence} />
                    </td>
                    <td className="py-3 px-3 text-right font-bold font-tabular text-rose-300">
                      {formatINR(ex.financial_exposure)}
                    </td>
                    <td className="py-3 px-3 text-zinc-400 max-w-xs truncate text-[11px]">
                      {ex.recommended_action || "Manual Review"}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Link
                        href={`/exceptions/${encodeURIComponent(ex.id)}`}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded bg-sky-950/80 hover:bg-sky-900 border border-sky-800/60 text-sky-300 text-xs font-semibold transition-colors"
                      >
                        Investigate <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination Controls */}
            <div className="flex items-center justify-between border-t border-zinc-800 pt-4 text-xs font-mono text-zinc-400">
              <div>
                Showing page {page} of {totalPages} ({totalCount} total exceptions)
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1 rounded border border-zinc-800 bg-[#171a23] hover:bg-zinc-800 disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-1 rounded border border-zinc-800 bg-[#171a23] hover:bg-zinc-800 disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
