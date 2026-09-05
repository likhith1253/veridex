"use client";

import React, { useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { RunBatchModal } from "../reconciliation/RunBatchModal";
import { CopilotDrawer } from "../copilot/CopilotDrawer";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // If viewing the public product website at root, omit AppShell
  // Note: All hooks must be called before any early return
  if (pathname === "/") {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F7F5F0] text-[#17191C]">
      {/* Deep Institutional Sidebar Navigation — fixed-width column on
          desktop, an off-canvas drawer below the md breakpoint (was
          previously always rendered at a fixed width with no way to hide
          it, clipping the entire main content column on phone-sized
          viewports). */}
      <Sidebar mobileOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      {/* Main Content Column */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Crisp Topbar */}
        <Topbar
          onOpenBatchModal={() => setIsBatchModalOpen(true)}
          onToggleCopilot={() => setIsCopilotOpen((prev) => !prev)}
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        />

        {/* Workspace Body */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#F7F5F0]">
          {children}
        </main>
      </div>

      {/* Global Modals & Drawers */}
      <RunBatchModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
      />
      <CopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
    </div>
  );
}
