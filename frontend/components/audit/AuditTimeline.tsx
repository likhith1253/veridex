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
  Database,
  FileText,
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
            <div className="h-6 w-6 rounded-xs skeleton" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-48 skeleton" />
              <div className="h-3 w-96 skeleton" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="p-8 text-center text-[#8e96a0] text-xs">
        No audit events recorded for this operational scope.
      </div>
    );
  }

  const getStageIcon = (stage?: string | null, eventType?: string | null) => {
    const s = (stage || eventType || "").toUpperCase();
    if (s.includes("HUMAN") || s.includes("APPROVAL")) {
      return <UserCheck className="h-3.5 w-3.5 text-[#c9a96e]" />;
    }
    if (s.includes("EXECUTION") || s.includes("EXECUTE")) {
      return <Play className="h-3.5 w-3.5 text-[#6ecba0]" />;
    }
    if (s.includes("EXCEPTION") || s.includes("REJECT") || s.includes("FAIL")) {
      return <AlertOctagon className="h-3.5 w-3.5 text-[#e07070]" />;
    }
    if (s.includes("ML") || s.includes("INVESTIGATION") || s.includes("AI")) {
      return <Cpu className="h-3.5 w-3.5 text-[#9aa5b2]" />;
    }
    if (s.includes("RECON") || s.includes("MATCH")) {
      return <FileSpreadsheet className="h-3.5 w-3.5 text-[#8e96a0]" />;
    }
    return <ShieldCheck className="h-3.5 w-3.5 text-[#8e96a0]" />;
  };

  return (
    <div
      className="relative ml-3 my-2 space-y-5 select-none"
      style={{ borderLeft: "1px solid var(--border-subtle)" }}
    >
      {events.map((ev, idx) => {
        const eventKey = ev.event_id ? `${ev.event_id}-${idx}` : (ev.id ? `${ev.id}-${idx}` : `audit-ev-${idx}`);
        const eventLabel = (ev.event_type || ev.stage || "AUDIT_RECORD").replace(/_/g, " ");
        const payload = ev.details || ev.evidence;
        const hasPayload = payload && typeof payload === "object" && Object.keys(payload).length > 0;

        return (
          <div key={eventKey} className="relative pl-6 text-xs">
            {/* Chronological Node Marker */}
            <div
              className="absolute -left-3 top-1 flex h-6 w-6 items-center justify-center rounded-xs border"
              style={{
                borderColor: "var(--border-standard)",
                background: "var(--surface-2)",
              }}
            >
              {getStageIcon(ev.stage, ev.event_type)}
            </div>

            {/* Event Block (WHEN, WHO, WHAT, WHY, EVIDENCE, OUTCOME) */}
            <div
              className="rounded-sm border p-4 text-[#eceae6]"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--surface-1)",
              }}
            >
              {/* Event Header: WHAT + WHO + WHEN */}
              <div
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 pb-3 mb-2.5"
                style={{ borderBottom: "1px solid var(--border-subtle)" }}
              >
                <div className="flex items-center gap-2">
                  <span className="font-bold text-xs uppercase tracking-wider text-[#eceae6]">
                    {eventLabel}
                  </span>
                  {ev.actor && (
                    <span
                      className="text-[10px] px-2 py-0.5 rounded-xs border text-[#8e96a0]"
                      style={{
                        borderColor: "var(--border-standard)",
                        background: "var(--surface-2)",
                      }}
                    >
                      WHO: <strong className="text-[#eceae6] font-mono">{ev.actor}</strong>
                    </span>
                  )}
                </div>
                <span className="text-[11px] font-mono text-[#545e6a]">
                  WHEN: {ev.timestamp ? formatDateTime(ev.timestamp) : "—"}
                </span>
              </div>

              {/* Event Message (WHAT / WHY) */}
              {ev.event && (
                <p className="text-xs text-[#eceae6] leading-relaxed mb-2">
                  {ev.event}
                </p>
              )}

              {/* Operational Anchors */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono text-[#8e96a0] pt-1">
                {ev.transaction_id && (
                  <div>
                    <span className="text-[#545e6a]">ANCHOR TXN: </span>
                    <span className="text-[#eceae6]">{ev.transaction_id}</span>
                  </div>
                )}
                {ev.run_id && (
                  <div>
                    <span className="text-[#545e6a]">RUN SCOPE: </span>
                    <span className="text-[#eceae6]">{ev.run_id}</span>
                  </div>
                )}
              </div>

              {/* Immutable Evidence Payload */}
              {hasPayload && (
                <div
                  className="mt-3 pt-2 text-[10px] font-mono space-y-1"
                  style={{ borderTop: "1px solid var(--border-subtle)" }}
                >
                  <span className="text-[#545e6a] uppercase block tracking-wider">EVIDENCE RECORD:</span>
                  <pre
                    className="p-2 rounded-xs border overflow-x-auto text-[10px] text-[#8e96a0]"
                    style={{
                      borderColor: "var(--border-subtle)",
                      background: "var(--surface-2)",
                    }}
                  >
                    {JSON.stringify(payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
