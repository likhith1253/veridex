"use client";

import React, { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList } from "recharts";
import type { ExceptionItem } from "@/types/controller";

interface ExceptionCategoryChartProps {
  exceptions: ExceptionItem[];
  isLoading?: boolean;
}

const BAR_COLORS = ["#e07070", "#d4a84e", "#c98f70", "#b389c9", "#8fb3d9", "#6ecba0", "#9aa5b2"];

export function ExceptionCategoryChart({ exceptions, isLoading }: ExceptionCategoryChartProps) {
  const data = useMemo(() => {
    const counts = new Map<string, number>();
    for (const ex of exceptions) {
      const cat = (ex.category || ex.exception_category || "unexplained").replace(/_/g, " ");
      counts.set(cat, (counts.get(cat) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 7);
  }, [exceptions]);

  if (isLoading) {
    return (
      <div className="h-[200px] flex items-center justify-center">
        <div className="h-full w-full skeleton rounded-xs" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="h-[200px] flex items-center justify-center text-xs text-[#8e96a0]">
        No issues to categorize — all records reconciled
      </div>
    );
  }

  return (
    <div className="h-[220px] veridex-fade-in">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 4, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fill: "#8e96a0", fontSize: 10, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(201,169,110,0.06)" }}
            formatter={(value) => [`${value} issues`, ""]}
            contentStyle={{
              background: "var(--surface-1)",
              border: "1px solid var(--border-standard)",
              borderRadius: 4,
              fontSize: 11,
            }}
            labelStyle={{ color: "#eceae6", fontWeight: 600, marginBottom: 2 }}
          />
          <Bar dataKey="count" radius={[0, 3, 3, 0]} animationDuration={800} animationEasing="ease-out">
            {data.map((_, i) => (
              <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              style={{ fill: "#eceae6", fontSize: 11, fontFamily: "monospace", fontWeight: 700 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
