"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { settlementsApi } from "@/lib/api/settlementsApi";
import { formatINR, formatDateTime } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import {
  Landmark,
  ArrowRight,
  FileSpreadsheet,
  CheckCircle2,
  FileCheck,
} from "lucide-react";

export default function SettlementsPage() {
  const {
    data: settlementsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["settlements-list"],
    queryFn: () => settlementsApi.getSettlements({ limit: 50 }),
    refetchInterval: 15000,
  });

  const settlements = settlementsData?.settlements || [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Settlement Intelligence & 3-Way Bank Parity
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Automated gateway settlement decomposition, GST tax-line audits, and UTR bank statement credits matching.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-zinc-400">Total Batches:</span>
          <span className="font-mono text-sm font-bold text-zinc-100 px-2.5 py-1 rounded bg-[#171a23] border border-zinc-800">
            {settlementsData?.total_count || settlements.length} Settlements
          </span>
        </div>
      </div>

      {/* Settlements Table */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono flex items-center gap-2">
            <Landmark className="h-4 w-4 text-sky-400" />
            Settlement Payout Batches
          </h2>
          <span className="text-xs font-mono text-zinc-500">
            Razorpay Payouts & UTR Reference Parity
          </span>
        </div>

        {isLoading ? (
          <LoadingSkeleton variant="table" count={5} />
        ) : error ? (
          <ErrorState
            title="Failed to Load Settlements"
            message={error instanceof Error ? error.message : "Error connecting to backend"}
            onRetry={refetch}
          />
        ) : settlements.length === 0 ? (
          <EmptyState
            title="No Settlements Ingested"
            description="Sync payments and settlements from the Razorpay Gateway page or execute a reconciliation run."
          />
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                  <th className="py-2.5 px-3">Settlement ID</th>
                  <th className="py-2.5 px-3">Bank UTR Reference</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Net Amount</th>
                  <th className="py-2.5 px-3 text-right">Fees / Tax</th>
                  <th className="py-2.5 px-3 text-right">Created At</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {settlements.map((s, idx) => (
                  <tr key={s.settlement_id ? `${s.settlement_id}-${idx}` : `settlement-${idx}`} className="hover:bg-[#171a23] transition-colors">
                    <td className="py-3 px-3 font-bold text-zinc-100">{s.settlement_id}</td>
                    <td className="py-3 px-3 text-zinc-400">{s.utr || "Pending UTR"}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="py-3 px-3 text-right font-bold font-tabular text-zinc-100">
                      {formatINR(s.expected_net_amount ?? s.gross_amount ?? s.amount)}
                    </td>
                    <td className="py-3 px-3 text-right text-zinc-400 font-tabular text-[11px]">
                      {s.gross_amount ? `Gross: ${formatINR(s.gross_amount)}` : (s.fees ? `${formatINR(s.fees)} / ${formatINR(s.tax)}` : "—")}
                    </td>
                    <td className="py-3 px-3 text-right text-zinc-500 text-[11px]">
                      {formatDateTime(s.settlement_date ?? s.created_at)}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <Link
                        href={`/settlements/${encodeURIComponent(s.settlement_id)}/tax-audit`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-amber-950/60 hover:bg-amber-900 border border-amber-800/60 text-amber-300 text-xs font-semibold transition-colors"
                      >
                        <FileCheck className="h-3 w-3" /> Tax Audit
                      </Link>
                      <Link
                        href={`/settlements/${encodeURIComponent(s.settlement_id)}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-sky-950/80 hover:bg-sky-900 border border-sky-800/60 text-sky-300 text-xs font-semibold transition-colors"
                      >
                        Breakdown <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
