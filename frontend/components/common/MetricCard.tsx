import React, { type ReactNode } from "react";
import { cn } from "@/lib/utils/formatters";
import { TrendArrow } from "@/components/common/TrendArrow";
import { CountUp } from "@/components/common/CountUp";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  icon?: ReactNode;
  badge?: ReactNode;
  statusBorder?: "emerald" | "rose" | "amber" | "indigo" | "none";
  className?: string;
  /**
   * Real change vs. the previous fetch (percentage points or absolute), shown
   * as a small up/down arrow next to the delta pill. Omit if no prior value
   * is available yet — never fabricated.
   */
  trendDelta?: number | null;
  /** Whether an increase in this metric is the desirable direction. */
  trendGoodDirection?: "up" | "down";
  /**
   * When provided, the displayed `value` is replaced by a count-up animation
   * from the previous real fetched number to this real number, run through
   * `countUpFormat` on every frame (e.g. formatINR). The raw `value` prop is
   * still used as a static fallback/accessible text when this is omitted.
   */
  countUpValue?: number;
  countUpFormat?: (n: number) => string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  delta,
  deltaType = "neutral",
  icon,
  badge,
  statusBorder = "none",
  className,
  trendDelta,
  trendGoodDirection = "up",
  countUpValue,
  countUpFormat,
}: MetricCardProps) {
  const borderStyles: Record<string, React.CSSProperties> = {
    none: {
      borderColor: "var(--border-standard)",
      background: "var(--surface-1)",
    },
    emerald: {
      borderColor: "var(--matched-border)",
      background: "var(--surface-1)",
      borderTop: "2px solid var(--matched)",
    },
    rose: {
      borderColor: "var(--variance-border)",
      background: "var(--surface-1)",
      borderTop: "2px solid var(--variance)",
    },
    amber: {
      borderColor: "var(--pending-border)",
      background: "var(--surface-1)",
      borderTop: "2px solid var(--pending)",
    },
    indigo: {
      borderColor: "var(--border-standard)",
      background: "var(--surface-1)",
      borderTop: "2px solid var(--accent)",
    },
  };

  const deltaStyles: Record<string, React.CSSProperties> = {
    positive: {
      color: "var(--matched-text)",
      background: "var(--matched-bg)",
      borderColor: "var(--matched-border)",
    },
    negative: {
      color: "var(--variance-text)",
      background: "var(--variance-bg)",
      borderColor: "var(--variance-border)",
    },
    neutral: {
      color: "var(--text-secondary)",
      background: "var(--surface-2)",
      borderColor: "var(--border-subtle)",
    },
  };

  return (
    <div
      className={cn(
        "rounded-xs border p-4 text-[#17191C] veridex-card-lift hover:border-[#BDB8AE] shadow-xs",
        className
      )}
      style={borderStyles[statusBorder] || borderStyles.none}
    >
      <div className="flex items-center justify-between gap-2 pb-2">
        <span
          className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#6F747A]"
        >
          {title}
        </span>
        {icon && <div className="text-[#6F747A]">{icon}</div>}
        {badge && <div>{badge}</div>}
      </div>

      <div className="flex items-baseline justify-between gap-2 pt-1">
        <div className="font-mono text-2xl font-bold tracking-tight text-[#17191C] font-tabular">
          {countUpValue !== undefined ? (
            <CountUp value={countUpValue} format={countUpFormat} />
          ) : (
            value
          )}
        </div>
        {delta && (
          <span
            className="inline-flex items-center px-1.5 py-0.5 rounded-xs text-[10px] font-mono font-semibold border"
            style={deltaStyles[deltaType] || deltaStyles.neutral}
          >
            {delta}
          </span>
        )}
      </div>

      {trendDelta !== undefined && trendDelta !== null && (
        <div className="mt-1">
          <TrendArrow delta={trendDelta} goodDirection={trendGoodDirection} />
        </div>
      )}

      {subtitle && (
        <p
          className="mt-1.5 text-xs text-[#555B61] line-clamp-1 font-medium"
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
