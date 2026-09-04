"use client";

import React, { useState } from "react";
import { formatDateTime } from "@/lib/utils/formatters";
import type { AuditTimelineItem } from "@/types/audit";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import {
  ShieldCheck,
  Cpu,
  UserCheck,
  FileSpreadsheet,
  AlertOctagon,
  Play,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  FileCode,
} from "lucide-react";

interface AuditTimelineProps {
  events?: AuditTimelineItem[];
  isLoading?: boolean;
}

export function AuditTimeline({ events, isLoading }: AuditTimelineProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-7 w-7 rounded-xs skeleton" />
            <div className="flex-1 space-y-2">
              <div className="h-5 w-48 skeleton" />
              <div className="h-4 w-full skeleton" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="py-12 text-center text-[#8e96a0] text-xs">
        No audit events recorded for this operational scope.
      </div>
    );
  }

  const getStageStyle = (stage?: string | null, eventType?: string | null) => {
    const s = (stage || eventType || "").toUpperCase();
    if (s.includes("HUMAN") || s.includes("APPROVAL") || s.includes("DECISION")) {
      return {
        icon: <UserCheck className="h-3.5 w-3.5 text-[#080a0c]" />,
        markerBg: "var(--accent)",
        markerBorder: "var(--accent-hover)",
        badgeBg: "var(--accent-dim)",
        badgeText: "var(--accent)",
        badgeBorder: "var(--accent-border)",
      };
    }
    if (s.includes("EXECUTION") || s.includes("EXECUTE") || s.includes("RESOLVE")) {
      return {
        icon: <Play className="h-3.5 w-3.5 text-[#080a0c]" />,
        markerBg: "var(--matched-text)",
        markerBorder: "var(--matched-border)",
        badgeBg: "var(--matched-bg)",
        badgeText: "var(--matched-text)",
        badgeBorder: "var(--matched-border)",
      };
    }
    if (s.includes("EXCEPTION") || s.includes("REJECT") || s.includes("FAIL")) {
      return {
        icon: <AlertOctagon className="h-3.5 w-3.5 text-[#eceae6]" />,
        markerBg: "var(--variance-text)",
        markerBorder: "var(--variance-border)",
        badgeBg: "var(--variance-bg)",
        badgeText: "var(--variance-text)",
        badgeBorder: "var(--variance-border)",
      };
    }
    if (s.includes("ML") || s.includes("INVESTIGATION") || s.includes("AI")) {
      return {
        icon: <Cpu className="h-3.5 w-3.5 text-[#eceae6]" />,
        markerBg: "#22272e",
        markerBorder: "var(--border-subtle)",
        badgeBg: "var(--surface-3)",
        badgeText: "#c9a96e",
        badgeBorder: "var(--border-subtle)",
      };
    }
    return {
      icon: <FileSpreadsheet className="h-3.5 w-3.5 text-[#eceae6]" />,
      markerBg: "#22272e",
      markerBorder: "var(--border-subtle)",
      badgeBg: "var(--surface-3)",
      badgeText: "var(--text-secondary)",
      badgeBorder: "var(--border-subtle)",
    };
  };

  return (
    <div
      className="relative pl-6 space-y-5 select-none ml-3 my-2"
      style={{ borderLeft: "2px solid var(--border-subtle)" }}
    >
      {events.map((ev, idx) => {
        const eventKey = ev.event_id
          ? `${ev.event_id}-${idx}`
          : ev.id
          ? `${ev.id}-${idx}`
          : `audit-ev-${idx}`;
        const eventLabel = (ev.event_type || ev.stage || "AUDIT_RECORD").replace(/_/g, " ");
        const payload = ev.details || ev.evidence;
        const hasPayload = Boolean(payload && typeof payload === "object" && Object.keys(payload).length > 0);
        const style = getStageStyle(ev.stage, ev.event_type);

        return (
          <AuditEventRow
            key={eventKey}
            ev={ev}
            eventLabel={eventLabel}
            hasPayload={hasPayload}
            payload={payload}
            style={style}
          />
        );
      })}
    </div>
  );
}

