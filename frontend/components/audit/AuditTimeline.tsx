"use client";

import React from "react";
import { formatDateTime } from "@/lib/utils/formatters";
import type { AuditTimelineItem } from "@/types/audit";
import {
  ShieldCheck,
  Cpu,
  UserCheck,
  FileSpreadsheet,
  AlertOctagon,
  Play,
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
      <div className="py-12 text-center text-[#6F747A] text-xs">
        No audit events recorded for this operational scope.
      </div>
    );
  }

  const getStageStyle = (stage?: string | null, eventType?: string | null) => {
    const s = (stage || eventType || "").toUpperCase();
    if (s.includes("HUMAN") || s.includes("APPROVAL")) {
      return {
        icon: <UserCheck className="h-3.5 w-3.5 text-[#171A1E]" />,
        markerBg: "#C9A96E",
        markerBorder: "#B89658",
        badgeBg: "rgba(201, 169, 110, 0.12)",
        badgeText: "#8A6418",
        badgeBorder: "rgba(201, 169, 110, 0.4)",
      };
    }
    if (s.includes("EXECUTION") || s.includes("EXECUTE")) {
      return {
        icon: <Play className="h-3.5 w-3.5 text-[#FFFFFF]" />,
        markerBg: "#1E7B4D",
        markerBorder: "#16653E",
        badgeBg: "rgba(30, 123, 77, 0.10)",
        badgeText: "#16653E",
        badgeBorder: "rgba(30, 123, 77, 0.3)",
      };
    }
    if (s.includes("EXCEPTION") || s.includes("REJECT") || s.includes("FAIL")) {
      return {
        icon: <AlertOctagon className="h-3.5 w-3.5 text-[#FFFFFF]" />,
        markerBg: "#B83A3A",
        markerBorder: "#9E2828",
        badgeBg: "rgba(184, 58, 58, 0.10)",
        badgeText: "#9E2828",
        badgeBorder: "rgba(184, 58, 58, 0.3)",
      };
    }
    if (s.includes("ML") || s.includes("INVESTIGATION") || s.includes("AI")) {
      return {
        icon: <Cpu className="h-3.5 w-3.5 text-[#17191C]" />,
        markerBg: "#E8E5DD",
        markerBorder: "#BDB8AE",
        badgeBg: "#F1EFE9",
        badgeText: "#424954",
        badgeBorder: "#D7D3CA",
      };
    }
    return {
      icon: <FileSpreadsheet className="h-3.5 w-3.5 text-[#17191C]" />,
      markerBg: "#E8E5DD",
      markerBorder: "#BDB8AE",
      badgeBg: "#F1EFE9",
      badgeText: "#555B61",
      badgeBorder: "#D7D3CA",
    };
  };

  return (
    <div className="relative pl-6 space-y-6 select-none border-l-2 border-[#D7D3CA] ml-3 my-2">
      {events.map((ev, idx) => {
        const eventKey = ev.event_id ? `${ev.event_id}-${idx}` : (ev.id ? `${ev.id}-${idx}` : `audit-ev-${idx}`);
        const eventLabel = (ev.event_type || ev.stage || "AUDIT_RECORD").replace(/_/g, " ");
        const payload = ev.details || ev.evidence;
        const hasPayload = payload && typeof payload === "object" && Object.keys(payload).length > 0;
        const style = getStageStyle(ev.stage, ev.event_type);

        return (
          <div key={eventKey} className="relative group">
            {/* Timeline Node Marker */}
            <div
              className="absolute -left-[35px] top-1 flex h-6 w-6 items-center justify-center rounded-xs shadow-xs"
              style={{
                background: style.markerBg,
                border: `1px solid ${style.markerBorder}`,
              }}
            >
              {style.icon}
            </div>

            {/* Event Card (Pure white #FFFFFF, crisp border #D7D3CA) */}
            <div className="bg-[#FFFFFF] border border-[#D7D3CA] hover:border-[#BDB8AE] rounded-xs p-4 shadow-xs transition-micro">
              {/* Header Row: WHAT + WHO + WHEN */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 mb-3 border-b border-[#E2DDD3]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold text-xs uppercase tracking-wider text-[#17191C]">
                    {eventLabel}
                  </span>
                  {ev.actor && (
                    <span
                      className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-xs border"
                      style={{
                        background: style.badgeBg,
                        color: style.badgeText,
                        borderColor: style.badgeBorder,
                      }}
                    >
                      ACTOR: {ev.actor}
                    </span>
                  )}
                </div>

                <div className="text-[11px] font-mono text-[#555B61] flex items-center gap-1.5">
                  <span className="text-[#6F747A]">WHEN:</span>
                  <span className="font-semibold text-[#17191C]">
                    {ev.timestamp ? formatDateTime(ev.timestamp) : "—"}
                  </span>
                </div>
              </div>

              {/* Event Description (WHAT / WHY) */}
              {ev.event && (
                <p className="text-xs text-[#17191C] leading-relaxed mb-3 font-normal">
                  {ev.event}
                </p>
              )}

              {/* Anchors: TXN ID + RUN ID */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono pt-1">
                {ev.transaction_id && (
                  <div className="flex items-center gap-1.5 bg-[#F7F5F0] px-2.5 py-1 rounded-xs border border-[#E2DDD3]">
                    <span className="text-[#6F747A] text-[10px] uppercase">TXN ANCHOR:</span>
                    <span className="font-semibold text-[#17191C]">{ev.transaction_id}</span>
                  </div>
                )}
                {ev.run_id && (
                  <div className="flex items-center gap-1.5 bg-[#F7F5F0] px-2.5 py-1 rounded-xs border border-[#E2DDD3]">
                    <span className="text-[#6F747A] text-[10px] uppercase">RUN SCOPE:</span>
                    <span className="font-semibold text-[#17191C]">{ev.run_id}</span>
                  </div>
                )}
              </div>

              {/* Evidence Record */}
              {hasPayload && (
                <div className="mt-3 pt-2.5 border-t border-[#E2DDD3]">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-[#6F747A] mb-1">
                    Immutable Evidence Record
                  </div>
                  <pre className="p-3 rounded-xs border border-[#D7D3CA] bg-[#F7F5F0] overflow-x-auto text-[10.5px] font-mono text-[#17191C] leading-relaxed">
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
