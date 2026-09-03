"use client";

import React from "react";
import { formatINR, formatVariance, cn } from "@/lib/utils/formatters";
import type { SettlementFinancialBreakdown } from "@/types/settlements";
import { Minus, Plus, Equal, AlertCircle, CheckCircle2 } from "lucide-react";

interface SettlementDecompositionProps {
  breakdown?: SettlementFinancialBreakdown | null;
  isLoading?: boolean;
}

export function SettlementDecomposition({
  breakdown,
  isLoading,
}: SettlementDecompositionProps) {
  if (isLoading || !breakdown) {
    return (
      <div className="h-64 rounded-lg border border-zinc-800 bg-[#11131a] p-5 animate-pulse">
        <div className="h-4 w-48 rounded bg-zinc-800 mb-6" />
        <div className="grid grid-cols-5 gap-3">
          <div className="h-24 rounded bg-zinc-800" />
          <div className="h-24 rounded bg-zinc-800" />
          <div className="h-24 rounded bg-zinc-800" />
          <div className="h-24 rounded bg-zinc-800" />
          <div className="h-24 rounded bg-zinc-800" />
        </div>
      </div>
    );
  }

  const varianceResult = formatVariance(breakdown.variance);
  const isClean = varianceResult.isZero || breakdown.variance_type === "NO_VARIANCE";

  return (
    <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 text-zinc-100">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400 font-mono">
            Settlement Financial Decomposition
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Gross Transaction Volume $-$ Gateway Fees $-$ Taxes (GST) $+$ Adjustments $=$ Expected Net Settlement
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-zinc-400">Classification:</span>
          <span
            className={cn(
              "px-2 py-0.5 rounded text-xs font-mono font-bold border",
              isClean
                ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                : "bg-rose-950/60 text-rose-400 border-rose-800/60"
            )}
          >
            {(breakdown.variance_type || "VARIANCE").replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {/* Financial Formula Cards Layout */}
      <div className="grid grid-cols-1 gap-2 pt-5 md:grid-cols-11 items-center">
        {/* Gross */}
        <div className="md:col-span-2 rounded-lg border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] font-mono uppercase text-zinc-400">Gross Captured</div>
          <div className="mt-1 font-mono text-base font-bold text-zinc-100 font-tabular">
            {formatINR(breakdown.gross_amount)}
          </div>
        </div>

        {/* Minus Sign */}
        <div className="flex justify-center text-zinc-500">
          <Minus className="h-4 w-4" />
        </div>

        {/* Fee */}
        <div className="md:col-span-2 rounded-lg border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] font-mono uppercase text-zinc-400">Gateway Fees</div>
          <div className="mt-1 font-mono text-base font-bold text-rose-300 font-tabular">
            {formatINR(breakdown.fee_amount)}
          </div>
        </div>

        {/* Minus Sign */}
        <div className="flex justify-center text-zinc-500">
          <Minus className="h-4 w-4" />
        </div>

        {/* Tax */}
        <div className="md:col-span-2 rounded-lg border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] font-mono uppercase text-zinc-400">GST on Fees (18%)</div>
          <div className="mt-1 font-mono text-base font-bold text-amber-300 font-tabular">
            {formatINR(breakdown.tax_amount)}
          </div>
        </div>

        {/* Equals Sign */}
        <div className="flex justify-center text-zinc-500">
          <Equal className="h-4 w-4" />
        </div>

        {/* Expected Net */}
        <div className="md:col-span-2 rounded-lg border border-sky-900/50 bg-sky-950/20 p-3">
          <div className="text-[10px] font-mono uppercase text-sky-400">Expected Net Payout</div>
          <div className="mt-1 font-mono text-base font-bold text-sky-200 font-tabular">
            {formatINR(breakdown.expected_net_amount)}
          </div>
        </div>
      </div>

      {/* Comparison against Bank Received Credit */}
      <div className="mt-5 rounded-lg border border-zinc-800/80 bg-[#141722] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="text-xs text-zinc-400 font-mono">Actual Bank Statement Credit (UTR Verified)</div>
          <div className="font-mono text-xl font-bold text-zinc-100 font-tabular">
            {formatINR(breakdown.bank_received_amount)}
          </div>
        </div>

        <div className="flex items-center gap-3 border-t sm:border-t-0 sm:border-l border-zinc-800 pt-3 sm:pt-0 sm:pl-6">
          <div className="space-y-0.5">
            <div className="text-[11px] font-mono text-zinc-500 uppercase">Reconciliation Variance</div>
            <div
              className={cn(
                "font-mono text-lg font-bold font-tabular flex items-center gap-1.5",
                isClean ? "text-emerald-400" : "text-rose-400"
              )}
            >
              {isClean ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              {varianceResult.text}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
