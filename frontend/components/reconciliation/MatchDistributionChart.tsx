"use client";

import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

interface MatchDistributionChartProps {
  deterministic: number;
  mlRecovered: number;
  manualReview: number;
  unresolved: number;
  isLoading?: boolean;
}

const SLICE_COLORS = {
  deterministic: "#6ecba0",
  ml: "#8fb3d9",
  manual: "#d4a84e",
  unresolved: "#e07070",
};

export function MatchDistributionChart({
  deterministic,
  mlRecovered,
  manualReview,
  unresolved,
  isLoading,
}: MatchDistributionChartProps) {
  const total = deterministic + mlRecovered + manualReview + unresolved;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[180px]">
        <div className="h-32 w-32 rounded-full skeleton" />
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-[180px] text-xs text-[#8e96a0]">
        No reconciled records yet
      </div>
    );
  }

  const data = [
    { name: "Exact matches", value: deterministic, color: SLICE_COLORS.deterministic },
    { name: "Smart matches", value: mlRecovered, color: SLICE_COLORS.ml },
    { name: "Manual review", value: manualReview, color: SLICE_COLORS.manual },
    { name: "Open issues", value: unresolved, color: SLICE_COLORS.unresolved },
  ].filter((d) => d.value > 0);

  const matchRate = total > 0 ? (((deterministic + mlRecovered) / total) * 100).toFixed(1) : "0.0";

  return (
    <div className="relative">
      <div className="h-[180px] veridex-scale-in">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={78}
              paddingAngle={2}
              stroke="none"
              animationDuration={900}
              animationEasing="ease-out"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [`${value} records`, String(name)]}
              contentStyle={{
                background: "var(--surface-1)",
                border: "1px solid var(--border-standard)",
                borderRadius: 4,
                fontSize: 11,
                fontFamily: "var(--font-mono, monospace)",
              }}
              labelStyle={{ display: "none" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {/* Center readout */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div className="text-2xl font-bold font-mono text-[#eceae6] font-tabular">{matchRate}%</div>
        <div className="text-[9px] uppercase tracking-wider text-[#8e96a0]">reconciled</div>
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 mt-3 text-[11px]">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
            <span className="text-[#8e96a0] truncate">{d.name}</span>
            <span className="text-[#eceae6] font-mono font-semibold ml-auto">{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
