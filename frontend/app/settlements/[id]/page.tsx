"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { settlementsApi } from "@/lib/api/settlementsApi";
import { formatINR, formatDateTime } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { SettlementDecomposition } from "@/components/settlements/SettlementDecomposition";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ArrowLeft,
  Landmark,
  FileCheck,
  CreditCard,
  Layers,
  ArrowRight,
} from "lucide-react";

export default function SettlementDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  // Financial Breakdown Query
  const {
    data: breakdown,
    isLoading: breakdownLoading,
    error: breakdownError,
    refetch,
  } = useQuery({
    queryKey: ["settlement-breakdown", id],
    queryFn: () => settlementsApi.getFinancialBreakdown(id),
    enabled: !!id,
  });

  // Linked Transactions Query
  const {
    data: linkage,
    isLoading: linkageLoading,
  } = useQuery({
    queryKey: ["settlement-transactions", id],
    queryFn: () => settlementsApi.getTransactionLinkage(id),
    enabled: !!id,
  });

  if (breakdownError) {
    return (
      <ErrorState
        title="Failed to Load Settlement Breakdown"
        message={breakdownError instanceof Error ? breakdownError.message : "Error connecting to backend"}
        onRetry={refetch}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/settlements"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#171a23] hover:bg-[#1e222e] text-zinc-400 hover:text-zinc-200 border border-zinc-800 font-mono text-xs transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Settlements
          </Link>
          <span className="text-zinc-600">/</span>
          <span className="text-xs font-mono text-zinc-400">Settlement: {id}</span>
        </div>

        <Link
          href={`/settlements/${encodeURIComponent(id)}/tax-audit`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-black font-mono font-bold text-xs shadow-sm transition-colors"
        >
          <FileCheck className="h-3.5 w-3.5" />
          <span>Inspect GST Tax Line Audit</span>
        </Link>
      </div>

      {/* Financial Decomposition Component */}
      <SettlementDecomposition
        breakdown={breakdown}
        isLoading={breakdownLoading}
      />

      {/* Linked Transactions Table */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-sky-400" />
              Linked Gateway Payments in Batch
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              UTR Reference: <strong className="text-zinc-300 font-mono">{linkage?.utr || "N/A"}</strong> | Payments Count:{" "}
              <strong className="text-zinc-300 font-mono">{linkage?.total_payments_count || 0}</strong>
            </p>
          </div>

          {linkage?.total_payments_volume_inr && (
            <div className="text-right font-mono text-xs">
              <span className="text-zinc-500 block text-[10px]">Total Linked Volume</span>
              <span className="text-zinc-100 font-bold font-tabular">
                {formatINR(linkage.total_payments_volume_inr)}
              </span>
            </div>
          )}
        </div>

        {linkageLoading ? (
          <LoadingSkeleton variant="table" count={4} />
        ) : !linkage?.payments || linkage.payments.length === 0 ? (
          <div className="p-8 text-center text-zinc-500 font-mono text-xs">
            No linked transactions recorded for this settlement.
          </div>
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                  <th className="py-2.5 px-3">Payment ID</th>
                  <th className="py-2.5 px-3">Order Ref</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Gross Amount</th>
                  <th className="py-2.5 px-3 text-right">MDR Fee</th>
                  <th className="py-2.5 px-3 text-right">Tax</th>
                  <th className="py-2.5 px-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {linkage.payments.map((p, idx) => (
                  <tr key={p.payment_id ? `${p.payment_id}-${idx}` : `payment-${idx}`} className="hover:bg-[#171a23] transition-colors">
                    <td className="py-3 px-3 font-bold text-zinc-100">{p.payment_id}</td>
                    <td className="py-3 px-3 text-zinc-400">{p.order_id || "—"}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={p.status} />
                    </td>
                    <td className="py-3 px-3 text-right font-bold font-tabular text-zinc-100">
                      {formatINR(p.amount)}
                    </td>
                    <td className="py-3 px-3 text-right text-rose-300 font-tabular text-[11px]">
                      {p.fee ? formatINR(p.fee) : "—"}
                    </td>
                    <td className="py-3 px-3 text-right text-amber-300 font-tabular text-[11px]">
                      {p.tax ? formatINR(p.tax) : "—"}
                    </td>
                    <td className="py-3 px-3 text-right text-zinc-500 text-[11px]">
                      {formatDateTime(p.timestamp)}
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
