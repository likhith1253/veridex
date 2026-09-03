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
              "h-28 rounded-sm border p-4",
              className
            )}
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div className="h-3 w-20 skeleton rounded-xs" />
            <div className="mt-4 h-6 w-32 skeleton rounded-xs" />
            <div className="mt-3 h-3 w-40 skeleton rounded-xs" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === "table") {
    return (
      <div
        className={cn("rounded-sm border p-4", className)}
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="mb-4 h-4 w-36 skeleton rounded-xs" />
        <div className="space-y-3">
          {Array.from({ length: count }).map((_, i) => (
            <div
              key={i}
              className="flex gap-4 pb-3"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div className="h-3.5 w-24 skeleton rounded-xs" />
              <div className="h-3.5 flex-1 skeleton rounded-xs" />
              <div className="h-3.5 w-20 skeleton rounded-xs" />
              <div className="h-3.5 w-16 skeleton rounded-xs" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (variant === "dossier") {
    return (
      <div className={cn("space-y-6", className)}>
        <div
          className="h-32 rounded-sm border p-6"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div className="h-5 w-56 skeleton rounded-xs" />
          <div className="mt-4 h-3.5 w-80 skeleton rounded-xs" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div
            className="h-64 rounded-sm border p-6 lg:col-span-2"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div className="h-4 w-36 skeleton rounded-xs" />
          </div>
          <div
            className="h-64 rounded-sm border p-6"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div className="h-4 w-28 skeleton rounded-xs" />
          </div>
        </div>
      </div>
    );
  }

  return <div className={cn("h-3.5 w-full skeleton rounded-xs", className)} />;
}
