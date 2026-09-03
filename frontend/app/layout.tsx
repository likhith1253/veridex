import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "VERIDEX — AI Financial Control & Reconciliation Engine",
  description: "Find the discrepancy. Prove the cause. Control the action.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className="h-full bg-[#090a0f] text-zinc-100 selection:bg-sky-500/20 selection:text-sky-300">
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
