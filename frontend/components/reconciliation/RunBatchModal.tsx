"use client";

import React, { useState, useCallback } from "react";
import { X, Play, Loader2, CheckCircle2, AlertTriangle, Database } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { BatchIngestResponse } from "@/types/controller";

interface RunBatchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Collision-resistant ID for each new batch execution request.
// Uses crypto.randomUUID() when available (all modern browsers), falls back to
// a timestamp + random suffix that is unique enough for a UI session.
function generateRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `run_ui_${crypto.randomUUID()}`;
  }
  return `run_ui_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`;
}

// Explicit lifecycle states — only one can be active at a time.
type RunState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "success"; data: BatchIngestResponse }
  | { phase: "error"; message: string };

export function RunBatchModal({ isOpen, onClose }: RunBatchModalProps) {
  const queryClient = useQueryClient();

  // batchSize controls synthetic data generation; this persists across runs (UX convenience).
  const [batchSize, setBatchSize] = useState(50);

  // Single coherent lifecycle state — mutually exclusive by construction.
  const [runState, setRunState] = useState<RunState>({ phase: "idle" });

  // isSubmitting derived from lifecycle state — prevents double-submission at the handler level.
  const isSubmitting = runState.phase === "submitting";

  const handleStartRun = useCallback(async () => {
    // Guard: prevent concurrent submissions even if button becomes clickable via keyboard etc.
    if (isSubmitting) return;

    // Generate a fresh unique ID immediately before this execution — not at mount, not reused.
    const runId = generateRunId();

    // Transition: clear any previous result/error, enter submitting.
    setRunState({ phase: "submitting" });

    // Build synthetic 3-source batch from current batchSize.
    const gw: Array<Record<string, unknown>> = [];
    const ld: Array<Record<string, unknown>> = [];
    const bk: Array<Record<string, unknown>> = [];
    const now = new Date().toISOString();

    for (let i = 1; i <= batchSize; i++) {
      const orderId = `ORD_${runId.slice(-8)}_${i.toString().padStart(4, "0")}`;
      const payId = `PAY_${runId.slice(-8)}_${i.toString().padStart(4, "0")}`;
      const utr = `UTR_${runId.slice(-8)}_${i.toString().padStart(4, "0")}`;
      const amount = 5000 + i * 250;
      const fee = Number((amount * 0.02).toFixed(2));
      const tax = Number((fee * 0.18).toFixed(2));
      const net = amount - fee - tax;

      // 70% clean matches; 30% intentional discrepancies for exception generation.
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
        // Intentional amount mismatch on every 7th item.
        amount: (i % 7 === 0 ? amount + 100 : amount).toString(),
        currency: "INR",
        timestamp: now,
        narration: `Internal order ${orderId}`,
      });

      if (i % 9 !== 0) {
        // Intentional missing bank credit on every 9th item.
        bk.push({
          txn_id: `BK_${utr}`,
          order_id: orderId,
          reference_number: utr,
          // Intentional fee deduction variance on every 5th item.
          amount: (i % 5 === 0 ? net - 50 : net).toString(),
          currency: "INR",
          timestamp: now,
          narration: `NEFT credit UTR ${utr}`,
        });
      }
    }

    try {
      const data = await controllerApi.ingestBatch({
        batch_id: runId,
        gateway_records: gw,
        ledger_records: ld,
        bank_records: bk,
      });

      // On confirmed 2xx success: transition to success, store result.
      setRunState({ phase: "success", data });
      queryClient.invalidateQueries();
    } catch (err: unknown) {
      // On any error (4xx, 5xx, network): transition to error — never render success.
      const message =
        err instanceof Error
          ? err.message
          : "Failed to execute reconciliation batch.";
      setRunState({ phase: "error", message });
    }
  }, [isSubmitting, batchSize, queryClient]);

  // When the modal is closed: reset to idle so reopening starts fresh.
  const handleClose = useCallback(() => {
    setRunState({ phase: "idle" });
    onClose();
  }, [onClose]);

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
            onClick={handleClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="py-4 space-y-4 text-xs">
          {/* Batch Size Selector — only editable before run starts */}
          <div>
            <label className="block text-zinc-400 mb-1 font-mono text-[11px]">Batch Size (Logical Transactions)</label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              disabled={isSubmitting}
              className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-2 text-zinc-200 font-mono text-xs focus:border-sky-500 focus:outline-hidden disabled:opacity-50"
            >
              <option value={50}>50 Transactions (150 Multi-Source Records — Track 4 Standard)</option>
              <option value={100}>100 Transactions (300 Multi-Source Records)</option>
              <option value={200}>200 Transactions (600 Multi-Source Records)</option>
            </select>
          </div>

          {/* ── SUCCESS STATE — only rendered when phase === "success" ── */}
          {runState.phase === "success" && (() => {
            const d = runState.data;
            // Fields verified against BatchIngestResponse Pydantic schema:
            //   records_received — total raw records ingested across all 3 feeds
            //   auto_matched_count + ml_recovered_count — deterministic + ML matched
            //   unresolved_count — records that became exceptions
            //   processing_duration_ms — wall-clock ms from the backend
            const recordsReceived = d.records_received ?? 0;
            const autoMatched = d.auto_matched_count ?? 0;
            const mlRecovered = d.ml_recovered_count ?? 0;
            const totalMatched = autoMatched + mlRecovered;
            const unresolved = d.unresolved_count ?? 0;
            const durationMs = d.processing_duration_ms;

            let throughputDisplay = "Duration: Unavailable";
            if (typeof durationMs === "number" && Number.isFinite(durationMs) && durationMs > 0) {
              const durationSec = durationMs / 1000;
              const tps = recordsReceived > 0 && durationSec > 0
                ? recordsReceived / durationSec
                : null;
              throughputDisplay = tps !== null && Number.isFinite(tps)
                ? `Throughput: ${tps.toFixed(0)} records/sec (${durationSec.toFixed(3)}s)`
                : `Processing Latency: ${durationMs.toFixed(1)}ms`;
            } else if (typeof durationMs === "number" && Number.isFinite(durationMs)) {
              throughputDisplay = `Processing Latency: ${durationMs.toFixed(1)}ms`;
            }

            return (
              <div className="p-3 rounded border border-emerald-800/60 bg-emerald-950/30 space-y-1.5">
                <div className="flex items-center gap-1.5 text-emerald-400 font-semibold font-mono">
                  <CheckCircle2 className="h-4 w-4" />
                  Batch Reconciled Successfully
                </div>
                <div className="text-[10px] text-zinc-500 font-mono">Run: {d.run_id}</div>
                <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase mb-0.5">Feed Records</div>
                    <span className="text-zinc-100 font-bold">{recordsReceived}</span>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase mb-0.5">Matched</div>
                    <span className="text-emerald-300 font-bold">{totalMatched}</span>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase mb-0.5">Exceptions</div>
                    <span className="text-rose-400 font-bold">{unresolved}</span>
                  </div>
                </div>
                <div className="text-[10px] text-zinc-400 font-mono pt-1">
                  {throughputDisplay}
                </div>
              </div>
            );
          })()}

          {/* ── ERROR STATE — only rendered when phase === "error" ── */}
          {runState.phase === "error" && (
            <div className="p-3 rounded border border-rose-800/60 bg-rose-950/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>{runState.message}</span>
            </div>
          )}

          {/* ── SUBMITTING INDICATOR — only rendered when phase === "submitting" ── */}
          {runState.phase === "submitting" && (
            <div className="p-3 rounded border border-sky-800/40 bg-sky-950/20 text-sky-300 text-xs flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
              <span>Reconciliation in progress — please wait…</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-zinc-800 pt-3">
          <button
            onClick={handleClose}
            className="px-3 py-1.5 rounded text-xs font-medium text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            {runState.phase === "success" ? "Close" : "Cancel"}
          </button>
          <button
            onClick={handleStartRun}
            disabled={isSubmitting}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-semibold bg-sky-500 hover:bg-sky-400 text-black disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Reconciling…</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Start Ingestion &amp; Reconciliation</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
