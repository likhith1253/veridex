"use client";

import React from "react";
import { formatINR, formatPercent } from "@/lib/utils/formatters";
import type { ReconciliationFunnel } from "@/types/controller";
import { CheckCircle2, Cpu, AlertTriangle, Layers } from "lucide-react";

interface FunnelChartProps {
  funnel?: ReconciliationFunnel | null;
  isLoading?: boolean;
}

export function FunnelChart({ funnel, isLoading }: FunnelChartProps) {
  if (isLoading || !funnel) {
    return (
      <div className="h-64 rounded-lg border border-zinc-800 bg-[#11131a] p-5 animate-pulse">
        <div className="h-4 w-44 rounded bg-zinc-800 mb-6" />
        <div className="space-y-4">
          <div className="h-10 rounded bg-zinc-800" />
          <div className="h-10 rounded bg-zinc-800" />
          <div className="h-10 rounded bg-zinc-800" />
        </div>
      </div>
    );
  }

  const detMatches = funnel.deterministic_matches ?? 0;
  const mlMatches = funnel.ml_recovered ?? funnel.ml_matches ?? 0;
  const exceptions = funnel.unresolved ?? funnel.unmatched_exceptions ?? 0;
  const totalMatches = detMatches + mlMatches;
  const totalItems = funnel.incoming_records ?? (totalMatches + exceptions);
  const matchRate = totalItems > 0
    ? (totalMatches / totalItems) * 100
    : (funnel.final_match_rate ? (funnel.final_match_rate > 1 ? funnel.final_match_rate : funnel.final_match_rate * 100) : 0);
  const deterministicPct = totalItems > 0 ? (detMatches / totalItems) * 100 : 0;
  const mlPct = totalItems > 0 ? (mlMatches / totalItems) * 100 : 0;
  const exceptionPct = totalItems > 0 ? (exceptions / totalItems) * 100 : 0;

  return (
    <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 text-zinc-100">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400 font-mono">
            3-Way Reconciliation Pipeline Funnel
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Deterministic Engine $\rightarrow$ ML XGBoost Arbitration $\rightarrow$ Reconciled vs Exceptions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-zinc-400">Total Volume:</span>
          <span className="font-mono text-sm font-bold text-zinc-100 font-tabular">
            {funnel.total_volume_inr ? formatINR(funnel.total_volume_inr) : `${totalItems} Records`}
          </span>
        </div>
      </div>

      {/* Stage Breakdown Grid */}
      <div className="grid grid-cols-1 gap-4 pt-5 sm:grid-cols-3">
        {/* Deterministic Stage */}
        <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-4">
          <div className="flex items-center justify-between text-xs text-emerald-400 font-semibold mb-2">
            <span className="flex items-center gap-1.5 font-mono">
              <CheckCircle2 className="h-3.5 w-3.5" /> Stage 1: Deterministic
            </span>
            <span className="font-mono text-emerald-300">
              {Number.isFinite(deterministicPct) ? deterministicPct.toFixed(1) : "0.0"}%
            </span>
          </div>
          <div className="font-mono text-2xl font-bold text-emerald-200">
            {detMatches}
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">
            Exact UTR / RRN / Account parity matches
          </p>
        </div>

        {/* ML Recovered Stage */}
        <div className="rounded-lg border border-purple-900/40 bg-purple-950/20 p-4">
          <div className="flex items-center justify-between text-xs text-purple-400 font-semibold mb-2">
            <span className="flex items-center gap-1.5 font-mono">
              <Cpu className="h-3.5 w-3.5" /> Stage 2: ML Recovered
            </span>
            <span className="font-mono text-purple-300">
              {Number.isFinite(mlPct) ? mlPct.toFixed(1) : "0.0"}%
            </span>
          </div>
          <div className="font-mono text-2xl font-bold text-purple-200">
            {mlMatches}
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">
            XGBoost candidate probability scoring
          </p>
        </div>

        {/* Unmatched Exceptions Stage */}
        <div className="rounded-lg border border-rose-900/40 bg-rose-950/20 p-4">
          <div className="flex items-center justify-between text-xs text-rose-400 font-semibold mb-2">
            <span className="flex items-center gap-1.5 font-mono">
              <AlertTriangle className="h-3.5 w-3.5" /> Stage 3: Exceptions
            </span>
            <span className="font-mono text-rose-300">
              {Number.isFinite(exceptionPct) ? exceptionPct.toFixed(1) : "0.0"}%
            </span>
          </div>
          <div className="font-mono text-2xl font-bold text-rose-200">
            {exceptions}
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">
            Routed to forensic investigation dossiers
          </p>
        </div>
      </div>

      {/* Visual Volume Progress Bar */}
      <div className="mt-5 space-y-2">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
          <span>Reconciliation Resolution Progress</span>
          <span className="text-zinc-200 font-bold">{matchRate.toFixed(2)}% Reconciled</span>
        </div>
        <div className="h-3 w-full rounded-full bg-zinc-900 overflow-hidden flex border border-zinc-800">
          <div
            style={{ width: `${deterministicPct}%` }}
            className="bg-emerald-500 transition-all duration-700"
            title={`Deterministic: ${funnel.deterministic_matches}`}
          />
          <div
            style={{ width: `${mlPct}%` }}
            className="bg-purple-500 transition-all duration-700"
            title={`ML Recovered: ${funnel.ml_matches}`}
          />
          <div
            style={{ width: `${exceptionPct}%` }}
            className="bg-rose-500 transition-all duration-700"
            title={`Unmatched Exceptions: ${funnel.unmatched_exceptions}`}
          />
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500 pt-1">
          <span>Reconciled Volume: {formatINR(funnel.reconciled_volume_inr)}</span>
          <span>Pending Volume: {formatINR(funnel.pending_volume_inr)}</span>
        </div>
      </div>
    </div>
  );
}
