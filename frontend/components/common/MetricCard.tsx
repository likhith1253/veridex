import React, { type ReactNode } from "react";
import { cn } from "@/lib/utils/formatters";

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
}: MetricCardProps) {
  const borderStyles: Record<string, React.CSSProperties> = {
    none: {
      borderColor: "var(--border-subtle)",
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
      color: "var(--text-tertiary)",
      background: "var(--surface-3)",
      borderColor: "var(--border-subtle)",
    },
  };

  return (
    <div
      className={cn(
        "rounded-sm border p-4 text-[#eceae6] transition-micro hover:border-[#2d3540]",
        className
      )}
      style={borderStyles[statusBorder] || borderStyles.none}
    >
      <div className="flex items-center justify-between gap-2 pb-2">
        <span
          className="text-[11px] font-semibold uppercase tracking-[0.08em]"
          style={{ color: "var(--text-tertiary)" }}
        >
          {title}
        </span>
        {icon && <div style={{ color: "var(--text-tertiary)" }}>{icon}</div>}
        {badge && <div>{badge}</div>}
      </div>

      <div className="flex items-baseline justify-between gap-2 pt-1">
        <div className="font-mono text-2xl font-bold tracking-tight text-[#eceae6] font-tabular">
          {value}
        </div>
        {delta && (
          <span
            className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-[10px] font-mono font-medium border"
            style={deltaStyles[deltaType] || deltaStyles.neutral}
          >
            {delta}
          </span>
        )}
      </div>

      {subtitle && (
        <p
          className="mt-1.5 text-xs line-clamp-1"
          style={{ color: "var(--text-secondary)" }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
