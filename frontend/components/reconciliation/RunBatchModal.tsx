"use client";

import React, { useState, useCallback } from "react";
import { X, Play, Loader2, Database, CheckCircle2, AlertTriangle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { BatchIngestResponse } from "@/types/controller";

interface RunBatchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Strictly mutually-exclusive run states
type RunState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "success"; data: BatchIngestResponse }
  | { phase: "error"; message: string };

function generateRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `run_${crypto.randomUUID()}`;
  }
  const timestamp = Date.now();
  const rand1 = Math.floor(Math.random() * 1000000).toString().padStart(6, "0");
  const rand2 = Math.floor(Math.random() * 1000000).toString().padStart(6, "0");
  return `run_${timestamp}_${rand1}_${rand2}`;
}

export function RunBatchModal({ isOpen, onClose }: RunBatchModalProps) {
  const queryClient = useQueryClient();
  const [batchSize, setBatchSize] = useState<number>(50);
  const [runState, setRunState] = useState<RunState>({ phase: "idle" });

  const isSubmitting = runState.phase === "submitting";

  const handleStartRun = useCallback(async () => {
    if (isSubmitting) return;

    setRunState({ phase: "submitting" });

    const n = Number(batchSize) || 50;
    const runId = generateRunId();

    const gw: Record<string, unknown>[] = [];
    const ld: Record<string, unknown>[] = [];
    const bk: Record<string, unknown>[] = [];

    const now = new Date();

    for (let i = 0; i < n; i++) {
      const txnId = `demo_txn_${runId}_${i + 1}`;
      const amount = 1000 + (i % 10) * 250;
      const orderId = `ord_demo_${runId}_${i + 1}`;
      const utr = `UTR_AXIS_${runId}_${i + 1}`;
      const isMismatch = i === 12 || i === 27;

      gw.push({
        id: `pay_${runId}_${i + 1}`,
        domain_transaction_id: txnId,
        order_id: orderId,
        amount: isMismatch ? amount + 120 : amount,
        currency: "INR",
        status: "captured",
        fee: 23.6,
        tax: 4.24,
        source: "gateway",
        timestamp: now.toISOString(),
      });

      ld.push({
        id: `led_${runId}_${i + 1}`,
        domain_transaction_id: txnId,
        order_id: orderId,
        amount: amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: now.toISOString(),
      });

      bk.push({
        id: `bnk_${runId}_${i + 1}`,
        domain_transaction_id: txnId,
        reference_number: utr,
        amount: isMismatch ? amount - 23.6 - 4.24 + 10 : amount - 23.6 - 4.24,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: now.toISOString(),
      });
    }

    try {
      const data = await controllerApi.ingestBatch({
        batch_id: runId,
        gateway_records: gw,
        ledger_records: ld,
        bank_records: bk,
      });

      setRunState({ phase: "success", data });
      queryClient.invalidateQueries();
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to execute reconciliation batch.";
      setRunState({ phase: "error", message });
    }
  }, [isSubmitting, batchSize, queryClient]);

  const handleClose = useCallback(() => {
    setRunState({ phase: "idle" });
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4">
      <div
        className="w-full max-w-lg rounded-sm border p-6 text-[#eceae6] shadow-2xl select-none"
        style={{
          borderColor: "var(--border-standard)",
          background: "var(--surface-1)",
        }}
      >
        {/* Modal Header */}
        <div
          className="flex items-center justify-between pb-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="p-1.5 rounded-sm border text-[#c9a96e]"
              style={{
                borderColor: "var(--accent-border)",
                background: "var(--accent-dim)",
              }}
            >
              <Database className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6]">
                Execute 3-Way Reconciliation Batch
              </h2>
              <p className="text-[10px] text-[#8e96a0]">
                Ingestion across Gateway, Ledger, and Core Banking feeds
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1 rounded text-[#8e96a0] hover:text-[#eceae6] transition-micro"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="py-4 space-y-4 text-xs">
          <div>
            <label className="block text-[#8e96a0] mb-1 text-[11px]">
              Evaluation Batch Size (Logical Transactions)
            </label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              disabled={isSubmitting}
              className="w-full rounded-sm border px-3 py-2 text-xs font-mono text-[#eceae6] transition-micro focus:outline-hidden disabled:opacity-50"
              style={{
                borderColor: "var(--border-standard)",
                background: "var(--surface-2)",
              }}
            >
              <option value={20}>N = 20 Transactions (Quick Micro-Verification)</option>
              <option value={50}>N = 50 Transactions (Official Track 4 Standard Bar)</option>
              <option value={100}>N = 100 Transactions (Extended Suite)</option>
            </select>
          </div>

          <div
            className="p-3.5 rounded-sm border text-[11px] leading-relaxed text-[#8e96a0]"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <strong className="text-[#eceae6]">Pipeline Execution:</strong> Generating {batchSize * 3} normalized feed records across Gateway, Ledger, and Bank. Deterministic matching runs first, followed by ML XGBoost arbitration and discrepancy routing.
          </div>

          {/* Success State */}
          {runState.phase === "success" && (() => {
            const d = runState.data;
            const autoMatched = d.auto_matched_count ?? 0;
            const mlRecovered = d.ml_recovered_count ?? 0;
            const totalMatched = autoMatched + mlRecovered;
            const unresolved = d.unresolved_count ?? 0;
            const recordsReceived = d.records_received ?? 0;
            const durationMs = d.processing_duration_ms;

            let throughputDisplay = "";
            if (typeof durationMs === "number" && Number.isFinite(durationMs) && durationMs > 0) {
              const durationSec = durationMs / 1000;
              const tps = recordsReceived > 0 && durationSec > 0
                ? recordsReceived / durationSec
                : null;
              throughputDisplay = tps !== null && Number.isFinite(tps)
                ? `Throughput: ${tps.toFixed(0)} rec/s (${durationSec.toFixed(3)}s)`
                : `Latency: ${durationMs.toFixed(1)}ms`;
            } else if (typeof durationMs === "number" && Number.isFinite(durationMs)) {
              throughputDisplay = `Processing Latency: ${durationMs.toFixed(1)}ms`;
            }

            return (
              <div
                className="p-4 rounded-sm border space-y-2"
                style={{
                  borderColor: "var(--matched-border)",
                  background: "var(--matched-bg)",
                }}
              >
                <div className="flex items-center gap-1.5 text-[#6ecba0] font-bold">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Batch Reconciled Successfully</span>
                </div>
                <div className="text-[10px] text-[#8e96a0]">Run ID: {d.run_id}</div>
                <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Feed Records</div>
                    <span className="text-[#eceae6] font-bold">{recordsReceived}</span>
                  </div>
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Matched</div>
                    <span className="text-[#6ecba0] font-bold">{totalMatched}</span>
                  </div>
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Exceptions</div>
                    <span className="text-[#e07070] font-bold">{unresolved}</span>
                  </div>
                </div>
                {throughputDisplay && (
                  <div className="text-[10px] text-[#8e96a0] pt-1">
                    {throughputDisplay}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Error State */}
          {runState.phase === "error" && (
            <div
              className="p-3.5 rounded-sm border text-xs flex items-center gap-2"
              style={{
                borderColor: "var(--variance-border)",
                background: "var(--variance-bg)",
                color: "var(--variance-text)",
              }}
            >
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>{runState.message}</span>
            </div>
          )}

          {/* Submitting State */}
          {runState.phase === "submitting" && (
            <div
              className="p-3.5 rounded-sm border text-xs flex items-center gap-2"
              style={{
                borderColor: "var(--border-standard)",
                background: "var(--surface-2)",
                color: "var(--text-secondary)",
              }}
            >
              <Loader2 className="h-4 w-4 animate-spin text-[#c9a96e] flex-shrink-0" />
              <span>Ingesting &amp; reconciling multi-source batch...</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div
          className="flex items-center justify-end gap-2 pt-4"
          style={{ borderTop: "1px solid var(--border-subtle)" }}
        >
          <button
            onClick={handleClose}
            className="px-3 py-1.5 rounded-sm text-xs font-semibold text-[#8e96a0] hover:text-[#eceae6] transition-micro"
          >
            {runState.phase === "success" ? "Close" : "Cancel"}
          </button>
          <button
            onClick={handleStartRun}
            disabled={isSubmitting}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-sm text-xs font-bold transition-micro disabled:opacity-50"
            style={{
              color: "var(--bg)",
              background: "var(--accent)",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--accent-hover)")}
            onMouseLeave={e => (e.currentTarget.style.background = "var(--accent)")}
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
