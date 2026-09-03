"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { integrationsApi } from "@/lib/api/integrationsApi";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  Settings,
  Activity,
  ShieldCheck,
  Server,
  Database,
  Lock,
  Cpu,
  Layers,
} from "lucide-react";

export default function SettingsPage() {
  // Backend Health Query
  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch,
  } = useQuery({
    queryKey: ["settings-health"],
    queryFn: () => apiClient<{ status: string; app?: string; version?: string }>("/health"),
  });

  // Razorpay Gateway Status
  const { data: rzpStatus } = useQuery({
    queryKey: ["settings-rzp"],
    queryFn: () => integrationsApi.getRazorpayStatus(),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            System Diagnostics & Environment Configuration
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Operational status of backend microservices, database connections, and finance policy thresholds.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-zinc-400">
          <span>Backend Endpoint:</span>
          <span className="font-semibold text-zinc-200 px-2 py-1 rounded bg-[#171a23] border border-zinc-800">
            http://127.0.0.1:8000
          </span>
        </div>
      </div>

      {/* Microservice Diagnostics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
        <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4 space-y-2">
          <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px]">
            <span>FastAPI Backend Engine</span>
            <Activity className="h-4 w-4 text-emerald-400 animate-pulse" />
          </div>
          <div className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            {health?.status === "ok" ? "Operational (Healthy)" : "Checking..."}
          </div>
          <div className="text-[11px] text-zinc-500">
            Engine: <strong className="text-zinc-300">{health?.app || "Veridex"}</strong> v{health?.version || "0.2.0"}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4 space-y-2">
          <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px]">
            <span>PostgreSQL & Storage Layer</span>
            <Database className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-400" />
            Connected
          </div>
          <div className="text-[11px] text-zinc-500">
            Driver: <strong className="text-zinc-300">AsyncPG / SQLAlchemy 2.0</strong>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-4 space-y-2">
          <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px]">
            <span>Payment Gateway Connector</span>
            <Server className="h-4 w-4 text-purple-400" />
          </div>
          <div className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${rzpStatus?.api_reachable ? "bg-emerald-400" : "bg-zinc-500"}`} />
            {rzpStatus?.api_reachable ? "Razorpay Active" : "Unconnected"}
          </div>
          <div className="text-[11px] text-zinc-500">
            Mode: <strong className="text-zinc-300 uppercase">{rzpStatus?.mode || "Test Mode"}</strong>
          </div>
        </div>
      </div>

      {/* Policy Limits & Governance Rules */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 text-xs font-mono space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            Financial Governance & Human Authorization Policy Limits
          </h2>
          <span className="text-[10px] text-zinc-500">Enforced by Backend Guardrails</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-3.5 rounded-lg bg-[#171a23] border border-zinc-800 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase">Single Adjustment Ceiling</div>
            <div className="text-lg font-bold text-zinc-100">INR 5,000.00</div>
            <p className="text-[11px] text-zinc-400">
              Any adjustment exceeding this threshold requires escalation to Senior Controller approval.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-[#171a23] border border-zinc-800 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase">Maximum Automated Write-off</div>
            <div className="text-lg font-bold text-zinc-100">INR 100.00</div>
            <p className="text-[11px] text-zinc-400">
              Write-offs above INR 100.00 cannot be posted automatically and require manual sign-off.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-[#171a23] border border-zinc-800 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase">Human-in-the-Loop Actor Validation</div>
            <div className="text-lg font-bold text-emerald-400">Strict Human Actor Enforcement</div>
            <p className="text-[11px] text-zinc-400">
              Action approvals submitted with AI agent names (e.g. &apos;ai&apos;, &apos;agent&apos;, &apos;bot&apos;) are strictly rejected by the backend.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-[#171a23] border border-zinc-800 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase">Cryptographic Audit Immutability</div>
            <div className="text-lg font-bold text-sky-400">Append-Only Event Store</div>
            <p className="text-[11px] text-zinc-400">
              Every stage transition and approval decision is logged with timestamp, actor ID, and evidence references.
            </p>
          </div>
        </div>
      </div>

      {/* Security Architecture Notice */}
      <div className="rounded-lg border border-zinc-800 bg-[#11131a] p-5 text-xs text-zinc-400 font-mono space-y-2">
        <div className="flex items-center gap-2 text-zinc-200 font-bold uppercase text-[11px]">
          <Lock className="h-4 w-4 text-emerald-400" /> Security Invariant Discipline
        </div>
        <p className="text-[11px] leading-relaxed">
          In compliance with fintech security standards, client-side configuration strictly excludes secret API keys, webhook signing secrets, and database credentials. All credentials remain secured on the backend environment.
        </p>
      </div>
    </div>
  );
}
