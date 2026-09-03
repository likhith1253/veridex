import React, { type ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/lib/utils/formatters";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-sm border p-8 text-center",
        className
      )}
      style={{
        borderColor: "var(--border-subtle)",
        background: "var(--surface-1)",
      }}
    >
      <div className="mb-3 text-[#525c66]">
        {icon || <Inbox className="h-5 w-5" />}
      </div>
      <h3 className="text-xs font-mono font-semibold text-[#eceae6] uppercase tracking-wider">
        {title}
      </h3>
      <p className="mt-1 max-w-sm text-xs text-[#8e96a0] leading-relaxed">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
