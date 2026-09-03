"use client";

import React, { useState } from "react";
import { X, Play, Loader2, CheckCircle2, AlertTriangle, Database } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { BatchIngestResponse } from "@/types/controller";

interface RunBatchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function RunBatchModal({ isOpen, onClose }: RunBatchModalProps) {
  const queryClient = useQueryClient();
  const [batchId, setBatchId] = useState(`run_ui_${Date.now().toString().slice(-6)}`);
  const [batchSize, setBatchSize] = useState(50);
  const [result, setResult] = useState<BatchIngestResponse | null>(null);

  const runMutation = useMutation({
    mutationFn: async () => {
      // Generate realistic N=50 synthetic batch across 3 feeds
      const gw: Array<Record<string, unknown>> = [];
      const ld: Array<Record<string, unknown>> = [];
      const bk: Array<Record<string, unknown>> = [];
      const now = new Date().toISOString();

      for (let i = 1; i <= batchSize; i++) {
        const orderId = `ORD_${batchId}_${i.toString().padStart(4, "0")}`;
        const payId = `PAY_${batchId}_${i.toString().padStart(4, "0")}`;
        const utr = `UTR_${batchId}_${i.toString().padStart(4, "0")}`;
        const amount = 5000 + i * 250;
        const fee = Number((amount * 0.02).toFixed(2));
        const tax = Number((fee * 0.18).toFixed(2));
        const net = amount - fee - tax;

        // Clean match for 70% of transactions, intentional discrepancies on 30%
        gw.push({
          txn_id: payId,
          order_id: orderId,
          reference_number: utr,
          amount: amount.toString(),
          currency: "INR",
          fee: fee.toString(),
          tax: tax.toString(),
          timestamp: now,
          narration: `Payment for ${orderId}`,
        });

        ld.push({
          txn_id: `LD_${orderId}`,
          order_id: orderId,
          reference_number: orderId,
          amount: (i % 7 === 0 ? amount + 100 : amount).toString(), // intentional amount mismatch on i%7
          currency: "INR",
          timestamp: now,
          narration: `Internal order ${orderId}`,
        });

        if (i % 9 !== 0) {
          // intentional missing bank credit on i%9
          bk.push({
            txn_id: `BK_${utr}`,
            order_id: orderId,
            reference_number: utr,
            amount: (i % 5 === 0 ? net - 50 : net).toString(), // intentional fee deduction variance
            currency: "INR",
            timestamp: now,
            narration: `NEFT credit UTR ${utr}`,
          });
        }
      }

      return controllerApi.ingestBatch({
        batch_id: batchId,
        gateway_records: gw,
        ledger_records: ld,
        bank_records: bk,
      });
    },
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries();
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="w-full max-w-lg rounded-lg border border-[#222634] bg-[#11131a] p-6 shadow-2xl text-zinc-100">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-sky-950/60 border border-sky-800/60 text-sky-400">
              <Database className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold font-mono text-zinc-100">Execute 3-Way Reconciliation Batch</h2>
              <p className="text-[11px] text-zinc-400">Triggers multi-source ingestion across Gateway, Ledger, and Bank feeds.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="py-4 space-y-4 text-xs">
          <div>
            <label className="block text-zinc-400 mb-1 font-mono text-[11px]">Batch Run Identifier</label>
            <input
              type="text"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-2 text-zinc-200 font-mono text-xs focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-zinc-400 mb-1 font-mono text-[11px]">Batch Size (Logical Transactions)</label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-2 text-zinc-200 font-mono text-xs focus:border-sky-500 focus:outline-hidden"
            >
              <option value={50}>50 Transactions (150 Multi-Source Records - Track 4 Standard)</option>
              <option value={100}>100 Transactions (300 Multi-Source Records)</option>
              <option value={200}>200 Transactions (600 Multi-Source Records)</option>
            </select>
          </div>

          {result && (() => {
            const processedCount = result.records_received ?? result.total_processed ?? 0;
            const matchesCount = (result.auto_matched_count !== undefined
              ? (result.auto_matched_count + (result.ml_recovered_count || 0))
              : result.matches_found) ?? 0;
            const exceptionsCount = result.unresolved_count ?? result.exceptions_detected ?? 0;
            const durationMs = result.processing_duration_ms;
            const durationSec = durationMs !== undefined ? durationMs / 1000 : result.duration_seconds;

            let throughputDisplay = "Duration: Unavailable";
            if (durationSec !== undefined && Number.isFinite(durationSec) && durationSec > 0) {
              const tps = processedCount / durationSec;
              throughputDisplay = `Throughput: ${Number.isFinite(tps) ? tps.toFixed(0) : "—"} records/sec (${durationSec.toFixed(3)}s)`;
            } else if (durationMs !== undefined && Number.isFinite(durationMs)) {
              throughputDisplay = `Processing Latency: ${durationMs.toFixed(1)}ms`;
            }

            return (
              <div className="p-3 rounded border border-emerald-800/60 bg-emerald-950/30 space-y-1.5">
                <div className="flex items-center gap-1.5 text-emerald-400 font-semibold font-mono">
                  <CheckCircle2 className="h-4 w-4" />
                  Batch Reconciled Successfully
                </div>
                <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
                  <div>Processed: <span className="text-zinc-100 font-bold">{processedCount}</span></div>
                  <div>Matches: <span className="text-emerald-300 font-bold">{matchesCount}</span></div>
                  <div>Exceptions: <span className="text-rose-400 font-bold">{exceptionsCount}</span></div>
                </div>
                <div className="text-[10px] text-zinc-400 font-mono">
                  {throughputDisplay}
                </div>
              </div>
            );
          })()}

          {runMutation.isError && (
            <div className="p-3 rounded border border-rose-800/60 bg-rose-950/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>{(runMutation.error as Error)?.message || "Failed to execute reconciliation batch."}</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-zinc-800 pt-3">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs font-medium text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            {result ? "Close" : "Cancel"}
          </button>
          <button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-semibold bg-sky-500 hover:bg-sky-400 text-black disabled:opacity-50 transition-colors"
          >
            {runMutation.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Reconciling...</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Start Ingestion & Reconciliation</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
