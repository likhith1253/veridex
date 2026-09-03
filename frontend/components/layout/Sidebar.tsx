"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitMerge,
  AlertOctagon,
  Landmark,
  ShieldCheck,
  History,
  CreditCard,
  BarChart3,
  Settings,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils/formatters";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { actionsApi } from "@/lib/api/actionsApi";
import { integrationsApi } from "@/lib/api/integrationsApi";

interface NavItem {
  name: string;
  href: string;
  icon: React.ElementType;
  badge?: number | string;
  badgeColor?: string;
  dot?: string;
}

interface NavGroup {
  group: string;
  items: NavItem[];
}

export function Sidebar() {
  const pathname = usePathname();

  // Live queries for navigation badges
  const { data: overview } = useQuery({
    queryKey: ["sidebar-overview"],
    queryFn: () => controllerApi.getOverview(),
    staleTime: 10000,
  });

  const { data: actions } = useQuery({
    queryKey: ["sidebar-actions"],
    queryFn: () => actionsApi.getActions({ state: "PENDING_APPROVAL" }),
    staleTime: 10000,
  });

  const { data: rzpStatus } = useQuery({
    queryKey: ["sidebar-rzp"],
    queryFn: () => integrationsApi.getRazorpayStatus(),
    staleTime: 15000,
  });

  const pendingActionsCount = actions?.length || 0;
  const openExceptionsCount = overview?.open_exceptions || 0;

  const navGroups: NavGroup[] = [
    {
      group: "Core Operations",
      items: [
        {
          name: "Command Center",
          href: "/",
          icon: LayoutDashboard,
        },
        {
          name: "Reconciliation",
          href: "/reconciliation",
          icon: GitMerge,
        },
        {
          name: "Exceptions",
          href: "/exceptions",
          icon: AlertOctagon,
          badge: openExceptionsCount > 0 ? openExceptionsCount : undefined,
          badgeColor: "bg-rose-950 text-rose-400 border-rose-800",
        },
        {
          name: "Settlements & Tax",
          href: "/settlements",
          icon: Landmark,
        },
        {
          name: "Actions & HITL",
          href: "/actions",
          icon: ShieldCheck,
          badge: pendingActionsCount > 0 ? pendingActionsCount : undefined,
          badgeColor: "bg-amber-950 text-amber-400 border-amber-800",
        },
        {
          name: "Audit Trail",
          href: "/audit",
          icon: History,
        },
      ],
    },
    {
      group: "Integrations & Evaluation",
      items: [
        {
          name: "Razorpay Gateway",
          href: "/razorpay",
          icon: CreditCard,
          dot: rzpStatus?.api_reachable ? "bg-emerald-400" : "bg-zinc-500",
        },
        {
          name: "Benchmark & Accuracy",
          href: "/benchmark",
          icon: BarChart3,
        },
        {
          name: "System Settings",
          href: "/settings",
          icon: Settings,
        },
      ],
    },
  ];

  return (
    <aside className="w-64 flex-shrink-0 flex flex-col border-r border-[#222634] bg-[#0c0e14] text-zinc-300 select-none">
      {/* Brand Header */}
      <div className="h-14 flex items-center px-4 border-b border-[#222634]">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded bg-gradient-to-br from-sky-400 to-indigo-600 flex items-center justify-center font-mono font-bold text-xs text-black shadow-sm">
            VX
          </div>
          <div>
            <div className="font-mono text-sm font-bold tracking-wider text-zinc-100 flex items-center gap-1.5">
              VERIDEX
              <span className="text-[9px] font-sans px-1 py-0.2 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                PROD
              </span>
            </div>
            <div className="text-[10px] text-zinc-500 tracking-tight">Financial Control Engine</div>
          </div>
        </div>
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
        {navGroups.map((grp) => (
          <div key={grp.group} className="space-y-1">
            <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              {grp.group}
            </div>
            <div className="space-y-0.5 pt-1">
              {grp.items.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center justify-between gap-3 px-2.5 py-1.5 rounded text-xs font-medium transition-colors",
                      isActive
                        ? "bg-[#171a23] text-sky-400 border border-sky-500/20 shadow-sm"
                        : "text-zinc-400 hover:bg-[#131620] hover:text-zinc-200"
                    )}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon className={cn("h-4 w-4 flex-shrink-0", isActive ? "text-sky-400" : "text-zinc-500")} />
                      <span className="truncate">{item.name}</span>
                    </div>

                    {item.badge !== undefined && (
                      <span
                        className={cn(
                          "px-1.5 py-0.2 rounded font-mono text-[10px] border font-bold",
                          item.badgeColor
                        )}
                      >
                        {item.badge}
                      </span>
                    )}

                    {item.dot && (
                      <span className={cn("h-1.5 w-1.5 rounded-full", item.dot)} />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Footer System Status */}
      <div className="p-3 border-t border-[#222634] bg-[#090a0f] text-[11px] text-zinc-400 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5 text-emerald-400 animate-pulse" />
          <span className="font-mono text-[10px] text-zinc-400">FastAPI :8000</span>
        </div>
        <span className="font-mono text-[9px] text-zinc-600">v0.2.0</span>
      </div>
    </aside>
  );
}
