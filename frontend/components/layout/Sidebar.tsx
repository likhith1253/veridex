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
      className="w-56 flex-shrink-0 flex flex-col select-none"
      style={{
        background: "var(--surface-1)",
        borderRight: "1px solid var(--border-subtle)",
      }}
    >
      {/* Brand Header */}
      <div
        className="h-14 flex items-center px-4"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2.5">
          <div className="vx-mark">VX</div>
          <div>
            <div
              className="text-[13px] font-bold tracking-[0.08em]"
              style={{ color: "var(--text-primary)" }}
            >
              VERIDEX
            </div>
            <div
              className="text-[10px] tracking-normal font-normal"
              style={{ color: "var(--text-tertiary)" }}
            >
              Financial Control Engine
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-5 scrollbar-none">
        {navGroups.map((grp) => (
          <div key={grp.group} className="space-y-0.5">
            <div
              className="px-2.5 pb-1.5 text-[9px] font-semibold uppercase tracking-[0.12em]"
              style={{ color: "var(--text-tertiary)" }}
            >
              {grp.group}
            </div>

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
                    "group flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-sm text-xs font-medium transition-micro",
                    isActive
                      ? "text-[#eceae6]"
                      : "text-[#8e96a0] hover:text-[#eceae6] hover:bg-[#13161a]"
                  )}
                  style={
                    isActive
                      ? {
                          background: "rgba(201, 169, 110, 0.08)",
                          borderLeft: "2px solid var(--accent)",
                          paddingLeft: "calc(0.625rem - 2px)",
                        }
                      : {
                          borderLeft: "2px solid transparent",
                          paddingLeft: "calc(0.625rem - 2px)",
                        }
                  }
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className="h-3.5 w-3.5 flex-shrink-0"
                      style={{
                        color: isActive ? "var(--accent)" : "currentColor",
                      }}
                    />
                    <span className="truncate text-[12px]">{item.name}</span>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {item.badge !== undefined && item.badgeVariant === "exception" && (
                      <span
                        className="px-1.5 py-px rounded-xs font-mono text-[9px] font-bold"
                        style={{
                          color: "var(--variance-text)",
                          background: "var(--variance-bg)",
                          border: "1px solid var(--variance-border)",
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                    {item.badge !== undefined && item.badgeVariant === "action" && (
                      <span
                        className="px-1.5 py-px rounded-xs font-mono text-[9px] font-bold"
                        style={{
                          color: "var(--pending-text)",
                          background: "var(--pending-bg)",
                          border: "1px solid var(--pending-border)",
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                    {item.dot && (
                      <span
                        className="status-dot"
                        style={{
                          background:
                            item.dot === "live"
                              ? "var(--matched-text)"
                              : "var(--text-tertiary)",
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

      {/* Engine Status Footer (Still, architectural) */}
      <div
        className="px-3.5 py-2.5 flex items-center justify-between"
        style={{
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="flex items-center gap-2">
          <Activity
            className="h-3 w-3"
            style={{ color: "var(--matched-text)" }}
          />
          <span
            className="font-mono text-[10px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            Engine Ready :8000
          </span>
        </div>
        <span
          className="font-mono text-[9px]"
          style={{ color: "var(--text-tertiary)", opacity: 0.6 }}
        >
          v0.2
        </span>
      </div>
    </aside>
  );
}
