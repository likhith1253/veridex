"use client";

import React from "react";
import { formatDateTime, cn } from "@/lib/utils/formatters";
import type { AuditTimelineItem } from "@/types/audit";
import {
  ShieldCheck,
  Cpu,
  UserCheck,
  FileSpreadsheet,
  AlertOctagon,
  Play,
  RotateCcw,
  CheckCircle2,
} from "lucide-react";

interface AuditTimelineProps {
  events?: AuditTimelineItem[];
  isLoading?: boolean;
}

export function AuditTimeline({ events, isLoading }: AuditTimelineProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 p-4 animate-pulse">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-8 w-8 rounded-full bg-zinc-800" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-48 rounded bg-zinc-800" />
              <div className="h-3 w-96 rounded bg-zinc-800/60" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="p-8 text-center text-zinc-500 font-mono text-xs">
        No audit events recorded for this operational scope.
      </div>
    );
  }

  const getStageIcon = (stage: string) => {
    const s = stage.toUpperCase();
    if (s.includes("HUMAN") || s.includes("APPROVAL")) {
      return <UserCheck className="h-4 w-4 text-emerald-400" />;
    }
    if (s.includes("EXECUTION")) {
      return <Play className="h-4 w-4 text-sky-400" />;
    }
    if (s.includes("EXCEPTION")) {
      return <AlertOctagon className="h-4 w-4 text-rose-400" />;
    }
    if (s.includes("ML") || s.includes("INVESTIGATION") || s.includes("AI")) {
      return <Cpu className="h-4 w-4 text-purple-400" />;
    }
    if (s.includes("RECON")) {
      return <FileSpreadsheet className="h-4 w-4 text-indigo-400" />;
    }
    return <ShieldCheck className="h-4 w-4 text-zinc-400" />;
  };

  return (
    <div className="relative border-l border-zinc-800 ml-4 my-2 space-y-6">
      {events.map((ev, idx) => (
        <div key={idx} className="relative pl-6 text-xs">
          {/* Node Icon Circle */}
          <div className="absolute -left-3.5 top-0.5 flex h-7 w-7 items-center justify-center rounded-full border border-zinc-800 bg-[#11131a] shadow-xs">
            {getStageIcon(ev.stage)}
          </div>

          {/* Event Content Box */}
          <div className="rounded-lg border border-zinc-800/80 bg-[#11131a] p-4 text-zinc-200">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 pb-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-zinc-100">
                  {ev.stage.replace(/_/g, " ")}
                </span>
                {ev.actor && (
                  <span className="font-mono text-[11px] px-1.5 py-0.2 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
                    Actor: {ev.actor}
                  </span>
                )}
              </div>
              <span className="font-mono text-[11px] text-zinc-500">
                {formatDateTime(ev.timestamp)}
              </span>
            </div>

            <p className="mt-1 text-xs text-zinc-300 font-mono leading-relaxed">
              {ev.event}
            </p>

            {ev.transaction_id && (
              <div className="mt-2 text-[11px] font-mono text-zinc-500">
                Entity Ref: <span className="text-zinc-300">{ev.transaction_id}</span>
              </div>
            )}

            {ev.evidence && Object.keys(ev.evidence).length > 0 && (
              <details className="mt-2 text-[11px] font-mono text-zinc-400">
                <summary className="cursor-pointer text-sky-400 hover:underline">
                  View Grounded Evidence Payload
                </summary>
                <pre className="mt-1.5 p-2 rounded bg-black/50 border border-zinc-800 text-[10px] text-zinc-300 overflow-x-auto">
                  {JSON.stringify(ev.evidence, null, 2)}
                </pre>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
