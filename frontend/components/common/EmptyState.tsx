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
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 bg-[#11131a]/50 p-8 text-center",
        className
      )}
    >
      <div className="mb-3 rounded-full bg-zinc-900 border border-zinc-800 p-3 text-zinc-400">
        {icon || <Inbox className="h-6 w-6" />}
      </div>
      <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-zinc-400">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
