"use client";

import React from "react";
import { motion } from "framer-motion";

export interface BreakdownSegment {
  label: string;
  value: number;
  color: string;
}

interface BreakdownBarProps {
  segments: BreakdownSegment[];
  className?: string;
  height?: number;
  /** Show the numeric count next to each legend label. */
  showCounts?: boolean;
}

/**
 * Horizontal segmented distribution bar (flex row of colored divs sized by
 * percentage of the real fetched total) with a color legend below it. No
 * charting library — plain divs, animated width on mount.
 */
export function BreakdownBar({
  segments,
  className,
  height = 10,
  showCounts = true,
}: BreakdownBarProps) {
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value), 0);

  if (total <= 0) {
    return (
      <div className={className}>
        <div
          className="rounded-full overflow-hidden"
          style={{ height, background: "var(--surface-3)" }}
        />
        <p className="text-[11px] mt-2" style={{ color: "var(--text-tertiary)" }}>
          No distribution data yet.
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      <div
        className="flex rounded-full overflow-hidden w-full"
        style={{ height, background: "var(--surface-3)" }}
      >
        {segments
          .filter((s) => s.value > 0)
          .map((s, idx) => {
            const pct = (s.value / total) * 100;
            return (
              <motion.div
                key={`${s.label}-${idx}`}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.6, delay: idx * 0.05, ease: [0.16, 1, 0.3, 1] }}
                style={{ background: s.color, height: "100%" }}
                title={`${s.label}: ${pct.toFixed(1)}%`}
              />
            );
          })}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
        {segments.map((s, idx) => (
          <div key={`${s.label}-legend-${idx}`} className="flex items-center gap-1.5 text-[11px]">
            <span
              className="inline-block rounded-full flex-shrink-0"
              style={{ width: 8, height: 8, background: s.color }}
            />
            <span style={{ color: "var(--text-secondary)" }} className="capitalize">
              {s.label.replace(/_/g, " ")}
            </span>
            {showCounts && (
              <span className="font-mono font-semibold" style={{ color: "var(--text-primary)" }}>
                {s.value}
              </span>
            )}
            <span style={{ color: "var(--text-tertiary)" }}>
              ({total > 0 ? ((s.value / total) * 100).toFixed(0) : 0}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
