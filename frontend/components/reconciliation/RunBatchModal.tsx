"use client";

import React, { useState, useCallback, useRef } from "react";
import {
  X,
  Play,
  Loader2,
  Database,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  UploadCloud,
  FileSpreadsheet,
  Check,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { BatchIngestResponse } from "@/types/controller";

interface RunBatchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type RunState =
  | { phase: "idle" }
  | { phase: "submitting"; stage: string }
  | { phase: "success"; data: BatchIngestResponse }
  | { phase: "error"; message: string; detail?: string };

type ActiveTab = "demo" | "import";

function generateRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `run_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
  }
  return `run_${Date.now().toString(36)}`;
}

/**
 * Deterministic per-run PRNG (mulberry32) seeded from the run ID, so amounts
 * vary run-to-run and record-to-record instead of cycling through a fixed
 * lookup table (which made exception exposure values look suspiciously
 * repetitive — the same handful of amounts appearing dozens of times).
 */
function seededRng(seedStr: string): () => number {
  let h = 1779033703 ^ seedStr.length;
  for (let i = 0; i < seedStr.length; i++) {
    h = Math.imul(h ^ seedStr.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Realistic INR transaction amount: log-uniform so small payments are common
 * and large ones rare, rounded to a plausible paise value — never a fixed
 * lookup value, so exposure amounts across a batch are naturally diverse. */
function realisticAmount(rand: () => number): number {
  const logMin = Math.log(499);
  const logMax = Math.log(249999);
  const raw = Math.exp(logMin + rand() * (logMax - logMin));
  return Math.round(raw * 100) / 100;
}

/**
 * Build a diverse set of feed records using the same scenario patterns as
 * simulator/scenarios.py — clean matches, fee mismatches, delayed settlements,
 * ambiguous matches, duplicates, wrong references, partial refunds, missing bank credits.
 *
 * Each logical transaction produces 3 feed records (gateway, ledger, bank).
 * N logical transactions → 3N feed records.
 */
function buildDiverseBatch(
  n: number,
  runId: string
): {
  gateway_records: Record<string, unknown>[];
  ledger_records: Record<string, unknown>[];
  bank_records: Record<string, unknown>[];
} {
  const gw: Record<string, unknown>[] = [];
  const ld: Record<string, unknown>[] = [];
  const bk: Record<string, unknown>[] = [];

  const now = new Date();
  const MDR = 0.02;
  const GST = 0.18;

  const fee = (amount: number) => parseFloat((amount * MDR).toFixed(2));
  const tax = (amount: number) => parseFloat((fee(amount) * GST).toFixed(2));
  const net = (amount: number) => parseFloat((amount - fee(amount) - tax(amount)).toFixed(2));
  const rand = seededRng(runId);

  // Scenario assignment — diverse exception/edge scenarios at specific positions,
  // remaining are clean deterministic matches.
  const SCENARIO_MAP: Record<number, string> = {
    0: "fee_mismatch", // index 0: Fee variance
    1: "fee_mismatch", // index 1: Fee variance
    2: "delayed", // index 2: Delayed settlement (timing diff)
    3: "delayed", // index 3: Delayed settlement
    4: "ambiguous", // index 4: ML recovered candidate
    5: "duplicate", // index 5: Duplicate capture
    6: "wrong_reference", // index 6: Corrupted order ID
    7: "partial_refund", // index 7: Partial refund
    8: "missing_bank", // index 8: Gateway & ledger exist, bank credit pending
    9: "missing_ledger", // index 9: Gateway & bank exist, ledger missing
  };

  for (let i = 0; i < n; i++) {
    const scenario = SCENARIO_MAP[i] ?? "normal";
    const logicalId = `demo_${runId}_${String(i + 1).padStart(3, "0")}`;
    const gwId = `pay_${logicalId}`;
    const ldId = `ord_${logicalId}`;
    const bkId = `bnk_${logicalId}`;
    const amount = realisticAmount(rand);
    const utr = `UTR_AXIS_${logicalId}`;
    const ts = new Date(now.getTime() - (n - i) * 3600000).toISOString();

    if (scenario === "fee_mismatch") {
      // Gateway charges 3% MDR instead of 2% — fee discrepancy exception
      const obsFee = parseFloat((amount * 0.03).toFixed(2));
      const obsTax = parseFloat((obsFee * GST).toFixed(2));
      const obsNet = parseFloat((amount - obsFee - obsTax).toFixed(2));
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: utr,
        amount,
        currency: "INR",
        status: "captured",
        fee: obsFee,
        tax: obsTax,
        source: "gateway",
        timestamp: ts,
      });
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: utr,
        amount: obsNet,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: ts,
      });
    } else if (scenario === "delayed") {
      // Settlement arrives 5 days late — ML recoverable timing case
      const f = fee(amount);
      const t = tax(amount);
      const n_ = net(amount);
      const delayed = new Date(now.getTime() + 5 * 86400000).toISOString();
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: utr,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: delayed,
      });
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: utr,
        amount: n_,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: delayed,
      });
    } else if (scenario === "ambiguous") {
      // Direct Ledger-Bank reconciliation via ML Candidate Recovery (gateway unmapped/missing reference)
      const tsBank = new Date(new Date(ts).getTime() + 86400000).toISOString();
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: logicalId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: `UTR_${logicalId}`,
        narration: `SETTLEMENT ${logicalId} ${ldId}`,
        amount,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: tsBank,
      });
    } else if (scenario === "duplicate") {
      // Duplicate entry — same payment recorded twice
      const f = fee(amount);
      const t = tax(amount);
      const n_ = net(amount);
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: utr,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: ts,
      });
      ld.push({
        txn_id: `${ldId}_DUP`,
        id: `${ldId}_DUP`,
        domain_transaction_id: `${logicalId}_DUP`,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: utr,
        amount: n_,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: ts,
      });
    } else if (scenario === "wrong_reference") {
      // Corrupted order_id across sources
      const f = fee(amount);
      const t = tax(amount);
      const n_ = net(amount);
      const corruptedOrder = `${ldId}_ERR`;
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: corruptedOrder,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: ts,
      });
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: `${utr}_ERR`,
        amount: n_,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: ts,
      });
    } else if (scenario === "partial_refund") {
      // Partial refund — 30% refunded
      const refund = parseFloat((amount * 0.3).toFixed(2));
      const f = fee(amount);
      const t = tax(amount);
      const n_ = parseFloat((amount - f - t - refund).toFixed(2));
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: utr,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: ts,
      });
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "PARTIALLY_REFUNDED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: utr,
        amount: n_,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: ts,
      });
    } else if (scenario === "missing_bank") {
      // Bank credit missing / pending settlement
      const f = fee(amount);
      const t = tax(amount);
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: ts,
      });
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      // No bank entry created
    } else if (scenario === "missing_ledger") {
      // Captured at gateway and credited at bank, but missing internal ledger entry
      const f = fee(amount);
      const t = tax(amount);
      const n_ = net(amount);
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: utr,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: utr,
        amount: n_,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: ts,
      });
      // No ledger entry created
    } else {
      // Normal clean deterministic match
      const f = fee(amount);
      const t = tax(amount);
      const n_ = net(amount);
      gw.push({
        txn_id: gwId,
        id: gwId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        reference_number: utr,
        amount,
        currency: "INR",
        status: "captured",
        fee: f,
        tax: t,
        source: "gateway",
        timestamp: ts,
      });
      ld.push({
        txn_id: ldId,
        id: ldId,
        domain_transaction_id: logicalId,
        order_id: ldId,
        amount,
        currency: "INR",
        status: "COMPLETED",
        source: "ledger",
        timestamp: ts,
      });
      bk.push({
        txn_id: bkId,
        id: bkId,
        domain_transaction_id: logicalId,
        reference_number: utr,
        amount: n_,
        currency: "INR",
        status: "CREDIT",
        source: "bank",
        timestamp: ts,
      });
    }
  }

  return { gateway_records: gw, ledger_records: ld, bank_records: bk };
}

interface ParsedFileStats {
  gateway: number;
  ledger: number;
  bank: number;
  fileName: string;
}

export function RunBatchModal({ isOpen, onClose }: RunBatchModalProps) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<ActiveTab>("demo");
  const [runState, setRunState] = useState<RunState>({ phase: "idle" });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showErrorDetail, setShowErrorDetail] = useState(false);
  const [batchSize, setBatchSize] = useState<number>(50);
  const [customRunId, setCustomRunId] = useState<string>("");

  // CSV Import State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [parsedFiles, setParsedFiles] = useState<{
    gw: Record<string, unknown>[];
    ld: Record<string, unknown>[];
    bk: Record<string, unknown>[];
    stats?: ParsedFileStats;
  }>({ gw: [], ld: [], bk: [] });
  const [importError, setImportError] = useState<string | null>(null);

  const isSubmitting = runState.phase === "submitting";

  // Parse CSV file content
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportError(null);
    const reader = new FileReader();

    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
        if (lines.length < 2) {
          setImportError("CSV file must contain a header row and at least one data row.");
          return;
        }

        const headers = lines[0].split(",").map((h) => h.trim().toLowerCase().replace(/['"]+/g, ""));
        const rows: Record<string, string>[] = [];
        for (let i = 1; i < lines.length; i++) {
          const vals = lines[i].split(",").map((v) => v.trim().replace(/['"]+/g, ""));
          const rowObj: Record<string, string> = {};
          headers.forEach((h, idx) => {
            rowObj[h] = vals[idx] ?? "";
          });
          rows.push(rowObj);
        }

        // Determine feed type from headers
        const isGateway = headers.includes("gross_amount") || headers.includes("settlement_id") || headers.includes("fee");
        const isLedger = headers.includes("customer_id") || headers.includes("transaction_amount") || headers.includes("payment_status");
        const isBank = headers.includes("bank_transaction_id") || headers.includes("credit_amount") || headers.includes("debit_amount");

        const nowIso = new Date().toISOString();

        if (isGateway) {
          const gwRecords = rows.map((r, i) => ({
            txn_id: r.transaction_id || r.txn_id || `gw_csv_${i + 1}`,
            id: r.transaction_id || r.txn_id || `gw_csv_${i + 1}`,
            order_id: r.order_id || undefined,
            amount: parseFloat(r.gross_amount || r.amount || "0"),
            currency: r.currency || "INR",
            status: r.status || "captured",
            fee: r.fee ? parseFloat(r.fee) : 0,
            tax: r.tax ? parseFloat(r.tax) : 0,
            source: "gateway",
            timestamp: r.settlement_date || r.timestamp || nowIso,
          }));
          setParsedFiles((prev) => ({
            ...prev,
            gw: gwRecords,
            stats: {
              gateway: gwRecords.length,
              ledger: prev.ld.length,
              bank: prev.bk.length,
              fileName: file.name,
            },
          }));
        } else if (isLedger) {
          const ldRecords = rows.map((r, i) => ({
            txn_id: r.order_id || r.txn_id || `ld_csv_${i + 1}`,
            id: r.order_id || r.txn_id || `ld_csv_${i + 1}`,
            order_id: r.order_id || undefined,
            amount: parseFloat(r.transaction_amount || r.amount || "0"),
            currency: r.currency || "INR",
            status: r.payment_status || "COMPLETED",
            source: "ledger",
            timestamp: r.order_date || r.timestamp || nowIso,
          }));
          setParsedFiles((prev) => ({
            ...prev,
            ld: ldRecords,
            stats: {
              gateway: prev.gw.length,
              ledger: ldRecords.length,
              bank: prev.bk.length,
              fileName: file.name,
            },
          }));
        } else if (isBank) {
          const bkRecords = rows.map((r, i) => {
            const credit = parseFloat(r.credit_amount || "0");
            const debit = parseFloat(r.debit_amount || "0");
            const amt = credit > 0 ? credit : debit > 0 ? debit : parseFloat(r.amount || "0");
            return {
              txn_id: r.bank_transaction_id || r.txn_id || `bk_csv_${i + 1}`,
              id: r.bank_transaction_id || r.txn_id || `bk_csv_${i + 1}`,
              reference_number: r.utr || r.reference_number || undefined,
              amount: amt,
              currency: r.currency || "INR",
              status: credit > 0 ? "CREDIT" : "DEBIT",
              source: "bank",
              timestamp: r.value_date || r.timestamp || nowIso,
            };
          });
          setParsedFiles((prev) => ({
            ...prev,
            bk: bkRecords,
            stats: {
              gateway: prev.gw.length,
              ledger: prev.ld.length,
              bank: bkRecords.length,
              fileName: file.name,
            },
          }));
        } else {
          // Generic CSV: Treat as gateway feed
          const genericRecords = rows.map((r, i) => ({
            txn_id: r.txn_id || r.id || r.transaction_id || `rec_${i + 1}`,
            id: r.txn_id || r.id || r.transaction_id || `rec_${i + 1}`,
            order_id: r.order_id || undefined,
            reference_number: r.utr || r.reference_number || undefined,
            amount: parseFloat(r.amount || r.gross_amount || "0"),
            currency: r.currency || "INR",
            status: r.status || "captured",
            source: r.source || "gateway",
            timestamp: r.timestamp || r.date || nowIso,
          }));
          setParsedFiles((prev) => ({
            ...prev,
            gw: genericRecords,
            stats: {
              gateway: genericRecords.length,
              ledger: prev.ld.length,
              bank: prev.bk.length,
              fileName: file.name,
            },
          }));
        }
      } catch (err) {
        setImportError(`Failed to parse CSV: ${err instanceof Error ? err.message : String(err)}`);
      }
    };
    reader.readAsText(file);
  };

  const handleStartRun = useCallback(async () => {
    if (isSubmitting) return;
    setRunState({ phase: "submitting", stage: "Ingesting multi-source feeds..." });
    setShowErrorDetail(false);

    const runId = customRunId.trim() || generateRunId();

    let gwRecords: Record<string, unknown>[] = [];
    let ldRecords: Record<string, unknown>[] = [];
    let bkRecords: Record<string, unknown>[] = [];

    if (activeTab === "import" && (parsedFiles.gw.length > 0 || parsedFiles.ld.length > 0 || parsedFiles.bk.length > 0)) {
      gwRecords = parsedFiles.gw;
      ldRecords = parsedFiles.ld;
      bkRecords = parsedFiles.bk;
    } else {
      const n = Number(batchSize) || 50;
      const batch = buildDiverseBatch(n, runId);
      gwRecords = batch.gateway_records;
      ldRecords = batch.ledger_records;
      bkRecords = batch.bank_records;
    }

    try {
      setRunState({ phase: "submitting", stage: "Executing 3-way reconciliation engine..." });
      const data = await controllerApi.ingestBatch({
        batch_id: runId,
        gateway_records: gwRecords,
        ledger_records: ldRecords,
        bank_records: bkRecords,
      });

      setRunState({ phase: "success", data });
      // Invalidate queries so Command Center, exceptions, runs, audit all update atomically
      queryClient.invalidateQueries();
    } catch (err: unknown) {
      let message = "Reconciliation could not start. The request was rejected by the service.";
      let detail: string | undefined;
      if (err instanceof Error) {
        if (err.message.includes("422") || err.message.toLowerCase().includes("validation")) {
          message = "Reconciliation request validation error. Field types or required values were rejected.";
        } else if (err.message.includes("500")) {
          message = "Reconciliation could not complete due to an internal service exception.";
        }
        detail = err.message;
      }
      setRunState({ phase: "error", message, detail });
    }
  }, [isSubmitting, customRunId, activeTab, parsedFiles, batchSize, queryClient]);

  const handleClose = useCallback(() => {
    setRunState({ phase: "idle" });
    setShowAdvanced(false);
    setShowErrorDetail(false);
    setParsedFiles({ gw: [], ld: [], bk: [] });
    setImportError(null);
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  const demoLogicalTxns = batchSize;
  const demoFeedRecords = batchSize * 3;

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
                Run reconciliation
              </h2>
              <p className="text-[10px] text-[#8e96a0]">
                Reconcile records across Gateway, Ledger, and Bank feeds
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

        {/* Modal Tabs */}
        {runState.phase === "idle" && (
          <div className="flex items-center border-b border-[#22272e] pt-3">
            <button
              onClick={() => setActiveTab("demo")}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-micro ${
                activeTab === "demo"
                  ? "border-[#c9a96e] text-[#eceae6]"
                  : "border-transparent text-[#8e96a0] hover:text-[#eceae6]"
              }`}
            >
              <Database className="h-3.5 w-3.5" />
              Use demo data
            </button>
            <button
              onClick={() => setActiveTab("import")}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-micro ${
                activeTab === "import"
                  ? "border-[#c9a96e] text-[#eceae6]"
                  : "border-transparent text-[#8e96a0] hover:text-[#eceae6]"
              }`}
            >
              <UploadCloud className="h-3.5 w-3.5" />
              Import your files
            </button>
          </div>
        )}

        {/* Modal Body */}
        <div className="py-4 space-y-4 text-xs">
          {runState.phase === "idle" && activeTab === "demo" && (
            <div className="space-y-3">
              <div
                className="p-3.5 rounded-sm border text-[11px] leading-relaxed text-[#8e96a0]"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--surface-2)",
                }}
              >
                Reconcile a balanced financial dataset of <strong className="text-[#eceae6]">50 logical transactions (150 multi-source feed records)</strong> across Gateway, Ledger, and Bank feeds. Exercises clean matches, fee discrepancies, delayed settlements, duplicate captures, and ambiguous matches.
              </div>

              {/* Advanced Options Toggle */}
              <div>
                <button
                  onClick={() => setShowAdvanced((v) => !v)}
                  className="flex items-center gap-1.5 text-[11px] text-[#8e96a0] hover:text-[#c9a96e] transition-micro font-mono"
                >
                  {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  Advanced options
                </button>

                {showAdvanced && (
                  <div
                    className="mt-2 p-3.5 rounded-sm border space-y-3 text-[11px]"
                    style={{
                      borderColor: "var(--border-subtle)",
                      background: "var(--surface-2)",
                    }}
                  >
                    <div>
                      <label className="block text-[#8e96a0] mb-1 text-[10px] uppercase font-semibold tracking-wider">
                        Logical Transactions
                      </label>
                      <select
                        value={batchSize}
                        onChange={(e) => setBatchSize(Number(e.target.value))}
                        disabled={isSubmitting}
                        className="w-full rounded-sm border px-3 py-1.5 text-xs font-mono text-[#eceae6] transition-micro disabled:opacity-50"
                        style={{
                          borderColor: "var(--border-standard)",
                          background: "var(--surface-1)",
                        }}
                      >
                        <option value={20}>20 logical transactions · 60 feed records</option>
                        <option value={50}>50 logical transactions · 150 feed records (Recommended)</option>
                        <option value={100}>100 logical transactions · 300 feed records</option>
                      </select>
                      <p className="mt-1 text-[10px] text-[#545e6a]">
                        Each logical transaction generates 3 feed records (Gateway + Ledger + Bank).
                      </p>
                    </div>

                    <div>
                      <label className="block text-[#8e96a0] mb-1 text-[10px] uppercase font-semibold tracking-wider">
                        Custom Batch Identifier (Optional)
                      </label>
                      <input
                        type="text"
                        value={customRunId}
                        onChange={(e) => setCustomRunId(e.target.value)}
                        placeholder="Leave blank to auto-generate"
                        className="w-full rounded-sm border px-3 py-1.5 text-xs font-mono text-[#eceae6] transition-micro"
                        style={{
                          borderColor: "var(--border-standard)",
                          background: "var(--surface-1)",
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {runState.phase === "idle" && activeTab === "import" && (
            <div className="space-y-3">
              <div
                className="p-3.5 rounded-sm border text-[11px] leading-relaxed text-[#8e96a0]"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--surface-2)",
                }}
              >
                Upload statement CSVs for Gateway, Ledger, or Bank feeds. Supported formats match standard institution settlement exports.
              </div>

              {/* Upload Dropzone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-[#343b44] hover:border-[#c9a96e] rounded-sm p-6 text-center cursor-pointer transition-colors bg-[#111418]"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".csv"
                  className="hidden"
                />
                <FileSpreadsheet className="h-8 w-8 text-[#8e96a0] mx-auto mb-2" />
                <p className="text-xs font-semibold text-[#eceae6]">
                  Click to select CSV Statement file
                </p>
                <p className="text-[10px] text-[#8e96a0] mt-1">
                  Supports Gateway, Ledger, or Bank CSV exports
                </p>
              </div>

              {/* Parsed Stats Preview */}
              {parsedFiles.stats && (
                <div className="p-3 rounded-sm border border-[#2a3038] bg-[#161a1f] space-y-1.5 font-mono text-[11px]">
                  <div className="flex items-center justify-between text-[#6ecba0] font-semibold">
                    <span className="flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5" /> File Loaded: {parsedFiles.stats.fileName}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-1 text-[10px] text-[#8e96a0]">
                    <div>Gateway: <strong className="text-[#eceae6]">{parsedFiles.gw.length}</strong></div>
                    <div>Ledger: <strong className="text-[#eceae6]">{parsedFiles.ld.length}</strong></div>
                    <div>Bank: <strong className="text-[#eceae6]">{parsedFiles.bk.length}</strong></div>
                  </div>
                </div>
              )}

              {importError && (
                <div className="p-2.5 rounded-sm border border-[#6b2a2a] bg-[#2a1313] text-[#e07070] text-[11px] flex items-center gap-2">
                  <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                  <span>{importError}</span>
                </div>
              )}
            </div>
          )}

          {/* Success State */}
          {runState.phase === "success" && (() => {
            const d = runState.data;
            const autoMatched = d.auto_matched_count ?? 0;
            const mlRecovered = d.ml_recovered_count ?? 0;
            const totalMatched = autoMatched + mlRecovered;
            const unresolved = d.unresolved_count ?? 0;
            const feedRecords = d.records_received ?? 0;
            const logicalTxns = Math.round(feedRecords / 3) || demoLogicalTxns;
            const durationMs = d.processing_duration_ms;

            let throughputDisplay = "";
            if (typeof durationMs === "number" && Number.isFinite(durationMs) && durationMs > 0) {
              const durationSec = durationMs / 1000;
              const tps = feedRecords > 0 ? feedRecords / durationSec : null;
              throughputDisplay =
                tps !== null && Number.isFinite(tps)
                  ? `${tps.toFixed(0)} feed records/s · ${durationSec.toFixed(2)}s`
                  : `${durationMs.toFixed(0)}ms`;
            }

            return (
              <div
                className="p-4 rounded-sm border space-y-3"
                style={{
                  borderColor: "var(--matched-border)",
                  background: "var(--matched-bg)",
                }}
              >
                <div className="flex items-center gap-1.5 text-[#6ecba0] font-bold text-xs">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Reconciliation complete · Authoritative state persisted</span>
                </div>
                <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Logical Transactions</div>
                    <span className="text-[#eceae6] font-bold">{logicalTxns}</span>
                  </div>
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Feed Records Ingested</div>
                    <span className="text-[#eceae6] font-bold">{feedRecords}</span>
                  </div>
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Total Matched</div>
                    <span className="text-[#6ecba0] font-bold">{totalMatched}</span>
                  </div>
                  <div>
                    <div className="text-[#8e96a0] text-[10px] uppercase mb-0.5">Open Exceptions</div>
                    <span className="text-[#e07070] font-bold">{unresolved}</span>
                  </div>
                </div>
                {throughputDisplay && (
                  <div className="text-[10px] text-[#8e96a0] font-mono pt-1">
                    Throughput: {throughputDisplay}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Error State */}
          {runState.phase === "error" && (
            <div
              className="rounded-sm border overflow-hidden"
              style={{
                borderColor: "var(--variance-border)",
              }}
            >
              <div
                className="p-3.5 flex items-start gap-2 text-xs"
                style={{
                  background: "var(--variance-bg)",
                  color: "var(--variance-text)",
                }}
              >
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-px" />
                <div className="space-y-1.5 flex-1 min-w-0">
                  <p className="font-semibold">{runState.message}</p>
                  {runState.detail && (
                    <button
                      onClick={() => setShowErrorDetail((v) => !v)}
                      className="flex items-center gap-1 text-[10px] font-mono opacity-70 hover:opacity-100"
                    >
                      {showErrorDetail ? <ChevronUp className="h-2.5 w-2.5" /> : <ChevronDown className="h-2.5 w-2.5" />}
                      Technical details
                    </button>
                  )}
                  {showErrorDetail && runState.detail && (
                    <pre
                      className="text-[10px] font-mono p-2 rounded-xs overflow-x-auto whitespace-pre-wrap break-all"
                      style={{ background: "rgba(0,0,0,0.15)" }}
                    >
                      {runState.detail}
                    </pre>
                  )}
                </div>
              </div>
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
              <span>{runState.stage}</span>
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

          {runState.phase !== "success" && (
            <button
              onClick={handleStartRun}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-sm text-xs font-bold transition-micro disabled:opacity-50"
              style={{
                color: "var(--bg)",
                background: "var(--accent)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Reconciling…</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>
                    {runState.phase === "error"
                      ? "Try again"
                      : activeTab === "import"
                      ? "Reconcile imported files"
                      : "Run reconciliation"}
                  </span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
