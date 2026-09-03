"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatPercent, formatINR, cn } from "@/lib/utils/formatters";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  BarChart3,
  CheckCircle2,
  Cpu,
  Play,
  RotateCcw,
  Zap,
  Target,
  ShieldCheck,
  Loader2,
} from "lucide-react";

export default function BenchmarkPage() {
  const queryClient = useQueryClient();
  const [numTransactions, setNumTransactions] = useState<number>(100);

  const {
    data: benchmark,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["canonical-benchmark", numTransactions],
    queryFn: () => controllerApi.getBenchmark(numTransactions, 42),
    staleTime: 60000,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Canonical Track 4 Evaluation Console
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Measured accuracy, precision, recall, and throughput benchmarks against ground truth synthetic batch evaluations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={numTransactions}
            onChange={(e) => setNumTransactions(Number(e.target.value))}
            className="rounded border border-zinc-800 bg-[#171a23] px-3 py-1.5 text-zinc-300 font-mono text-xs focus:border-sky-500 focus:outline-hidden"
          >
            <option value={50}>N = 50 Transactions (Official Track 4 Bar)</option>
            <option value={100}>N = 100 Transactions (Extended Suite)</option>
            <option value={200}>N = 200 Transactions (High Throughput)</option>
          </select>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-sky-500 hover:bg-sky-400 text-black font-mono font-bold text-xs disabled:opacity-50 transition-colors"
          >
            {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-current" />}
            <span>Re-evaluate</span>
          </button>
        </div>
      </div>

      {/* Accuracy & Quality KPI Grid */}
      {isLoading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : error ? (
        <ErrorState
          title="Failed to Run Benchmark Evaluation"
          message={error instanceof Error ? error.message : "Error executing benchmark"}
          onRetry={refetch}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 font-mono text-xs">
          {/* Measured Accuracy */}
          <div className="rounded-lg border border-emerald-900/50 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Reconciliation Accuracy</span>
              <Target className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-300 font-tabular">
              {formatPercent(benchmark?.accuracy)}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">Ground truth verified</div>
          </div>

          {/* Precision & Recall */}
          <div className="rounded-lg border border-sky-900/50 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Precision / Recall</span>
              <CheckCircle2 className="h-4 w-4 text-sky-400" />
            </div>
            <div className="text-xl font-bold text-sky-300 font-tabular">
              {formatPercent(benchmark?.precision)} / {formatPercent(benchmark?.recall)}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">F1 Score: <strong>{formatPercent(benchmark?.f1_score)}</strong></div>
          </div>

          {/* Throughput */}
          <div className="rounded-lg border border-purple-900/50 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Throughput Speed</span>
              <Zap className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-purple-300 font-tabular">
              {benchmark?.throughput_records_per_sec ? benchmark.throughput_records_per_sec.toFixed(0) : 0} <span className="text-xs font-normal">rec/sec</span>
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">
              Latency: {benchmark?.duration_ms ? benchmark.duration_ms.toFixed(1) : 0} ms
            </div>
          </div>

          {/* Evaluated Scale */}
          <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4">
            <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] pb-2">
              <span>Transactions Evaluated</span>
              <BarChart3 className="h-4 w-4 text-zinc-400" />
            </div>
            <div className="text-2xl font-bold text-zinc-100 font-tabular">
              {benchmark?.num_transactions}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">
              Deterministic + ML Multi-Layered
            </div>
          </div>
        </div>
      )}

      {/* Matching Breakdown Console */}
      {benchmark && (
        <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 text-xs font-mono space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
              Multi-Layered Matching Arbitration Matrix
            </h2>
            <span className="text-zinc-500">Seed: 42 (Reproducible Canonical Benchmark)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-emerald-950/20 border border-emerald-900/40 space-y-1">
              <div className="text-[10px] text-emerald-400 uppercase font-bold">Stage 1: Deterministic Matches</div>
              <div className="text-2xl font-bold text-emerald-200">{benchmark.deterministic_matches}</div>
              <div className="text-[11px] text-zinc-400">Zero-variance exact identifier matches</div>
            </div>

            <div className="p-4 rounded-lg bg-purple-950/20 border border-purple-900/40 space-y-1">
              <div className="text-[10px] text-purple-400 uppercase font-bold">Stage 2: ML Recovered Matches</div>
              <div className="text-2xl font-bold text-purple-200">{benchmark.ml_recovered_matches}</div>
              <div className="text-[11px] text-zinc-400">Recovered via XGBoost candidate probabilities</div>
            </div>

            <div className="p-4 rounded-lg bg-rose-950/20 border border-rose-900/40 space-y-1">
              <div className="text-[10px] text-rose-400 uppercase font-bold">Stage 3: Unresolved Exceptions</div>
              <div className="text-2xl font-bold text-rose-200">{benchmark.unresolved_records}</div>
              <div className="text-[11px] text-zinc-400">Routed to forensic dossiers for HITL review</div>
            </div>
          </div>
        </div>
      )}

      {/* Official Razorpay Track 4 Bar Compliance Matrix */}
      <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-5 text-xs font-mono text-zinc-300 space-y-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-100 flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          Razorpay Buildathon Track 4 Requirements Compliance
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div className="p-3 rounded bg-[#171a23] border border-zinc-800">
            <div className="text-emerald-400 font-bold mb-1">✓ 50+ Record Batch</div>
            <p className="text-[11px] text-zinc-400">Closes finance-ops loop across multi-source synthetic batch.</p>
          </div>
          <div className="p-3 rounded bg-[#171a23] border border-zinc-800">
            <div className="text-emerald-400 font-bold mb-1">✓ Measured Accuracy</div>
            <p className="text-[11px] text-zinc-400">Precision, recall, and F1 mathematically evaluated against ground truth.</p>
          </div>
          <div className="p-3 rounded bg-[#171a23] border border-zinc-800">
            <div className="text-emerald-400 font-bold mb-1">✓ Honest Exception List</div>
            <p className="text-[11px] text-zinc-400">Unreconciled records routed with honest root causes and bounding limits.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
