import React from "react";
import { cn } from "@/lib/utils/formatters";

interface LoadingSkeletonProps {
  variant?: "card" | "table" | "dossier" | "text";
  count?: number;
  className?: string;
}

export function LoadingSkeleton({
  variant = "card",
  count = 3,
  className,
}: LoadingSkeletonProps) {
  if (variant === "card") {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-28 rounded-lg border border-zinc-800/80 bg-[#11131a] p-4 animate-pulse",
              className
            )}
          >
            <div className="h-3 w-24 rounded bg-zinc-800" />
            <div className="mt-4 h-7 w-36 rounded bg-zinc-800" />
            <div className="mt-3 h-3 w-48 rounded bg-zinc-800/50" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === "table") {
    return (
      <div className={cn("rounded-lg border border-zinc-800/80 bg-[#11131a] p-4 animate-pulse", className)}>
        <div className="mb-4 h-5 w-48 rounded bg-zinc-800" />
        <div className="space-y-3">
          {Array.from({ length: count }).map((_, i) => (
            <div key={i} className="flex gap-4 border-b border-zinc-800/50 pb-3">
              <div className="h-4 w-28 rounded bg-zinc-800" />
              <div className="h-4 flex-1 rounded bg-zinc-800/60" />
              <div className="h-4 w-20 rounded bg-zinc-800" />
              <div className="h-4 w-16 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (variant === "dossier") {
    return (
      <div className={cn("space-y-6 animate-pulse", className)}>
        <div className="h-32 rounded-lg border border-zinc-800/80 bg-[#11131a] p-6">
          <div className="h-6 w-64 rounded bg-zinc-800" />
          <div className="mt-4 h-4 w-96 rounded bg-zinc-800/60" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="h-64 rounded-lg border border-zinc-800/80 bg-[#11131a] p-6 lg:col-span-2">
            <div className="h-5 w-40 rounded bg-zinc-800" />
          </div>
          <div className="h-64 rounded-lg border border-zinc-800/80 bg-[#11131a] p-6">
            <div className="h-5 w-32 rounded bg-zinc-800" />
          </div>
        </div>
      </div>
    );
  }

  return <div className={cn("h-4 w-full rounded bg-zinc-800 animate-pulse", className)} />;
}
