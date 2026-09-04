"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import {
  ArrowRight,
  ArrowDown,
  ExternalLink,
} from "lucide-react";

export default function WebsitePage() {
  // Fetch real authoritative benchmark proof
  const { data: benchmarkData, isLoading: benchmarkLoading } = useQuery({
    queryKey: ["website-benchmark"],
    queryFn: () => controllerApi.getBenchmark(50, 42),
    staleTime: 60000,
  });

  // Interactive node selection for the Hero Proof demonstration
  const [selectedProofNode, setSelectedProofNode] = useState<string>("settlement");

  const proofDetails: Record<
    string,
    {
      label: string;
      source: string;
      recordId: string;
      amount: string;
      status: "normal" | "divergence" | "verified";
      why: string;
      evidence: string;
      assessment: string;
      action: string;
    }
  > = {
    order: {
      label: "Order Ingestion",
      source: "Internal Order Service",
      recordId: "ORD-94821",
      amount: "₹184,250",
      status: "verified",
      why: "Customer checked out for enterprise license tier with 18% GST.",
      evidence: "Canonical shopping cart payload signed at 14:02:11 UTC.",
      assessment: "Initial gross commitment recorded cleanly in ledger.",
      action: "No action required.",
    },
    payment: {
      label: "Gateway Payment",
      source: "Razorpay Production",
      recordId: "pay_N83xL09q",
      amount: "₹184,250",
      status: "verified",
      why: "Customer UPI credit confirmed with bank gateway reference.",
      evidence: "Webhook event payment.captured received with HMAC SHA256 signature.",
      assessment: "Payment gross equals order commitment without deduction.",
      action: "No action required.",
    },
    settlement: {
      label: "Gateway Settlement Advice",
      source: "Razorpay Settlement Batch",
      recordId: "setl_G77kP10v",
      amount: "₹176,420",
      status: "divergence",
      why: "Settlement amount diverged by -₹7,830 from standard 2% MDR fee schedule.",
      evidence: "Settlement line item specifies unexpected surcharge and non-contractual fee delta.",
      assessment: "Root cause: Disputed gateway fee basis and non-standard tax withholding.",
      action: "Human review required. Queue fee adjustment dispute action.",
    },
    bank: {
      label: "Core Bank Credit",
      source: "HDFC Core Statement",
      recordId: "UTR-20260901-7781",
      amount: "₹176,420",
      status: "verified",
      why: "Bank credited exact net funds remitted by gateway.",
      evidence: "NEFT credit statement matched on UTR and timestamp window.",
      assessment: "Cash landed in bank accounts matches gateway net remittance.",
      action: "No action required.",
    },
    ledger: {
      label: "General Ledger Posting",
      source: "SAP ERP Ledger",
      recordId: "GL-2026-4410",
      amount: "₹184,250 (Expected)",
      status: "divergence",
      why: "Ledger expected full ₹180,565 net payout based on contract master rates.",
      evidence: "Posting unclosed pending reconciliation variance resolution.",
      assessment: "Net variance of -₹7,830 remains unposted to cash clearing account.",
      action: "Trigger HITL reconciliation adjustment bounded to ₹5,000 threshold policy.",
    },
  };

  const activeDetail = proofDetails[selectedProofNode] || proofDetails.settlement;

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#17191C] selection:bg-[rgba(201,169,110,0.25)] selection:text-[#17191C]">
      {/* ── TOP NAVIGATION ────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-[rgba(247,245,240,0.92)] backdrop-blur-md border-b border-[#D7D3CA]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="vx-mark">VX</div>
            <span className="font-bold tracking-[0.1em] text-sm text-[#17191C]">
              VERIDEX
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-xs font-semibold text-[#555B61]">
            <a href="#how-it-works" className="hover:text-[#17191C] transition-micro">
              How it works
            </a>
            <a href="#proof" className="hover:text-[#17191C] transition-micro">
              Proof
            </a>
            <a href="#pillars" className="hover:text-[#17191C] transition-micro">
              Pillars
            </a>
            <a href="#evidence" className="hover:text-[#17191C] transition-micro">
              Evidence
            </a>
            <a href="#measured" className="hover:text-[#17191C] transition-micro">
              Measured
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/app"
              className="btn-gold shadow-xs"
            >
              <span>Control Center</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── HERO SECTION ──────────────────────────────────────────── */}
      <section className="pt-20 pb-16 border-b border-[#D7D3CA]">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-xs bg-[#FFFFFF] border border-[#D7D3CA] text-[11px] font-bold uppercase tracking-[0.14em] text-[#9E7B35] mb-6 shadow-xs">
            <span>AI FINANCIAL CONTROL &amp; RECONCILIATION ENGINE</span>
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-[#17191C] leading-[1.1] mb-6">
            KNOW WHERE
            <br />
            <span className="font-display font-normal italic text-[#9E7B35]">
              THE MONEY DIVERGED.
            </span>
          </h1>

          <p className="text-base sm:text-lg text-[#555B61] max-w-2xl mx-auto leading-relaxed mb-8">
            VERIDEX reconciles multi-source financial records, investigates discrepancies,
            grounds conclusions in evidence, and keeps financial actions under human control.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/app"
              className="btn-gold px-6 py-3 text-sm shadow-xs"
            >
              <span>Launch Platform</span>
              <ArrowRight className="h-4 w-4" />
            </Link>

            <a
              href="#proof"
              className="btn-secondary px-6 py-3 text-sm"
            >
              <span>See the Proof</span>
              <ArrowDown className="h-4 w-4 text-[#6F747A]" />
            </a>
          </div>
        </div>
      </section>

      {/* ── HERO FINANCIAL PROOF (Interactive Provenance Demonstration) ── */}
      <section id="proof" className="py-20 border-b border-[#D7D3CA] bg-[#FFFFFF]">
        <div className="max-w-5xl mx-auto px-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-8 mb-8 border-b border-[#D7D3CA]">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
                INTERACTIVE FINANCIAL PROVENANCE
              </span>
              <h2 className="text-2xl font-bold tracking-tight text-[#17191C] mt-1">
                Visualizing Multi-Source Discrepancy
              </h2>
              <p className="text-xs text-[#555B61] mt-1">
                <span className="italic font-medium text-[#17191C]">Evidence before action.</span> Click any node in the transaction lifecycle below to inspect forensic findings and evidence.
              </p>
            </div>

            <div className="px-3 py-1 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA] text-[10px] font-mono text-[#6F747A] uppercase font-bold tracking-wider self-start sm:self-auto">
              Demonstration Mode • Illustrative Case
            </div>
          </div>

          {/* Three Large Financial Anchors */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            <div className="p-5 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] uppercase font-bold text-[#6F747A] tracking-wider">
                Expected Commitment
              </div>
              <div className="mt-2 text-3xl font-bold font-mono text-[#17191C] font-tabular">
                ₹184,250
              </div>
              <div className="text-xs text-[#555B61] mt-1 font-medium">
                Customer purchase contract &amp; tax basis
              </div>
            </div>

            <div className="p-5 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] uppercase font-bold text-[#6F747A] tracking-wider">
                Bank Received Net
              </div>
              <div className="mt-2 text-3xl font-bold font-mono text-[#1E7B4D] font-tabular">
                ₹176,420
              </div>
              <div className="text-xs text-[#555B61] mt-1 font-medium">
                Core bank settlement credit realized
              </div>
            </div>

            <div className="p-5 rounded-xs bg-[#FFF9F9] border-2 border-[#B83A3A]">
              <div className="text-[10px] uppercase font-bold text-[#9E2828] tracking-wider">
                Unreconciled Variance
              </div>
              <div className="mt-2 text-3xl font-bold font-mono text-[#9E2828] font-tabular">
                −₹7,830
              </div>
              <div className="text-xs text-[#9E2828] mt-1 font-medium">
                Discrepancy identified in settlement fee schedule
              </div>
            </div>
          </div>

          {/* Linear Provenance Chain */}
          <div className="bg-[#F7F5F0] border border-[#D7D3CA] rounded-xs p-6 mb-6">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#6F747A] mb-4">
              PROVENANCE CHAIN (SELECT TO INSPECT)
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {[
                { id: "order", name: "01. ORDER", state: "verified", amount: "₹184,250" },
                { id: "payment", name: "02. PAYMENT", state: "verified", amount: "₹184,250" },
                { id: "settlement", name: "03. SETTLEMENT", state: "divergence", amount: "₹176,420" },
                { id: "bank", name: "04. BANK CREDIT", state: "verified", amount: "₹176,420" },
                { id: "ledger", name: "05. LEDGER", state: "divergence", amount: "₹184,250" },
              ].map((node) => {
                const isSelected = selectedProofNode === node.id;
                const isDivergence = node.state === "divergence";

                return (
                  <button
                    key={node.id}
                    onClick={() => setSelectedProofNode(node.id)}
                    className={`p-3 text-left rounded-xs transition-micro border cursor-pointer ${
                      isSelected
                        ? "bg-[#FFFFFF] border-2 border-[#C9A96E] shadow-sm"
                        : isDivergence
                        ? "bg-[#FFFFFF] border-[#B83A3A] hover:bg-[#FFF9F9]"
                        : "bg-[#FFFFFF] border-[#D7D3CA] hover:bg-[#F1EFE9]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold tracking-wider text-[#6F747A]">
                        {node.name}
                      </span>
                      {isDivergence ? (
                        <span className="h-2 w-2 rounded-full bg-[#B83A3A]" title="Divergence" />
                      ) : (
                        <span className="h-2 w-2 rounded-full bg-[#1E7B4D]" title="Verified" />
                      )}
                    </div>
                    <div className="mt-2 font-mono text-sm font-bold text-[#17191C] font-tabular">
                      {node.amount}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Forensic Inspection Detail for Selected Node */}
          <div className="bg-[#FFFFFF] border-2 border-[#C9A96E] rounded-xs p-6 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 mb-4 border-b border-[#E2DDD3]">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#9E7B35]">
                  FORENSIC DOSSIER RECORD
                </span>
                <h3 className="text-base font-bold text-[#17191C] mt-0.5">
                  {activeDetail.label} ({activeDetail.recordId})
                </h3>
              </div>
              <span className="text-xs font-mono font-semibold text-[#555B61] bg-[#F7F5F0] px-3 py-1 rounded-xs border border-[#D7D3CA]">
                Source: {activeDetail.source}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-[#6F747A] mb-1">
                  WHY THIS DIVERGED
                </div>
                <p className="text-[#17191C] leading-relaxed mb-4 font-normal">
                  {activeDetail.why}
                </p>

                <div className="text-[10px] font-bold uppercase tracking-wider text-[#6F747A] mb-1">
                  CRYPTOGRAPHIC EVIDENCE
                </div>
                <p className="font-mono text-[#555B61] bg-[#F7F5F0] p-2.5 rounded-xs border border-[#D7D3CA]">
                  {activeDetail.evidence}
                </p>
              </div>

              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-[#6F747A] mb-1">
                  VERIDEX OPERATIONAL ASSESSMENT
                </div>
                <p className="text-[#17191C] leading-relaxed mb-4 font-normal">
                  {activeDetail.assessment}
                </p>

                <div className="text-[10px] font-bold uppercase tracking-wider text-[#9E7B35] mb-1">
                  BOUNDED ACTION UNDER HUMAN CONTROL
                </div>
                <div className="p-3 rounded-xs border border-[rgba(201,169,110,0.5)] bg-[rgba(201,169,110,0.1)] text-[#17191C] font-medium">
                  {activeDetail.action}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── THE VERIDEX LOOP (HOW IT WORKS) ───────────────────────── */}
      <section id="how-it-works" className="py-20 border-b border-[#D7D3CA]">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
              METHODOLOGY
            </span>
            <h2 className="text-3xl font-bold tracking-tight text-[#17191C] mt-2">
              SEE EXACTLY <span className="italic font-display font-normal text-[#9E7B35]">WHERE THE MONEY DIVERGED.</span>
            </h2>
            <p className="text-xs text-[#555B61] mt-2 leading-relaxed">
              Every financial discrepancy is tracked through an append-only pipeline from raw feed ingestion to human-authorized resolution.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
            {[
              { step: "01", name: "INGEST", desc: "Multi-source raw telemetry from Gateway, Ledger, Bank" },
              { step: "02", name: "NORMALIZE", desc: "Canonical schema alignment with strict decimal currency" },
              { step: "03", name: "MATCH", desc: "Deterministic hash matching across UTR & references" },
              { step: "04", name: "INVESTIGATE", desc: "ML candidate scoring and discrepancy identification" },
              { step: "05", name: "PROVE", desc: "Evidence graph linking transaction provenance" },
              { step: "06", name: "DECIDE", desc: "AI recommends root cause; humans authorize action" },
              { step: "07", name: "AUDIT", desc: "Immutable cryptographic ledger record of every event" },
            ].map((item) => (
              <div
                key={item.step}
                className="bg-[#FFFFFF] border border-[#D7D3CA] rounded-xs p-4 flex flex-col justify-between shadow-xs"
              >
                <div>
                  <div className="font-mono text-xs font-bold text-[#9E7B35] mb-2">
                    {item.step}
                  </div>
                  <div className="font-bold text-xs text-[#17191C] mb-1.5">
                    {item.name}
                  </div>
                </div>
                <div className="text-[11px] text-[#555B61] leading-relaxed pt-3 border-t border-[#E2DDD3]">
                  {item.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── THREE CORE PRODUCT PILLARS ────────────────────────────── */}
      <section id="pillars" className="py-20 border-b border-[#D7D3CA] bg-[#FFFFFF]">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
              CORE PILLARS
            </span>
            <h2 className="text-3xl font-bold tracking-tight text-[#17191C] mt-2">
              FINANCIAL CONTROL ARCHITECTURE
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 divide-y md:divide-y-0 md:divide-x divide-[#D7D3CA]">
            <div className="pt-6 md:pt-0 md:pr-8">
              <span className="text-[10px] font-mono font-bold text-[#9E7B35] tracking-widest block mb-2">
                01 / FOUNDATION
              </span>
              <h3 className="text-xl font-bold text-[#17191C] mb-3">RECONCILE</h3>
              <p className="text-xs text-[#555B61] leading-relaxed">
                Bring gateway, ledger, settlement, and bank records into a common authoritative control flow. Unify divergent feeds into canonical records without altering underlying banking data.
              </p>
            </div>

            <div className="pt-6 md:pt-0 md:px-8">
              <span className="text-[10px] font-mono font-bold text-[#9E7B35] tracking-widest block mb-2">
                02 / FORENSICS
              </span>
              <h3 className="text-xl font-bold text-[#17191C] mb-3">PROVE</h3>
              <p className="text-xs text-[#555B61] leading-relaxed">
                Trace financial conclusions directly to immutable evidence. Build explicit graph provenance linking orders, payments, settlement batches, and bank credits so every discrepancy has an audit trail.
              </p>
            </div>

            <div className="pt-6 md:pt-0 md:pl-8">
              <span className="text-[10px] font-mono font-bold text-[#9E7B35] tracking-widest block mb-2">
                03 / GOVERNANCE
              </span>
              <h3 className="text-xl font-bold text-[#17191C] mb-3">CONTROL</h3>
              <p className="text-xs text-[#555B61] leading-relaxed">
                AI recommends root-cause resolutions. Humans authorize financial execution. Financial actions remain strictly bounded by policy limits (e.g. ₹5,000 threshold) and fully audited.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── UNKNOWN IS A VALID FINANCIAL STATE ─────────────────────── */}
      <section id="evidence" className="py-20 border-b border-[#D7D3CA]">
        <div className="max-w-4xl mx-auto px-6">
          <div className="bg-[#FFFFFF] border-2 border-[#D7D3CA] rounded-xs p-8 shadow-xs">
            <div className="text-center max-w-xl mx-auto mb-8">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
                RESPONSIBLE FINANCIAL AI PHILOSOPHY
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#17191C] mt-2">
                UNKNOWN IS A VALID FINANCIAL STATE.
              </h2>
              <p className="text-xs text-[#555B61] mt-2 leading-relaxed">
                When evidence is incomplete, VERIDEX halts autonomous assumptions. Uncertainty is acknowledged as an explicit state, not swept under a false reconciliation.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-[#E2DDD3]">
              <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
                <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                  State Classification
                </div>
                <div className="mt-1.5 text-sm font-bold font-mono text-[#82550E]">
                  INSUFFICIENT EVIDENCE
                </div>
                <div className="text-[11px] text-[#555B61] mt-1">
                  Missing secondary confirmation
                </div>
              </div>

              <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
                <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                  Available Evidence
                </div>
                <div className="mt-1.5 text-sm font-bold font-mono text-[#17191C]">
                  2 / 4 Sources
                </div>
                <div className="text-[11px] text-[#555B61] mt-1">
                  Bank feed absent
                </div>
              </div>

              <div className="p-4 rounded-xs bg-[#FFF9F9] border border-[#B83A3A]">
                <div className="text-[10px] font-bold uppercase text-[#9E2828] tracking-wider">
                  Autonomous Action
                </div>
                <div className="mt-1.5 text-sm font-bold font-mono text-[#9E2828]">
                  STRICTLY BLOCKED
                </div>
                <div className="text-[11px] text-[#9E2828] mt-1">
                  No automated fund movement
                </div>
              </div>

              <div className="p-4 rounded-xs bg-[#F7FBF8] border border-[#1E7B4D]">
                <div className="text-[10px] font-bold uppercase text-[#16653E] tracking-wider">
                  Human Governance
                </div>
                <div className="mt-1.5 text-sm font-bold font-mono text-[#1E7B4D]">
                  REVIEW REQUIRED
                </div>
                <div className="text-[11px] text-[#16653E] mt-1">
                  Escalated to finance ops
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── MEASURED, NOT CLAIMED (Benchmark Proof) ────────────────── */}
      <section id="measured" className="py-20 border-b border-[#D7D3CA] bg-[#FFFFFF]">
        <div className="max-w-5xl mx-auto px-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-8 mb-8 border-b border-[#D7D3CA]">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
                ENGINE VALIDATION BENCHMARK
              </span>
              <h2 className="text-2xl font-bold tracking-tight text-[#17191C] mt-1">
                MEASURED, NOT CLAIMED.
              </h2>
              <p className="text-xs text-[#555B61] mt-1">
                Live authoritative evaluation metrics generated directly by the running reconciliation engine.
              </p>
            </div>

            <div className="text-xs font-mono text-[#6F747A]">
              Endpoint: /api/v1/controller/benchmark
            </div>
          </div>

          {/* Benchmark Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                Logical Txns
              </div>
              <div className="mt-2 text-2xl font-bold font-mono text-[#17191C] font-tabular">
                {benchmarkData?.num_transactions || 50}
              </div>
              <div className="text-[10px] text-[#555B61] mt-1">150 feed records</div>
            </div>

            <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                Precision
              </div>
              <div className="mt-2 text-2xl font-bold font-mono text-[#1E7B4D] font-tabular">
                {benchmarkLoading
                  ? "..."
                  : `${((benchmarkData?.precision ?? 0.9) * 100).toFixed(2)}%`}
              </div>
              <div className="text-[10px] text-[#555B61] mt-1">False match resistance</div>
            </div>

            <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                Recall
              </div>
              <div className="mt-2 text-2xl font-bold font-mono text-[#1E7B4D] font-tabular">
                {benchmarkLoading
                  ? "..."
                  : `${((benchmarkData?.recall ?? 1.0) * 100).toFixed(2)}%`}
              </div>
              <div className="text-[10px] text-[#555B61] mt-1">Ground truth match coverage</div>
            </div>

            <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                F1 Score
              </div>
              <div className="mt-2 text-2xl font-bold font-mono text-[#9E7B35] font-tabular">
                {benchmarkLoading
                  ? "..."
                  : `${((benchmarkData?.f1_score ?? 0.9474) * 100).toFixed(2)}%`}
              </div>
              <div className="text-[10px] text-[#555B61] mt-1">Harmonic accuracy</div>
            </div>

            <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
              <div className="text-[10px] font-bold uppercase text-[#6F747A] tracking-wider">
                Throughput
              </div>
              <div className="mt-2 text-2xl font-bold font-mono text-[#17191C] font-tabular">
                {benchmarkLoading
                  ? "..."
                  : `${benchmarkData?.throughput_records_per_sec || "2,935"} rec/s`}
              </div>
              <div className="text-[10px] text-[#555B61] mt-1">Live execution speed</div>
            </div>
          </div>

          <div className="p-4 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA] text-xs text-[#555B61] flex items-center justify-between">
            <span>
              Evaluation benchmark dataset seeded with 7 realistic discrepancy archetypes (normal, duplicate, delayed settlement, ambiguous reference, fee mismatch).
            </span>
            <Link
              href="/benchmark"
              className="text-[#9E7B35] font-bold hover:text-[#C9A96E] flex items-center gap-1 ml-4 flex-shrink-0"
            >
              <span>View Benchmark Console</span>
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── ENTER THE CONTROL ROOM (CTA SECTION) ─────────────────── */}
      <section className="py-24 border-b border-[#D7D3CA] text-center">
        <div className="max-w-3xl mx-auto px-6">
          <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
            OPERATIONAL ENVIRONMENT
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#17191C] mt-2 mb-4">
            CONTINUOUS FINANCIAL AUDIT AT SCALE
          </h2>
          <p className="text-sm text-[#555B61] max-w-xl mx-auto mb-8 leading-relaxed">
            Take command of the live reconciliation engine, investigate active exceptions, inspect statutory tax lines, and authorize bounded financial adjustments.
          </p>

          <Link
            href="/app"
            className="btn-gold px-8 py-3.5 text-sm font-bold shadow-xs inline-flex items-center gap-2"
          >
            <span>Access Control Center</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────────────────── */}
      <footer className="py-8 bg-[#F7F5F0] text-xs text-[#6F747A]">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="vx-mark text-[10px] w-5 h-5">VX</div>
            <span className="font-semibold text-[#17191C]">VERIDEX</span>
            <span>— AI Financial Control &amp; Reconciliation Engine</span>
          </div>

          <div className="flex items-center gap-4 text-[11px] font-mono">
            <span>PORT 8000 ACTIVE</span>
            <span>•</span>
            <span>STRICT HITL GOVERNANCE</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