function AuditEventRow({
  ev,
  eventLabel,
  hasPayload,
  payload,
  style,
}: {
  ev: AuditTimelineItem;
  eventLabel: string;
  hasPayload: boolean;
  payload: unknown;
  style: {
    icon: React.ReactNode;
    markerBg: string;
    markerBorder: string;
    badgeBg: string;
    badgeText: string;
    badgeBorder: string;
  };
}) {
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);

  // Derive structured details if available
  const actor = ev.actor || "System Automated";
  const timestamp = ev.timestamp ? formatDateTime(ev.timestamp) : "—";
  const description = ev.event || (payload as any)?.description || (payload as any)?.explanation || "Operational audit record";
  const outcome = (payload as any)?.outcome || (payload as any)?.status || (payload as any)?.action || "SUCCESS";

  return (
    <div className="relative group">
      {/* Timeline Node Marker */}
      <div
        className="absolute -left-[35px] top-1.5 flex h-6 w-6 items-center justify-center rounded-xs shadow-xs"
        style={{
          background: style.markerBg,
          border: `1px solid ${style.markerBorder}`,
        }}
      >
        {style.icon}
      </div>

      {/* Event Card */}
      <div
        className="rounded-xs p-4 transition-micro border"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--border-subtle)",
        }}
      >
        {/* Header Row: WHAT + WHO + WHEN */}
        <div
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 mb-3"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold text-xs uppercase tracking-wider text-[#eceae6]">
              {eventLabel}
            </span>
            <span
              className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-xs border"
              style={{
                background: style.badgeBg,
                color: style.badgeText,
                borderColor: style.badgeBorder,
              }}
            >
              WHO: {actor}
            </span>
          </div>

          <div className="text-[11px] font-mono text-[#8e96a0] flex items-center gap-1.5">
            <span className="text-[#545e6a]">WHEN:</span>
            <span className="font-semibold text-[#eceae6]">{timestamp}</span>
          </div>
        </div>

        {/* Structured Grid: WHAT / WHY / OUTCOME */}
        <div className="space-y-2 mb-3 text-xs">
          <div className="flex items-start gap-2">
            <span className="text-[10px] font-mono font-semibold text-[#8e96a0] uppercase w-14 flex-shrink-0 pt-0.5">
              WHY:
            </span>
            <p className="text-xs text-[#eceae6] leading-relaxed flex-1">
              {description}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-semibold text-[#8e96a0] uppercase w-14 flex-shrink-0">
              OUTCOME:
            </span>
            <span className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-[#6ecba0]">
              <CheckCircle2 className="h-3 w-3" />
              {String(outcome).toUpperCase()}
            </span>
          </div>
        </div>

        {/* Anchors: TXN ID + RUN ID — using TechnicalReference */}
        <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono pt-1">
          {ev.transaction_id && (
            <div className="flex items-center gap-1.5">
              <span className="text-[#545e6a] text-[10px] uppercase">TXN:</span>
              <TechnicalReference id={ev.transaction_id} maxVisible={22} inline />
            </div>
          )}
          {ev.run_id && (
            <div className="flex items-center gap-1.5">
              <span className="text-[#545e6a] text-[10px] uppercase">RUN:</span>
              <TechnicalReference id={ev.run_id} maxVisible={22} inline />
            </div>
          )}
          {ev.id && (
            <div className="flex items-center gap-1.5">
              <span className="text-[#545e6a] text-[10px] uppercase">EVENT:</span>
              <TechnicalReference id={ev.id} maxVisible={18} inline />
            </div>
          )}
        </div>

        {/* Technical Evidence — Progressive Disclosure behind toggle */}
        {hasPayload && (
          <div
            className="mt-3 pt-2.5"
            style={{ borderTop: "1px solid var(--border-subtle)" }}
          >
            <button
              onClick={() => setEvidenceExpanded((v) => !v)}
              className="flex items-center gap-1.5 text-[10px] font-mono text-[#8e96a0] hover:text-[#c9a96e] transition-colors uppercase tracking-wider"
            >
              <FileCode className="h-3 w-3" />
              {evidenceExpanded ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
              {evidenceExpanded ? "Hide technical details" : "Technical details"}
            </button>
            {evidenceExpanded && (
              <pre
                className="mt-2 p-3 rounded-xs border overflow-x-auto text-[10.5px] font-mono leading-relaxed"
                style={{
                  background: "var(--surface-2)",
                  borderColor: "var(--border-subtle)",
                  color: "var(--text-secondary)",
                }}
              >
                {JSON.stringify(payload, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
