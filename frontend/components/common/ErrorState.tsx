import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils/formatters";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "API Communication Error",
  message = "Failed to load data from the FastAPI backend service.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-sm border p-6 text-center text-[#eceae6]",
        className
      )}
      style={{
        borderColor: "var(--variance-border)",
        background: "var(--variance-bg)",
      }}
    >
      <div className="mb-2 text-[#e07070]">
        <AlertTriangle className="h-5 w-5" />
      </div>
      <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#e07070]">
        {title}
      </h3>
      <p className="mt-1 max-w-md text-xs text-[#8e96a0]">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-xs font-mono font-medium text-[#eceae6] transition-micro"
          style={{
            borderColor: "var(--border-standard)",
            background: "var(--surface-3)",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = "var(--border-prominent)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = "var(--border-standard)";
          }}
        >
          <RefreshCw className="h-3 w-3" />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  );
}
