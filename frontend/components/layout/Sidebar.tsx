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
  badgeVariant?: "exception" | "action";
  dot?: "live" | "offline";
}

interface NavGroup {
  group: string;
  items: NavItem[];
}

export function Sidebar() {
  const pathname = usePathname();

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
  const openExceptionsCount = overview?.open_exceptions || overview?.unresolved_transactions || 0;

  const navGroups: NavGroup[] = [
    {
      group: "OPERATIONS",
      items: [
        {
          name: "Command Center",
          href: "/app",
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
          badgeVariant: "exception",
        },
        {
          name: "Settlements",
          href: "/settlements",
          icon: Landmark,
        },
        {
          name: "Actions",
          href: "/actions",
          icon: ShieldCheck,
          badge: pendingActionsCount > 0 ? pendingActionsCount : undefined,
          badgeVariant: "action",
        },
        {
          name: "Audit",
          href: "/audit",
          icon: History,
        },
      ],
    },
    {
      group: "INFRASTRUCTURE",
      items: [
        {
          name: "Razorpay",
          href: "/razorpay",
          icon: CreditCard,
          dot: rzpStatus?.api_reachable ? "live" : "offline",
        },
        {
          name: "Benchmark",
          href: "/benchmark",
          icon: BarChart3,
        },
      ],
    },
    {
      group: "SYSTEM",
      items: [
        {
          name: "Settings",
          href: "/settings",
          icon: Settings,
        },
      ],
    },
  ];

  return (
    <aside
      className="w-56 flex-shrink-0 flex flex-col select-none border-r border-[#262A30] bg-[#171A1E]"
    >
      {/* Brand Header */}
      <div className="h-14 flex items-center px-4 border-b border-[#262A30]">
        <div className="flex items-center gap-2.5">
          <div className="vx-mark">VX</div>
          <div>
            <div className="text-[13px] font-bold tracking-[0.08em] text-[#ECEAE6]">
              VERIDEX
            </div>
            <div className="text-[10px] tracking-normal font-normal text-[#8E96A0]">
              Financial Control Engine
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-5 scrollbar-none">
        {navGroups.map((grp) => (
          <div key={grp.group} className="space-y-0.5">
            <div className="px-2.5 pb-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#6F747A]">
              {grp.group}
            </div>

            {grp.items.map((item) => {
              const isActive =
                item.href === "/app"
                  ? pathname === "/app" || pathname === "/"
                  : pathname.startsWith(item.href);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-xs text-xs font-medium transition-micro",
                    isActive
                      ? "text-[#FFFFFF] bg-[rgba(201,169,110,0.12)] border-l-2 border-[#C9A96E]"
                      : "text-[#8E96A0] hover:text-[#ECEAE6] hover:bg-[#21252B] border-l-2 border-transparent"
                  )}
                  style={{
                    paddingLeft: "calc(0.625rem - 2px)",
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className={cn(
                        "h-3.5 w-3.5 flex-shrink-0 transition-micro",
                        isActive ? "text-[#C9A96E]" : "text-[#8E96A0] group-hover:text-[#ECEAE6]"
                      )}
                    />
                    <span className="truncate text-[12px]">{item.name}</span>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {item.badge !== undefined && item.badgeVariant === "exception" && (
                      <span className="px-1.5 py-px rounded-xs font-mono text-[9px] font-bold text-[#E07070] bg-[rgba(184,58,58,0.2)] border border-[rgba(184,58,58,0.4)]">
                        {item.badge}
                      </span>
                    )}
                    {item.badge !== undefined && item.badgeVariant === "action" && (
                      <span className="px-1.5 py-px rounded-xs font-mono text-[9px] font-bold text-[#D8BC8A] bg-[rgba(201,169,110,0.2)] border border-[rgba(201,169,110,0.4)]">
                        {item.badge}
                      </span>
                    )}
                    {item.dot && (
                      <span
                        className="status-dot"
                        style={{
                          background:
                            item.dot === "live"
                              ? "#1E7B4D"
                              : "#6F747A",
                        }}
                      />
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        ))}
      </div>

      {/* Engine Status Footer (Still, permanent, institutional) */}
      <div className="px-3.5 py-2.5 flex items-center justify-between border-t border-[#262A30] bg-[#13161A]">
        <div className="flex items-center gap-2">
          <Activity className="h-3 w-3 text-[#1E7B4D]" />
          <span className="font-mono text-[10px] text-[#8E96A0]">
            Engine Ready :8000
          </span>
        </div>
        <span className="font-mono text-[9px] text-[#6F747A]">
          v0.2
        </span>
      </div>
    </aside>
  );
}
