"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { integrationsApi } from "@/lib/api/integrationsApi";
import {
  Activity,
  ShieldCheck,
  Server,
  Database,
  Lock,
} from "lucide-react";

export default function SettingsPage() {
  // Backend Health Query
  const {
    data: health,
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
    <div className="space-y-6 pb-12 select-none">
      {/* Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            System Diagnostics
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            System Diagnostics &amp; Environment Governance
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Operational status of backend services, database persistence, and financial policy thresholds
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-[#8e96a0]">
          <span>Backend Target:</span>
          <span
            className="font-mono font-semibold text-[#eceae6] px-2.5 py-1 rounded-xs border"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            http://127.0.0.1:8000
          </span>
        </div>
      </div>

      {/* Service Diagnostics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
        <div
          className="rounded-sm border p-4 space-y-2"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] font-semibold">
            <span>FastAPI Backend Engine</span>
            <Activity className="h-4 w-4 text-[#6ecba0]" />
          </div>
          <div className="text-lg font-bold text-[#eceae6] flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#6ecba0]" />
            {health?.status === "ok" ? "Operational (Healthy)" : "Checking…"}
          </div>
          <div className="text-[11px] text-[#545e6a] font-mono">
            Engine: <strong className="text-[#eceae6]">{health?.app || "Veridex"}</strong> v{health?.version || "0.2.0"}
          </div>
        </div>

        <div
          className="rounded-sm border p-4 space-y-2"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] font-semibold">
            <span>Authoritative Storage</span>
            <Database className="h-4 w-4 text-[#c9a96e]" />
          </div>
          <div className="text-lg font-bold text-[#eceae6] flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#6ecba0]" />
            Active &amp; Grounded
          </div>
          <div className="text-[11px] text-[#545e6a] font-mono">
            PostgreSQL relational persistence layer
          </div>
        </div>

        <div
          className="rounded-sm border p-4 space-y-2"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div className="flex items-center justify-between text-[#8e96a0] uppercase text-[10px] font-semibold">
            <span>Gateway Ingestion</span>
            <Server className="h-4 w-4 text-[#8e96a0]" />
          </div>
          <div className="text-lg font-bold text-[#eceae6] flex items-center gap-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{
                background: rzpStatus?.api_reachable ? "var(--matched-text)" : "var(--variance-text)",
              }}
            />
            {rzpStatus?.api_reachable ? "Connected" : "Offline"}
          </div>
          <div className="text-[11px] text-[#545e6a] font-mono">
            Razorpay Sandbox API pipeline
          </div>
        </div>
      </div>

      {/* Governance & Policy Ceilings */}
      <div
        className="rounded-sm border p-6 text-xs text-[#eceae6] space-y-4"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="flex items-center gap-2 pb-3 border-b"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Lock className="h-4 w-4 text-[#c9a96e]" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6]">
            Active Governance Rules &amp; Policy Ceilings
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div
            className="p-3.5 rounded-xs border space-y-1.5"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="font-semibold text-xs text-[#eceae6]">
              Single Ledger Adjustment Threshold
            </div>
            <div className="text-base font-bold font-mono text-[#c9a96e]">
              INR 5,000.00
            </div>
            <p className="text-[11px] text-[#8e96a0] leading-snug">
              Adjustments exceeding this threshold require Level 2 Controller dual-authorization.
            </p>
          </div>

          <div
            className="p-3.5 rounded-xs border space-y-1.5"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="font-semibold text-xs text-[#eceae6]">
              Discrepancy Write-Off Threshold
            </div>
            <div className="text-base font-bold font-mono text-[#c9a96e]">
              INR 100.00
            </div>
            <p className="text-[11px] text-[#8e96a0] leading-snug">
              Strict limit on automatic or manual write-offs for unexplained penny variances.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
